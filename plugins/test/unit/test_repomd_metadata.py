# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the License
# (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied, including the
# implied warranties of MERCHANTABILITY, NON-INFRINGEMENT, or FITNESS FOR A
# PARTICULAR PURPOSE.
# You should have received a copy of GPLv2 along with this software; if not,
# see http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt


import unittest

import mock
from nectar.config import DownloaderConfig

from pulp_rpm.plugins.importers.yum.repomd import metadata


def file_info_factory(name, path=None):
    ret = metadata.FILE_INFO_SKEL.copy()
    ret.update({
        'name': name,
        'relative_path': path or 'x/y/z/%s' % name,
    })
    return ret


class TestDownloadMetadataFiles(unittest.TestCase):
    def setUp(self):
        self.metadata_files = metadata.MetadataFiles('http://pulpproject.org',
                                                     '/a/b/c',
                                                     DownloaderConfig())

    def test_skip_known_sqlite_files(self):
        self.metadata_files.metadata = {
            'primary': file_info_factory('primary'),
            'other_db': file_info_factory('other_db'),
        }

        self.metadata_files.downloader.download = mock.MagicMock(
            spec_set=self.metadata_files.downloader.download)

        self.metadata_files.download_metadata_files()

        requests = self.metadata_files.downloader.download.call_args[0][0]

        self.assertEqual(len(requests), 1)
        self.assertTrue(requests[0].destination.endswith('primary'))

    def test_does_not_skip_unknown_sqlite_files(self):
        self.metadata_files.metadata = {
            'primary': file_info_factory('primary'),
            # this one isn't "known" and thus should be downloaded
            'pkgtags': file_info_factory('pkgtags', 'x/y/z/pkgtags.sqlite.gz'),
        }

        self.metadata_files.downloader.download = mock.MagicMock(
            spec_set=self.metadata_files.downloader.download)

        self.metadata_files.download_metadata_files()

        requests = self.metadata_files.downloader.download.call_args[0][0]

        # make sure both files had download requests created and passed to the
        # downloader
        self.assertEqual(len(requests), 2)
        self.assertTrue(requests[0].destination.endswith('primary'))
        self.assertTrue(requests[1].destination.endswith('pkgtags.sqlite.gz'))
