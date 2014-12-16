# -*- coding: utf-8 -*-

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


class TestMetadataFiles(unittest.TestCase):
    def setUp(self):
        self.metadata_files = metadata.MetadataFiles('http://pulpproject.org',
                                                     '/a/b/c',
                                                     DownloaderConfig())

    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.metadata.change_location_tag')
    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.metadata.gdbm.open')
    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.metadata.other')
    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.metadata.filelists')
    def test_add_repo_data_filters_location_tag(self, mock_filelists, mock_other, mock_open,
                                                mock_change_location_tag):
        model = mock.Mock(metadata={})
        raw_xml = '<location xml:base="flux" href="qux"/>'
        model.raw_xml = raw_xml
        mock_open.return_value = mock.MagicMock()
        mock_open.return_value.__getitem__.return_value = raw_xml
        mock_open.return_value.close = mock.Mock()
        self.metadata_files.generate_db_key = mock.Mock(return_value='foo')
        self.metadata_files.dbs = mock.MagicMock()
        mock_filelists.process_package_element.return_value = ('a', 'b')
        mock_other.process_package_element.return_value = ('a', 'b')

        # we actually only care about the location tag, the previous mock setup
        # was to enable this testing
        mock_change_location_tag.return_value = 'baz'
        self.metadata_files.add_repodata(model)
        mock_change_location_tag.assert_called_once_with(raw_xml, model.relative_path)
        self.assertEquals('baz', model.metadata['repodata']['primary'])


class TestProcessRepomdDataElement(unittest.TestCase):
    """
    This class contains tests for the process_repomd_data_element() function.
    """
    def test_sanitizes_checksum_tag(self):
        """
        Assert that the function properly sanitizes the checksum type in the checksum tag.
        """
        def mock_find(tag):
            checksum_element = mock.MagicMock()
            if tag == metadata.CHECKSUM_TAG:
                checksum_element.attrib = {'type': 'sha'}
                checksum_element.text = 'checksum'
            return checksum_element

        data_element = mock.MagicMock()
        data_element.find.side_effect = mock_find

        file_info = metadata.process_repomd_data_element(data_element)

        self.assertEqual(file_info['checksum']['algorithm'], 'sha1')

    def test_sanitizes_open_checksum_tag(self):
        """
        Assert that the function properly sanitizes the checksum type in the open checksum tag.
        """
        def mock_find(tag):
            checksum_element = mock.MagicMock()
            if tag == metadata.OPEN_CHECKSUM_TAG:
                checksum_element.attrib = {'type': 'sha'}
                checksum_element.text = 'checksum'
            return checksum_element

        data_element = mock.MagicMock()
        data_element.find.side_effect = mock_find

        file_info = metadata.process_repomd_data_element(data_element)

        self.assertEqual(file_info['open_checksum']['algorithm'], 'sha1')
