# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

import ConfigParser
import logging
import os
import shutil
import tempfile

from nectar.config import DownloaderConfig
from nectar.downloaders.curl import HTTPCurlDownloader
from nectar.listener import AggregatingEventListener
from nectar.request import DownloadRequest

from pulp_rpm.common import constants, ids, models
from pulp_rpm.plugins.importers.yum.listener import DistroFileListener

SECTION_GENERAL = 'general'
SECTION_STAGE2 = 'stage2'
SECTION_CHECKSUMS = 'checksums'

_LOGGER = logging.getLogger(__name__)


def sync(sync_conduit, feed, working_dir, report, progress_callback):
    """
    Look for a distribution in the target repo and sync it if found

    :param sync_conduit:        conduit provided by the platform
    :type  sync_conduit:        pulp.plugins.conduits.repo_sync.RepoSyncConduit
    :param feed:                URL of the yum repo being sync'd
    :type  feed:                basestring
    :param working_dir:         full path to the directory to which files
                                should be downloaded
    :type  working_dir:         basestring
    :param report:              progress report object
    :type  report:              pulp_rpm.plugins.importers.yum.report.DistributionReport
    :param progress_callback:   function that takes no arguments but induces
                                the current progress report to be sent.
    """
    # this temporary dir will hopefully be moved to the unit's storage path
    # if all downloads go well. If not, it will be deleted below, ensuring a
    # complete cleanup
    tmp_dir = tempfile.mkdtemp(dir=working_dir)
    try:
        treefile_path = get_treefile(feed, tmp_dir)
        if not treefile_path:
            _LOGGER.debug('no treefile found')
            report['state'] = constants.STATE_COMPLETE
            return

        try:
            model, files = parse_treefile(treefile_path)
        except ValueError:
            _LOGGER.error('could not parse treefile')
            report['state'] = constants.STATE_FAILED
            return

        report.set_initial_values(len(files))
        config = DownloaderConfig()
        listener = DistroFileListener(report, progress_callback)
        downloader = HTTPCurlDownloader(config, listener)
        _LOGGER.debug('downloading distribution files')
        downloader.download(file_to_download_request(f, feed, tmp_dir) for f in files)
        if len(listener.failed_reports) == 0:
            unit = sync_conduit.init_unit(ids.TYPE_ID_DISTRO, model.unit_key, model.metadata, model.relative_path)
            model.process_download_reports(listener.succeeded_reports)
            # remove pre-existing dir
            shutil.rmtree(unit.storage_path, ignore_errors=True)
            shutil.move(tmp_dir, unit.storage_path)
            # mkdtemp is very paranoid, so we'll change to more sensible perms
            os.chmod(unit.storage_path, 0o775)
            sync_conduit.save_unit(unit)
        else:
            _LOGGER.error('some distro file downloads failed')
            report['state'] = constants.STATE_FAILED
            report['error_details'] = [(fail.url, fail.error_report) for fail in listener.failed_reports]
            return
        report['state'] = constants.STATE_COMPLETE
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def file_to_download_request(file_dict, feed, storage_path):
    """
    Takes information about a file described in a treeinfo file and turns that
    into a download request suitable for use with nectar.

    :param file_dict:       dict containing keys 'relativepath', 'checksum',
                            and 'checksumtype'.
    :type  file_dict:       dict
    :param feed:            URL to the base of a repository
    :type  feed:            basestring
    :param storage_path:    full filesystem path to where the downloaded files
                            should be saved.
    :type  storage_path:    basestring

    :return:    new download request
    :rtype:     nectar.request.DownloadRequest
    """
    savepath = os.path.join(storage_path, file_dict['relativepath'])
    # make directories such as "images"
    if not os.path.exists(os.path.dirname(savepath)):
        os.makedirs(os.path.dirname(savepath))

    return DownloadRequest(
        os.path.join(feed, file_dict['relativepath']),
        savepath,
        file_dict,
    )


def get_treefile(feed, tmp_dir):
    """
    Download the treefile and return its full path on disk, or None if not found

    :param feed:    URL to the repository
    :type  feed:    str
    :param tmp_dir: full path to the temporary directory being used
    :type  tmp_dir: str
    :return:        full path to treefile on disk, or None if not found
    :rtype:         str or NoneType
    """
    for filename in constants.TREE_INFO_LIST:
        path = os.path.join(tmp_dir, filename)
        url = os.path.join(feed, filename)
        request = DownloadRequest(url, path)
        # TODO: use the config settings available from the sync workflow.
        config = DownloaderConfig()
        listener = AggregatingEventListener()
        downloader = HTTPCurlDownloader(config, listener)
        downloader.download([request])
        if len(listener.succeeded_reports) == 1:
            return path


def parse_treefile(path):
    """
    The treefile seems to be approximately in INI format, which can be read
    by the standard library's ConfigParser.

    :param path:    full path to the treefile
    :return:        instance of Distribution model, and a list of dicts
                    describing the distribution's files
    :rtype:         (pulp_rpm.common.models.Distribution, dict)
    """
    parser = ConfigParser.RawConfigParser()
    # the default implementation of this method makes all option names lowercase,
    # which we don't want. This is the suggested solution in the python.org docs.
    parser.optionxform = str
    with open(path) as open_file:
        try:
            parser.readfp(open_file)
        except ConfigParser.ParsingError:
            # wouldn't need this if ParsingError subclassed ValueError.
            raise ValueError('could not parse treeinfo file')
    try:
        model = models.Distribution(
            parser.get(SECTION_GENERAL, 'family'),
            parser.get(SECTION_GENERAL, 'variant'),
            parser.get(SECTION_GENERAL, 'version'),
            parser.get(SECTION_GENERAL, 'arch'),
        )
    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
        raise ValueError('invalid treefile: could not find unit key components')
    files = {}
    # this section is likely to have all the files we care about listed with
    # checksums. But, it might not. Other sections checked below will only add
    # files to the "files" dict if they are not already present. For those cases,
    # there will not be checksums available.
    if parser.has_section(SECTION_CHECKSUMS):
        for item in parser.items(SECTION_CHECKSUMS):
            relativepath = item[0]
            checksumtype, checksum = item[1].split(':')
            files[relativepath] = {
                'relativepath': relativepath,
                'checksum': checksum,
                'checksumtype': checksumtype
            }

    for section_name in parser.sections():
        if section_name.startswith('images-') or section_name == SECTION_STAGE2:
            for item in parser.items(section_name):
                if item[1] not in files:
                    relativepath = item[1]
                    files[relativepath] = {
                        'relativepath': relativepath,
                        'checksum': None,
                        'checksumtype': None,
                    }

    return model, files.values()
