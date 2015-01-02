import mock
from mock import patch

from pulp.server.db.migrate.models import _import_all_the_way

from pulp_rpm.devel import rpm_support_base


FAKE_DIST_UNITS = [{'files':
                    [{'fileName': 'repomd.xml',
                      'downloadurl': 'http ://fake-url/os/repodata/repomd.xml',
                      'item_type': 'distribution'}],
                    '_id': u'6ec94809-6d4f-48cf-9077-88d003eb284e', 'arch': 'x86_64',
                    'id': 'ks-fake-id'}]

FAKE_DIST_UNITS_MULTIFILE = [{'files':
                              [{'fileName': 'repomd.xml',
                                'downloadurl': 'http ://fake-url/os/repodata/repomd.xml',
                                'item_type': 'distribution'},
                               {'fileName': 'another_file',
                                'downloadurl': 'http ://fake-url/os/another_file',
                                'item_type': 'distribution'}],
                              '_id': u'6ec94809-6d4f-48cf-9077-88d003eb284e', 'arch': 'x86_64',
                              'id': 'ks-fake-id'}]


class MigrationTests(rpm_support_base.PulpRPMTests):
    def test_fix_distribution_units(self):
        migration = _import_all_the_way('pulp_rpm.plugins.migrations.0015_fix_distributor_units')

        mock_collection = mock.MagicMock()
        mock_collection.find.return_value = FAKE_DIST_UNITS
        migration._fix_distribution_units(mock_collection)
        mock_collection.find.assert_called_once_with({'files': {'$exists': True}})
        mock_collection.update.assert_called_once_with(
            {'_id': u'6ec94809-6d4f-48cf-9077-88d003eb284e'},
            {'$set': {'files': []}}, safe=True)

    def test_fix_distribution_units_multifile(self):
        """
        verify that we don't remove files that are OK
        """
        migration = _import_all_the_way('pulp_rpm.plugins.migrations.0015_fix_distributor_units')

        mock_collection = mock.MagicMock()
        mock_collection.find.return_value = FAKE_DIST_UNITS_MULTIFILE
        migration._fix_distribution_units(mock_collection)
        mock_collection.find.assert_called_once_with({'files': {'$exists': True}})
        mock_collection.update.assert_called_once_with(
            {'_id': u'6ec94809-6d4f-48cf-9077-88d003eb284e'},
            {'$set':
                {'files': [{'downloadurl': 'http ://fake-url/os/another_file',
                            'item_type': 'distribution',
                            'fileName': 'another_file'}]}},
            safe=True)

    @patch('os.walk')
    @patch('pulp_rpm.plugins.importers.yum.parse.treeinfo.strip_treeinfo_repomd')
    def test_treeinfo_fix(self, mock_strip_treeinfo, mock_walk):
        mock_walk.return_value = [('/some/path/', [], ['treeinfo', 'file-A'])]
        migration = _import_all_the_way('pulp_rpm.plugins.migrations.0015_fix_distributor_units')
        migration._fix_treeinfo_files('/some/path')
        mock_strip_treeinfo.assert_called_once_with('/some/path/treeinfo')

    @patch('os.walk')
    @patch('pulp_rpm.plugins.importers.yum.parse.treeinfo.strip_treeinfo_repomd')
    def test_treeinfo_fix_dot_treeinfo(self, mock_strip_treeinfo, mock_walk):
        mock_walk.return_value = [('/some/path/', [], ['file-A', '.treeinfo'])]
        migration = _import_all_the_way('pulp_rpm.plugins.migrations.0015_fix_distributor_units')
        migration._fix_treeinfo_files('/some/path')
        mock_strip_treeinfo.assert_called_once_with('/some/path/.treeinfo')
