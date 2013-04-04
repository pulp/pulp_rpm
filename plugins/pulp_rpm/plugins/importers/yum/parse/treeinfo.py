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
import os.path
import shutil

from pulp.common.download.config import DownloaderConfig
from pulp.common.download.downloaders.curl import HTTPCurlDownloader
from pulp.common.download.listener import AggregatingEventListener
from pulp.common.download.request import DownloadRequest

from pulp_rpm.common import constants, ids, models

SECTION_GENERAL = 'general'
SECTION_STAGE2 = 'stage2'
SECTION_CHECKSUMS = 'checksums'

_LOGGER = logging.getLogger(__name__)


def main(sync_conduit, feed, tmp_dir):
    treefile_path = get_treefile(feed, tmp_dir)
    try:
        model, files = parse_treefile(treefile_path)
    except ValueError:
        return
    config = DownloaderConfig()
    listener = AggregatingEventListener()
    downloader = HTTPCurlDownloader(config, listener)
    downloader.download(file_to_download_request(f, feed, tmp_dir) for f in files)
    if len(listener.failed_reports) == 0:
        model.process_download_reports(listener.succeeded_reports)
        unit = sync_conduit.init_unit(ids.TYPE_ID_DISTRO, model.unit_key, model.metadata, model.relative_path)
        shutil.move(treefile_path, unit.storage_path)
        sync_conduit.save_unit(unit)
    else:
        # TODO: log something?
        pass


def file_to_download_request(file_dict, feed, storage_path):
    _LOGGER.info(locals())
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
    # try to get treeinfo file
    for filename in constants.TREE_INFO_LIST:
        path = os.path.join(tmp_dir, filename)
        url = os.path.join(feed, filename)
        request = DownloadRequest(url, path)
        # TODO: combine these three lines?
        config = DownloaderConfig()
        listener = AggregatingEventListener()
        downloader = HTTPCurlDownloader(config, listener)
        downloader.download([request])
        if len(listener.succeeded_reports) == 1:
            return path


def parse_treefile(path):
    parser = ConfigParser.RawConfigParser()
    with open(path) as open_file:
        parser.readfp(open_file)
    try:
        model = models.Distribution(
            parser.get(SECTION_GENERAL, 'family'),
            parser.get(SECTION_GENERAL, 'variant'),
            parser.get(SECTION_GENERAL, 'version'),
            parser.get(SECTION_GENERAL, 'arch'),
        )
    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
        raise ValueError
    files = {}
    if parser.has_section(SECTION_CHECKSUMS):
        for item in parser.items(SECTION_CHECKSUMS):
            relativepath = item[0]
            checksumtype, checksum = item[1].split(':')
            files[relativepath] = {
                'relativepath': relativepath,
                'checksum': checksum,
                'checksumtype': checksumtype
            }
    if parser.has_section(SECTION_STAGE2):
        for item in parser.items(SECTION_STAGE2):
            if item[0] not in files:
                relativepath = item[0]
                files[relativepath] = {
                    'relativepath': relativepath,
                    'checksum': None,
                    'checksumtype': None,
                }
    # TODO: look at "images-*" sections

    return model, files.values()

