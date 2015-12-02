# -*- coding: utf-8 -*-
import bz2
import lzma
import os
import shutil
import tempfile
import unittest

import mock
from nectar.config import DownloaderConfig

from pulp_rpm.plugins.importers.yum.utils import RepoURLModifier
from pulp_rpm.plugins.importers.yum.repomd import metadata


def file_info_factory(name, path=None):
    ret = metadata.FILE_INFO_SKEL.copy()
    ret.update({
        'name': name,
        'relative_path': path or 'x/y/z/%s' % name,
    })
    return ret


class TestParseRepomd(unittest.TestCase):
    repodata_path = os.path.join(os.path.dirname(__file__), '../../../../../data/test_repodata')
    repodata_path_bad_revision = os.path.join(os.path.dirname(__file__),
                                              '../../../../../data/test_repodata_badrevision')

    def setUp(self):
        self.metadata_files = metadata.MetadataFiles('http://pulpproject.org',
                                                     '/a/b/c',
                                                     DownloaderConfig())

    def test_parse_revision(self):
        self.metadata_files.dst_dir = self.repodata_path

        self.metadata_files.parse_repomd()

        self.assertEqual(self.metadata_files.revision, 1331832478)

    def test_parse_bad_revision(self):
        self.metadata_files.dst_dir = self.repodata_path_bad_revision

        self.metadata_files.parse_repomd()

        self.assertEqual(self.metadata_files.revision, 0)

    def test_primary(self):
        self.metadata_files.dst_dir = self.repodata_path

        self.metadata_files.parse_repomd()

        self.assertEqual(self.metadata_files.metadata['primary']['name'], 'primary')
        self.assertEqual(self.metadata_files.metadata['primary']['size'], 3749)
        self.assertEqual(self.metadata_files.metadata['primary']['open_size'], 31607)
        self.assertEqual(self.metadata_files.metadata['primary']['timestamp'], 1331832478)
        self.assertEqual(self.metadata_files.metadata['primary']['checksum']['algorithm'], 'sha256')
        self.assertEqual(self.metadata_files.metadata['primary']['checksum']['hex_digest'],
                         'be20ece13e6c21b132667ddcaa4d7ad0b32e470b9917aba51979e0707116280d')
        self.assertEqual(self.metadata_files.metadata['primary']['open_checksum']['algorithm'],
                         'sha256')
        self.assertEqual(self.metadata_files.metadata['primary']['open_checksum']['hex_digest'],
                         'b40b555e80502128423000a91cedd91fc85f209f1408e0b584221fbca2a319ae')
        self.assertEqual(self.metadata_files.metadata['primary']['relative_path'],
                         'repodata/be20ece13e6c21b132667ddcaa4d7ad0b32e470b9917aba51979e0707116280d'
                         '-primary.xml.gz')

    def test_filelists(self):
        self.metadata_files.dst_dir = self.repodata_path

        self.metadata_files.parse_repomd()

        self.assertEqual(self.metadata_files.metadata['filelists']['name'], 'filelists')
        self.assertEqual(self.metadata_files.metadata['filelists']['size'], 2022)
        self.assertEqual(self.metadata_files.metadata['filelists']['open_size'], 6514)
        self.assertEqual(self.metadata_files.metadata['filelists']['timestamp'], 1331832478)
        self.assertEqual(self.metadata_files.metadata['filelists']['checksum']['algorithm'],
                         'sha256')
        self.assertEqual(self.metadata_files.metadata['filelists']['checksum']['hex_digest'],
                         'b1a19cee1da6a1ddc798fcb85629bb73c0ce817e2ead51b33d60e9482af4dcf0')
        self.assertEqual(self.metadata_files.metadata['filelists']['open_checksum']['algorithm'],
                         'sha256')
        self.assertEqual(self.metadata_files.metadata['filelists']['open_checksum']['hex_digest'],
                         '6d0c14e876c1d0cfe7ea3cee42c0a4777da674cb6145fb9a3eb1814bfa21552a')
        self.assertEqual(self.metadata_files.metadata['filelists']['relative_path'],
                         'repodata/b1a19cee1da6a1ddc798fcb85629bb73c0ce817e2ead51b33d60e9482af4dcf0'
                         '-filelists.xml.gz')

    def test_other(self):
        self.metadata_files.dst_dir = self.repodata_path

        self.metadata_files.parse_repomd()

        self.assertEqual(self.metadata_files.metadata['other']['name'], 'other')
        self.assertEqual(self.metadata_files.metadata['other']['size'], 1864)
        self.assertEqual(self.metadata_files.metadata['other']['open_size'], 5471)
        self.assertEqual(self.metadata_files.metadata['other']['timestamp'], 1331832478)
        self.assertEqual(self.metadata_files.metadata['other']['checksum']['algorithm'], 'sha256')
        self.assertEqual(self.metadata_files.metadata['other']['checksum']['hex_digest'],
                         '98685671697c558eaa2b253df3df0b99bed62b4b9ca68db6b001384dac85db21')
        self.assertEqual(self.metadata_files.metadata['other']['open_checksum']['algorithm'],
                         'sha256')
        self.assertEqual(self.metadata_files.metadata['other']['open_checksum']['hex_digest'],
                         '0a8557d22baa874f269432a24f1a5af49ad69ad363cd34464666ee36dc785a0e')
        self.assertEqual(self.metadata_files.metadata['other']['relative_path'],
                         'repodata/98685671697c558eaa2b253df3df0b99bed62b4b9ca68db6b001384dac85db21'
                         '-other.xml.gz')

    def test_updateinfo(self):
        self.metadata_files.dst_dir = self.repodata_path

        self.metadata_files.parse_repomd()

        self.assertEqual(self.metadata_files.metadata['updateinfo']['name'], 'updateinfo')
        self.assertEqual(self.metadata_files.metadata['updateinfo']['size'], 575)
        self.assertEqual(self.metadata_files.metadata['updateinfo']['timestamp'], 1331832479.81)
        self.assertEqual(self.metadata_files.metadata['updateinfo']['checksum']['algorithm'],
                         'sha256')
        self.assertEqual(self.metadata_files.metadata['updateinfo']['checksum']['hex_digest'],
                         'd9e3d0852ee61c495e3eed94e59d26782230a3ea80af581b451de70165036dab')
        self.assertEqual(self.metadata_files.metadata['updateinfo']['open_checksum']['algorithm'],
                         'sha256')
        self.assertEqual(self.metadata_files.metadata['updateinfo']['open_checksum']['hex_digest'],
                         '5bafe91f80679874fd59e720a07a876b52f1158c46aa6487e0dbbc7caca4179e')
        self.assertEqual(self.metadata_files.metadata['updateinfo']['relative_path'],
                         'repodata/d9e3d0852ee61c495e3eed94e59d26782230a3ea80af581b451de70165036dab'
                         '-updateinfo.xml.gz')

    def test_group_gz(self):
        self.metadata_files.dst_dir = self.repodata_path

        self.metadata_files.parse_repomd()

        self.assertEqual(self.metadata_files.metadata['group_gz']['name'], 'group_gz')
        self.assertEqual(self.metadata_files.metadata['group_gz']['size'], 539)
        self.assertEqual(self.metadata_files.metadata['group_gz']['timestamp'], 1331832479.68)
        self.assertEqual(self.metadata_files.metadata['group_gz']['checksum']['algorithm'],
                         'sha256')
        self.assertEqual(self.metadata_files.metadata['group_gz']['checksum']['hex_digest'],
                         '010d5d5877f1974802170acb0f278a5966e6469d464c89c3ca7b3658cccd9758')
        self.assertEqual(self.metadata_files.metadata['group_gz']['open_checksum']['algorithm'],
                         'sha256')
        self.assertEqual(self.metadata_files.metadata['group_gz']['open_checksum']['hex_digest'],
                         '497d2c3f2af57f60a8d289027a091e33be58a9e5c473d0ad5e9177280b7e415a')
        self.assertEqual(self.metadata_files.metadata['group_gz']['relative_path'],
                         'repodata/010d5d5877f1974802170acb0f278a5966e6469d464c89c3ca7b3658cccd9758'
                         '-comps.xml.gz')

    def test_group(self):
        self.metadata_files.dst_dir = self.repodata_path

        self.metadata_files.parse_repomd()

        self.assertEqual(self.metadata_files.metadata['group']['name'], 'group')
        self.assertEqual(self.metadata_files.metadata['group']['size'], 2268)
        self.assertEqual(self.metadata_files.metadata['group']['timestamp'], 1331832479.68)
        self.assertEqual(self.metadata_files.metadata['group']['checksum']['algorithm'], 'sha256')
        self.assertEqual(self.metadata_files.metadata['group']['checksum']['hex_digest'],
                         '497d2c3f2af57f60a8d289027a091e33be58a9e5c473d0ad5e9177280b7e415a')
        self.assertEqual(self.metadata_files.metadata['group']['relative_path'],
                         'repodata/497d2c3f2af57f60a8d289027a091e33be58a9e5c473d0ad5e9177280b7e415a'
                         '-comps.xml')


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


