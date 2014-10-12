import ConfigParser
import logging
import os
import shutil
import tempfile

from nectar.listener import AggregatingEventListener
from nectar.request import DownloadRequest

from pulp.server.db.model.criteria import UnitAssociationCriteria

from pulp_rpm.common import constants, ids
from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.importers.yum.listener import DistroFileListener
from pulp_rpm.plugins.importers.yum.repomd import nectar_factory


SECTION_GENERAL = 'general'
SECTION_STAGE2 = 'stage2'
SECTION_CHECKSUMS = 'checksums'
KEY_PACKAGEDIR = 'packagedir'

_LOGGER = logging.getLogger(__name__)


def sync(sync_conduit, feed, working_dir, nectar_config, report, progress_callback):
    """
    Look for a distribution in the target repo and sync it if found

    :param sync_conduit:        conduit provided by the platform
    :type  sync_conduit:        pulp.plugins.conduits.repo_sync.RepoSyncConduit
    :param feed:                URL of the yum repo being sync'd
    :type  feed:                basestring
    :param working_dir:         full path to the directory to which files
                                should be downloaded
    :type  working_dir:         basestring
    :param nectar_config:       download config to be used by nectar
    :type  nectar_config:       nectar.config.DownloaderConfig
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
        treefile_path = get_treefile(feed, tmp_dir, nectar_config)
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
        listener = DistroFileListener(report, progress_callback)
        downloader = nectar_factory.create_downloader(feed, nectar_config, listener)
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
            # find any old distribution units and remove them. See BZ #1150714
            distribution_type_criteria = UnitAssociationCriteria(type_ids=[ids.TYPE_ID_DISTRO])
            existing_units = sync_conduit.get_units(criteria=distribution_type_criteria)
            for existing_unit in existing_units:
                if existing_unit != unit:
                    _LOGGER.info("Removing out-of-date distribution unit %s for repo %s" %
                                 (existing_unit.unit_key, sync_conduit.repo_id))
                    sync_conduit.remove_unit(existing_unit)
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


def strip_treeinfo_repomd(treeinfo_path):
    """
    strip repomd checksums from the treeinfo. These cause two issues:
      * pulp thinks repomd.xml is content and not metadata if it's listed here
      * pulp regenerates the repomd.xml file anyway, which would cause the
        listed checksum to be wrong

    :param treeinfo_path:            path to the on-disk treeinfo file
    :type  treeinfo_path:            str
    """
    # read entire treeinfo, strip entry we don't want, and replace with our new treeinfo
    with open(treeinfo_path, 'r+') as f:
        original_treeinfo_data = f.readlines()
        new_treeinfo_data = []
        for line in original_treeinfo_data:
            if not line.startswith('repodata/repomd.xml = '):
                new_treeinfo_data.append(line)
        f.seek(0)
        f.writelines(new_treeinfo_data)
        # truncate file to current position before closing
        f.truncate()


def get_treefile(feed, tmp_dir, nectar_config):
    """
    Download the treefile and return its full path on disk, or None if not found

    :param feed:            URL to the repository
    :type  feed:            str
    :param tmp_dir:         full path to the temporary directory being used
    :type  tmp_dir:         str
    :param nectar_config:   download config to be used by nectar
    :type  nectar_config:   nectar.config.DownloaderConfig

    :return:        full path to treefile on disk, or None if not found
    :rtype:         str or NoneType
    """
    for filename in constants.TREE_INFO_LIST:
        path = os.path.join(tmp_dir, filename)
        url = os.path.join(feed, filename)
        request = DownloadRequest(url, path)
        listener = AggregatingEventListener()
        downloader = nectar_factory.create_downloader(feed, nectar_config, listener)
        downloader.download([request])
        if len(listener.succeeded_reports) == 1:
            # bz 1095829
            strip_treeinfo_repomd(path)
            return path


def parse_treefile(path):
    """
    The treefile seems to be approximately in INI format, which can be read
    by the standard library's ConfigParser.

    :param path:    full path to the treefile
    :return:        instance of Distribution model, and a list of dicts
                    describing the distribution's files
    :rtype:         (pulp_rpm.plugins.db.models.Distribution, dict)
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

    # apparently the 'variant' is optional. for example, it does not appear
    # in the RHEL 5.9 treeinfo file. This is how the previous importer
    # handled that.
    try:
        variant = parser.get(SECTION_GENERAL, 'variant')
    except ConfigParser.NoOptionError:
        variant = None
    try:
        packagedir = parser.get(SECTION_GENERAL, KEY_PACKAGEDIR)
    except ConfigParser.NoOptionError:
        packagedir = None

    try:
        model = models.Distribution(
            parser.get(SECTION_GENERAL, 'family'),
            variant,
            parser.get(SECTION_GENERAL, 'version'),
            parser.get(SECTION_GENERAL, 'arch'),
            metadata={KEY_PACKAGEDIR: packagedir}
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