class TestQueryAuthToken(unittest.TestCase):
    def setUp(self):
        self.qstring = '?foo'
        self.url_modify = RepoURLModifier(query_auth_token=self.qstring[1:])
        self.metadata_files = metadata.MetadataFiles('http://pulpproject.org',
                                                     '/a/b/c',
                                                     DownloaderConfig(),
                                                     self.url_modify)

    def test_repo_url(self):
        self.assertTrue(self.metadata_files.repo_url.endswith(self.qstring))

    # DownloadRequest is already in metadata, so it needs to be mocked in-module
    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.metadata.DownloadRequest', autospec=True)
    def test_download_repomd(self, mock_download_request):
        self.metadata_files.download_repomd()
        self.assertTrue(mock_download_request.call_args[0][0].endswith(self.qstring))

    def test_download_metadata_files(self):
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
        self.assertTrue(requests[0].url.endswith('primary' + self.qstring))
        self.assertTrue(requests[1].url.endswith('pkgtags.sqlite.gz' + self.qstring))


class TestMetadataFiles(unittest.TestCase):
    def setUp(self):
        self.metadata_files = metadata.MetadataFiles('http://pulpproject.org',
                                                     '/a/b/c',
                                                     DownloaderConfig())
        self.working_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.working_dir)

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

    def test_get_metadata_file_bz(self):

        # create the test file
        source_file = os.path.join(self.working_dir, 'foo.bz2')
        compressed_file_handle = bz2.BZ2File(source_file, 'w')
        compressed_file_handle.write('apples')
        compressed_file_handle.close()
        self.metadata_files.metadata['foo'] = {'local_path': source_file}

        # validate it
        handle = self.metadata_files.get_metadata_file_handle('foo')
        data = handle.read()
        self.assertEquals(data, 'apples')
        handle.close()

    def test_get_metadata_file_lzma(self):
        # create the test file
        source_file = os.path.join(self.working_dir, 'foo.xz')
        handle = lzma.LZMAFile(source_file, 'w')
        handle.write('apples')
        handle.close()
        self.metadata_files.metadata['foo'] = {'local_path': source_file}

        # validate it
        handle = self.metadata_files.get_metadata_file_handle('foo')
        data = handle.read()
        self.assertEquals(data, 'apples')
        handle.close()


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
