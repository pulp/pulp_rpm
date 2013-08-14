# -*- coding: utf-8 -*-
#
# Copyright (c) 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

import os
import shutil
import sys
import unittest

import mock
from pulp.plugins.config import PluginCallConfiguration
from pulp.plugins.conduits.repo_publish import RepoPublishConduit
from pulp.server.exceptions import MissingResource
from pulp.plugins.model import AssociatedUnit, Repository, RepositoryGroup

# pulp_rpm/pulp_rpm/plugins/distributors/iso_distributor isn't in the python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)) + "/../../../plugins/distributors/")
from iso_distributor import export_utils, generate_iso
from pulp_rpm.common import constants, ids, models


class TestIsValidPrefix(unittest.TestCase):
    """
    Tests that is_valid_prefix only returns true for strings containing alphanumeric characters,
    dashes, and underscores.
    """
    def test_invalid_prefix(self):
        self.assertFalse(export_utils.is_valid_prefix('prefix#with*special@chars'))

    def test_valid_prefix(self):
        self.assertTrue(export_utils.is_valid_prefix('No-special_chars1'))


class TestCleanupWorkingDir(unittest.TestCase):
    """
    Tests that cleanup_working_dir, which wraps rmtree, calls rmtree correctly and doesn't pass on
    exceptions.
    """
    @mock.patch('shutil.rmtree', autospec=True)
    def test_successful_removal(self, mock_rmtree):
        # Setup
        test_dir = '/test/dir'

        # Test
        export_utils.cleanup_working_dir(test_dir)
        mock_rmtree.assert_called_once_with(test_dir)

    @mock.patch('shutil.rmtree', autospec=True)
    def test_failed_removal(self, mock_rmtree):
        # Setup
        mock_rmtree.side_effect = OSError('boop')

        # Test
        try:
            export_utils.cleanup_working_dir('/somedir')
        except OSError:
            self.fail('cleanup_working_dir should not raise an exception when rmtree fails')


class TestFormLookupKey(unittest.TestCase):
    """
    Tests form_lookup_key in export_utils
    """
    def test_form_lookup_key(self):
        # Setup a fake rpm and the expected return value
        test_rpm = {
            'name': 'test_name',
            'epoch': '1',
            'version': '1.0.2',
            'release': '1',
            'arch': 'noarch',
        }
        expected_key = ('test_name', '1', '1.0.2', '1', 'noarch')

        # Test
        self.assertEqual(expected_key, export_utils.form_lookup_key(test_rpm))

    def test_form_lookup_key_no_epoch(self):
        # Setup a test rpm that doesn't have an epoch. yum assumes an epoch of 0, so we will, too
        test_rpm = {
            'name': 'test_name',
            'epoch': None,
            'version': '1.0.2',
            'release': '1',
            'arch': 'noarch',
        }
        expected_key = ('test_name', '0', '1.0.2', '1', 'noarch')

        # Test
        self.assertEqual(expected_key, export_utils.form_lookup_key(test_rpm))


class TestFormUnitKeyMap(unittest.TestCase):
    """
    Tests form_unit_key_map in export_utils
    """
    def test_form_unit_key_map(self):
        # Setup a list of rpm units and expected keys
        mock_unit1, mock_unit2 = mock.Mock(spec=AssociatedUnit), mock.Mock(spec=AssociatedUnit)
        mock_unit1.unit_key = {
            'name': 'test_name1',
            'epoch': None,
            'version': '1.0.0',
            'release': '1',
            'arch': 'noarch',
        }
        mock_unit2.unit_key = {
            'name': 'test_name2',
            'epoch': '0',
            'version': '1.0.0',
            'release': '1',
            'arch': 'noarch',
        }
        lookup_key1 = ('test_name1', '0', '1.0.0', '1', 'noarch')
        lookup_key2 = ('test_name2', '0', '1.0.0', '1', 'noarch')
        expected_return = {lookup_key1: mock_unit1, lookup_key2: mock_unit2}

        # Test
        self.assertEqual(expected_return, export_utils.form_unit_key_map([mock_unit1, mock_unit2]))


class TestValidateExportConfig(unittest.TestCase):
    """
    Tests for validate_export_config in export_utils
    """
    def setUp(self):
        self.repo_config = {
            constants.PUBLISH_HTTPS_KEYWORD: True,
            constants.PUBLISH_HTTP_KEYWORD: False,
        }
        self.valid_config = PluginCallConfiguration({}, self.repo_config)

    def test_missing_required_key(self):
        # Confirm missing required keys causes validation to fail
        result, msg = export_utils.validate_export_config(PluginCallConfiguration({}, {}))
        self.assertFalse(result)

    def test_required_keys_only(self):
        # Confirm providing only required keys causes a successful validation
        return_value = export_utils.validate_export_config(self.valid_config)
        self.assertEqual(return_value, (True, None))

    def test_non_bool_http_key(self):
        # Confirm including a non-boolean for the publish http keyword fails validation
        self.repo_config[constants.PUBLISH_HTTP_KEYWORD] = 'potato'
        result, msg = export_utils.validate_export_config(PluginCallConfiguration({}, self.repo_config))
        self.assertFalse(result)

    def test_non_bool_https_key(self):
        # Confirm including a non-boolean for the publish https keyword fails validation
        self.repo_config[constants.PUBLISH_HTTPS_KEYWORD] = 'potato'
        result, msg = export_utils.validate_export_config(PluginCallConfiguration({}, self.repo_config))
        self.assertFalse(result)

    def test_invalid_key(self):
        self.repo_config['leek'] = 'garlic'
        result, msg = export_utils.validate_export_config(PluginCallConfiguration({}, self.repo_config))
        self.assertFalse(result)

    @mock.patch('os.path.isdir', autospec=True)
    @mock.patch('os.access', autospec=True)
    def test_full_config(self, mock_access, mock_isdir):
        self.repo_config[constants.SKIP_KEYWORD] = []
        self.repo_config[constants.ISO_PREFIX_KEYWORD] = 'prefix'
        self.repo_config[constants.ISO_SIZE_KEYWORD] = 630
        self.repo_config[constants.EXPORT_DIRECTORY_KEYWORD] = export_dir = '/path/to/dir'
        self.repo_config[constants.START_DATE_KEYWORD] = '2013-07-18T11:22:00'
        self.repo_config[constants.END_DATE_KEYWORD] = '2013-07-18T11:23:00'

        result, msg = export_utils.validate_export_config(PluginCallConfiguration({}, self.repo_config))
        self.assertTrue(result)
        mock_isdir.assert_called_once_with(export_dir)
        self.assertEqual(2, mock_access.call_count)
        self.assertEqual((export_dir, os.R_OK), mock_access.call_args_list[0][0])
        self.assertEqual((export_dir, os.W_OK), mock_access.call_args_list[1][0])

    def test_bad_skip_config(self):
        # Setup
        self.repo_config[constants.SKIP_KEYWORD] = 'not a list'

        # Test that a skip list that isn't a list fails to validate
        result = export_utils.validate_export_config(PluginCallConfiguration({}, self.repo_config))
        self.assertFalse(result[0])

    def test_bad_prefix_config(self):
        # Setup
        self.repo_config[constants.ISO_PREFIX_KEYWORD] = '!@#$%^&'

        # Test that a prefix with invalid characters fails validation
        result = export_utils.validate_export_config(PluginCallConfiguration({}, self.repo_config))
        self.assertFalse(result[0])

    def test_bad_iso_size_config(self):
        # Setup
        self.repo_config[constants.ISO_SIZE_KEYWORD] = -55

        # Test that a prefix with invalid characters fails validation
        result = export_utils.validate_export_config(PluginCallConfiguration({}, self.repo_config))
        self.assertFalse(result[0])

    def test_bad_start_date(self):
        # Setup
        self.repo_config[constants.START_DATE_KEYWORD] = 'malformed date'

        # Test
        result = export_utils.validate_export_config(PluginCallConfiguration({}, self.repo_config))
        self.assertFalse(result[0])

    def test_bad_end_date(self):
        # Setup
        self.repo_config[constants.END_DATE_KEYWORD] = 'malformed date'

        # Test
        result = export_utils.validate_export_config(PluginCallConfiguration({}, self.repo_config))
        self.assertFalse(result[0])

    @mock.patch('os.path.isdir', autospec=True)
    def test_missing_export_dir(self, mock_isdir):
        # Setup
        self.repo_config[constants.EXPORT_DIRECTORY_KEYWORD] = '/directory/not/found'
        mock_isdir.return_value = False

        # Test that if the export directory isn't found, validation fails
        result = export_utils.validate_export_config(PluginCallConfiguration({}, self.repo_config))
        self.assertFalse(result[0])

    @mock.patch('os.access', autospec=True)
    @mock.patch('os.path.isdir', autospec=True)
    def test_unwritable_export_dir(self, mock_isdir, mock_access):
        # Setup
        self.repo_config[constants.EXPORT_DIRECTORY_KEYWORD] = '/some/dir'
        mock_isdir.return_value = True
        mock_access.return_value = False

        # Test that if the export directory isn't writable, validation fails
        result = export_utils.validate_export_config(PluginCallConfiguration({}, self.repo_config))
        self.assertFalse(result[0])


class TestRetrieveRepoConfig(unittest.TestCase):
    """
    Tests for the retrieve_repo_config method in export_utils
    """
    def setUp(self):
        self.repo_config = {
            constants.PUBLISH_HTTPS_KEYWORD: True,
            constants.PUBLISH_HTTP_KEYWORD: False,
        }

        # Dummy repo
        self.repo = Repository('repo_id', working_dir='/working/dir')

        self.get_repo_relative_url = export_utils.get_repo_relative_url
        export_utils.get_repo_relative_url = mock.Mock(return_value='relative/path')
        self.create_date_range_filter = export_utils.create_date_range_filter
        export_utils.create_date_range_filter = mock.Mock(return_value={})

    def tearDown(self):
        export_utils.get_repo_relative_url = self.get_repo_relative_url
        export_utils.create_date_range_filter = self.create_date_range_filter

    def test_without_export_dir(self):
        """
        Test that when there is no export directory in the config, the repo working directory is used
        """
        # Setup
        config = PluginCallConfiguration({}, self.repo_config)

        # Test
        result = export_utils.retrieve_repo_config(self.repo, config)
        result_working_dir, result_date_filter = result
        self.assertEqual(result_working_dir, os.path.join(self.repo.working_dir, 'relative/path'))
        self.assertEqual({}, result_date_filter)
        export_utils.get_repo_relative_url.assert_called_once_with(self.repo.id)
        export_utils.create_date_range_filter.assert_called_once_with(config)

    def test_with_export_dir(self):
        """
        Test that when an export directory is in the configuration, it is used as the working directory
        """
        # Setup
        self.repo_config[constants.EXPORT_DIRECTORY_KEYWORD] = '/some/export/dir'
        expected_working_dir = '/some/export/dir/relative/path'
        config = PluginCallConfiguration({}, self.repo_config)

        # Test
        result = export_utils.retrieve_repo_config(self.repo, config)
        result_working_dir, result_date_filter = result
        self.assertEqual(result_working_dir, expected_working_dir)
        self.assertEqual({}, result_date_filter)
        export_utils.get_repo_relative_url.assert_called_once_with(self.repo.id)
        export_utils.create_date_range_filter.assert_called_once_with(config)


class TestRetrieveGroupExportConfig(unittest.TestCase):
    """
    Tests for the retrieve_group_export_config method in export_utils
    """
    def setUp(self):
        self.repo_config = {
            constants.PUBLISH_HTTPS_KEYWORD: True,
            constants.PUBLISH_HTTP_KEYWORD: False,
        }

        # Dummy repo
        self.repo_group = RepositoryGroup('group_id', '', '', {}, ['repo1', 'repo2'], '/working/dir')

        self.get_repo_relative_url = export_utils.get_repo_relative_url
        export_utils.get_repo_relative_url = mock.Mock(return_value='relative/path')
        self.create_date_range_filter = export_utils.create_date_range_filter
        export_utils.create_date_range_filter = mock.Mock(return_value={})
        self.is_rpm_repo = export_utils.is_rpm_repo
        export_utils.is_rpm_repo = mock.Mock(return_value=True)

    def tearDown(self):
        export_utils.get_repo_relative_url = self.get_repo_relative_url
        export_utils.create_date_range_filter = self.create_date_range_filter

    def test_without_export_dir(self):
        """
        Test configuration retrieval when there is no export directory in the config. This should use
        the repo group working directory as the working directory.
        """
        # Setup
        config = PluginCallConfiguration({}, self.repo_config)

        # Test
        rpm_repos, date_filter = export_utils.retrieve_group_export_config(self.repo_group, config)
        self.assertEqual(2, len(rpm_repos))
        for repo_id, working_dir in rpm_repos:
            self.assertEqual('/working/dir/relative/path', working_dir)
            self.assertTrue(repo_id in self.repo_group.repo_ids)
        self.assertEqual({}, date_filter)

    def test_with_export_dir(self):
        """
        Test configuration retrieval when there is an export directory in the config. This should be
        used as the working directory
        """
        # Setup
        self.repo_config[constants.EXPORT_DIRECTORY_KEYWORD] = '/export/dir'
        config = PluginCallConfiguration({}, self.repo_config)

        # Test
        rpm_repos, date_filter = export_utils.retrieve_group_export_config(self.repo_group, config)
        self.assertEqual(2, len(rpm_repos))
        for repo_id, working_dir in rpm_repos:
            self.assertEqual('/export/dir/relative/path', working_dir)
            self.assertTrue(repo_id in self.repo_group.repo_ids)
        self.assertEqual({}, date_filter)

    def test_not_rpm_repo(self):
        """
        Test that when the repo group contains a repo that is not an rpm repository, it is not returned
        """
        # Setup
        config = PluginCallConfiguration({}, self.repo_config)
        export_utils.is_rpm_repo.return_value = False

        # Test
        rpm_repos, date_filter = export_utils.retrieve_group_export_config(self.repo_group, config)
        self.assertEqual(0, len(rpm_repos))
        self.assertEqual({}, date_filter)


class TestGetRepoRelativeUrl(unittest.TestCase):
    """
    Tests for export_utils.get_repo_relative_url
    """
    @mock.patch('pulp.server.managers.repo.distributor.RepoDistributorManager.get_distributor',
                autospec=True)
    def test_get_repo_relative_url(self, mock_get_distributor):
        """
        Test that the relative url is successfully extracted from the yum distributor if it exists
        """
        # Setup
        mock_get_distributor.return_value = {'config': {'relative_url': 'relative/url'}}

        # Test
        result = export_utils.get_repo_relative_url('repo_id')
        self.assertEqual('repo_id', mock_get_distributor.call_args[0][1])
        self.assertEqual(ids.TYPE_ID_DISTRIBUTOR_YUM, mock_get_distributor.call_args[0][2])
        self.assertEqual(result, 'relative/url')

    @mock.patch('pulp.server.managers.repo.distributor.RepoDistributorManager.get_distributor',
                autospec=True, )
    def test_missing_resource(self, mock_get_distributor):
        """
        Test that when the manager fails to find the yum distributor for a repo, the repo id is used
        as a relative url instead.
        """
        # Setup
        mock_get_distributor.side_effect = MissingResource('boop')

        # Test
        result = export_utils.get_repo_relative_url('repo_id')
        self.assertEqual(result, 'repo_id')

    @mock.patch('pulp.server.managers.repo.distributor.RepoDistributorManager.get_distributor',
                autospec=True, )
    def test_key_error(self, mock_get_distributor):
        """
        Test that when the manager fails to find the relative url in the config due to a key error,
        the repo id is used instead.
        """
        # Setup
        mock_get_distributor.side_effect = KeyError('boop')

        # Test
        result = export_utils.get_repo_relative_url('repo_id')
        self.assertEqual(result, 'repo_id')


class TestIsRpmRepo(unittest.TestCase):
    """
    Tests for export_utils.is_rpm_repo
    """
    @mock.patch('pulp.server.managers.repo.query.RepoQueryManager.get_repository', autospec=True)
    def test_rpm_repo(self, mock_get_distributor):
        """
        Test retrieving a valid repository and getting its type from the notes
        """
        # Setup
        mock_get_distributor.return_value = {'notes': {'_repo-type': 'rpm-repo'}}

        # Test
        self.assertTrue(export_utils.is_rpm_repo('repo_id'))
        self.assertEqual('repo_id', mock_get_distributor.call_args[0][1])

    @mock.patch('pulp.server.managers.repo.query.RepoQueryManager.get_repository', autospec=True)
    def test_invalid_repo(self, mock_get_distributor):
        """
        Test that is_rpm_repo handles non-existent repository ids gracefully by returning False
        instead of raising a MissingResource exception
        """
        # Setup
        mock_get_distributor.side_effect = MissingResource('this repo_id is non-existent')

        # Test
        self.assertFalse(export_utils.is_rpm_repo('repo_id'))
        self.assertEqual('repo_id', mock_get_distributor.call_args[0][1])

    @mock.patch('pulp.server.managers.repo.query.RepoQueryManager.get_repository', autospec=True)
    def test_missing_type_repo(self, mock_get_distributor):
        """
        An edge case, but if a repo is missing a _repo-type note, return False instead of raising
        a KeyError
        """
        # Setup
        mock_get_distributor.side_effect = KeyError('boop')

        # Test
        self.assertFalse(export_utils.is_rpm_repo('repo_id'))
        self.assertEqual('repo_id', mock_get_distributor.call_args[0][1])


class TestSetProgress(unittest.TestCase):
    """
    Tests for the set_progress method in export_utils
    """
    def test_set_progress(self):
        # Setup
        mock_progress_callback = mock.MagicMock()

        # Test that the progress callback is called with the correct arguments
        export_utils.set_progress('id', 'status', mock_progress_callback)
        mock_progress_callback.assert_called_once_with('id', 'status')

    def test_none_progress(self):
        # Test that if progress_callback is None, an exception isn't raised
        try:
            export_utils.set_progress('id', 'status', None)
        except AttributeError:
            self.fail('set_progress should not raise an AttributeError')


class TestCreateDateRangeFilter(unittest.TestCase):
    """
    Tests for the create_date_range_filter method in export_utils
    """
    def setUp(self):
        self.repo_config = {
            constants.PUBLISH_HTTPS_KEYWORD: True,
            constants.PUBLISH_HTTP_KEYWORD: False,
        }
        self.test_date = '2010-01-01 12:00:00'

    def test_no_filter(self):
        # Test calling create_date_range_filter with no dates in the configuration
        date = export_utils.create_date_range_filter(PluginCallConfiguration({}, self.repo_config))
        self.assertTrue(date is None)

    def test_start_date_only(self):
        # Set up a configuration with a start date, and the expected return
        self.repo_config[constants.START_DATE_KEYWORD] = self.test_date
        config = PluginCallConfiguration({}, self.repo_config)
        expected_filter = {export_utils.ASSOCIATED_UNIT_DATE_KEYWORD: {'$gte': self.test_date}}

        # Test
        date_filter = export_utils.create_date_range_filter(config)
        self.assertEqual(expected_filter, date_filter)

    def test_end_date_only(self):
        # Set up a configuration with an end date, and the expected return
        self.repo_config[constants.END_DATE_KEYWORD] = self.test_date
        config = PluginCallConfiguration({}, self.repo_config)
        expected_filter = {export_utils.ASSOCIATED_UNIT_DATE_KEYWORD: {'$lte': self.test_date}}

        # Test
        date_filter = export_utils.create_date_range_filter(config)
        self.assertEqual(expected_filter, date_filter)

    def test_start_and_end_date(self):
        # Set up a configuration with both a start date and an end date.
        self.repo_config[constants.START_DATE_KEYWORD] = self.test_date
        self.repo_config[constants.END_DATE_KEYWORD] = self.test_date
        config = PluginCallConfiguration({}, self.repo_config)
        expected_filter = {export_utils.ASSOCIATED_UNIT_DATE_KEYWORD: {'$gte': self.test_date,
                                                                       '$lte': self.test_date}}

        # Test
        date_filter = export_utils.create_date_range_filter(config)
        self.assertEqual(expected_filter, date_filter)


class TestExportRpm(unittest.TestCase):
    """
    Tests export_rpm in export_utils
    """
    def setUp(self):
        test_unit1 = AssociatedUnit(ids.TYPE_ID_RPM, None, None, '/fake/rpm1', None, None, None, None)
        test_unit2 = AssociatedUnit(ids.TYPE_ID_RPM, None, None, '/fake/rpm2', None, None, None, None)
        self.rpm_list = [test_unit1, test_unit2]

    @mock.patch('pulp_rpm.yum_plugin.util.get_relpath_from_unit', autospec=True)
    @mock.patch('pulp_rpm.yum_plugin.util.create_copy', autospec=True)
    def test_unsuccessful_copy(self, mock_copy, mock_get_relpath):
        # Set up the mock of create_copy to return False
        mock_copy.return_value = False
        mock_get_relpath.return_value = 'relative/path'

        # Test that both packages failed
        summary, details = export_utils.export_rpm('/fake/working/dir', self.rpm_list, None)
        self.assertEqual(2, mock_get_relpath.call_count)
        self.assertEqual(2, summary['num_package_units_errors'])

    @mock.patch('pulp_rpm.yum_plugin.util.get_relpath_from_unit', autospec=True)
    @mock.patch('pulp_rpm.yum_plugin.util.create_copy', autospec=True)
    @mock.patch('os.path.exists', autospec=True)
    def test_successful_copy(self, mock_exists, mock_copy, mock_rel_path):
        # Setup
        mock_exists.return_value = True
        mock_rel_path.return_value = 'fake_path'
        mock_copy.return_value = True

        # Test that create_copy was called with the source path and the working dir joined with relpath
        summary, details = export_utils.export_rpm('/working/dir', self.rpm_list, None)
        self.assertEqual(('/fake/rpm1', '/working/dir/fake_path',), mock_copy.call_args_list[0][0])
        self.assertEqual(('/fake/rpm2', '/working/dir/fake_path',), mock_copy.call_args_list[1][0])
        self.assertEqual(2, summary['num_package_units_exported'])


class TestExportErrata(unittest.TestCase):
    """
    Tests export_errata in export_utils
    """
    def test_no_errata(self):
        # Setup
        updateinfo_path = export_utils.export_errata('/fake', [], [])

        # Test
        self.assertTrue(updateinfo_path is None)

    @mock.patch('pulp_rpm.yum_plugin.updateinfo.updateinfo', autospec=True, return_value='/path')
    def test_successful_export(self, mock_updateinfo):
        # Setup some list to hand to updateinfo
        test_errata_list = ['not', 'actually', 'errata']

        # Test that updateinfo is called with the errata unit
        update_info = export_utils.export_errata('/fake', test_errata_list)
        self.assertTrue((test_errata_list, '/fake'), mock_updateinfo.call_args[0])
        self.assertEqual('/path', update_info)


class TestExportDistribution(unittest.TestCase):
    """
    Tests export_distribution in export_utils
    """
    @mock.patch('pulp_rpm.yum_plugin.util.create_copy', autospec=True)
    def test_successful_export(self, mock_copy):
        # Setup a distribution unit
        metadata = {'files': [{'relativepath': 'unit'}]}
        distribution_units = [AssociatedUnit(ids.TYPE_ID_DISTRO, None, metadata, '/fake/path', None,
                                             None, None, None)]

        # Test that the unit is successfully exported
        summary, details = export_utils.export_distribution('/working/dir', distribution_units)
        self.assertEqual(('/fake/path/unit', '/working/dir/unit'), mock_copy.call_args[0])
        self.assertEqual(1, summary['num_distribution_units_exported'])

    @mock.patch('pulp_rpm.yum_plugin.util.create_copy', autospec=True, return_value=False)
    def test_failed_copy(self, mock_copy):
        # Set up a distribution unit
        metadata = {'files': [{'relativepath': 'unit'}]}
        distribution_unit = [AssociatedUnit(ids.TYPE_ID_DISTRO, None, metadata, '/fake/path', None,
                                            None, None, None)]

        # Test that when create_copy fails, units are not exported
        summary, details = export_utils.export_distribution('/working/dir', distribution_unit)
        mock_copy.assert_called_once_with('/fake/path/unit', '/working/dir/unit')
        self.assertEqual(0, summary['num_distribution_units_exported'])

    def test_bad_metadata(self):
        # Set up a distribution unit is no metadata
        distribution_unit = [AssociatedUnit(ids.TYPE_ID_DISTRO, None, {}, None, None, None, None, None)]

        # Without the metadata, the unit should not be exported
        summary, details = export_utils.export_distribution('/working/dir', distribution_unit)
        self.assertEqual(0, summary['num_distribution_units_exported'])


class TestExportPackageGroupsAndCats(unittest.TestCase):
    """
    Tests export_package_groups_and_cats in export_utils. This method just generates an xml file using
    a yum distributor utility.
    """
    @mock.patch('pulp_rpm.yum_plugin.comps_util.write_comps_xml', autospec=True)
    def test_export_groups_and_cats(self, mock_comps_xml):
        # Set up a group and category unit to be exported
        group_unit = AssociatedUnit(ids.TYPE_ID_PKG_GROUP, None, None, None, None, None, None, None)
        cat_unit = AssociatedUnit(ids.TYPE_ID_PKG_CATEGORY, None, None, None, None, None, None, None)

        # Test that the groups and categories were sorted correctly and comps_xml was called
        result = export_utils.export_package_groups_and_cats('/working/dir', [group_unit, cat_unit])
        self.assertEqual(1, result[1]['num_package_groups_exported'])
        self.assertEqual(1, result[1]['num_package_categories_exported'])
        mock_comps_xml.assert_called_once_with('/working/dir', [group_unit], [cat_unit])

    @mock.patch('pulp_rpm.yum_plugin.comps_util.write_comps_xml', autospec=True)
    def test_export_groups(self, mock_comps_xml):
        # Set up just a group unit
        group_unit = [AssociatedUnit(ids.TYPE_ID_PKG_GROUP, None, None, None, None, None, None, None)]

        # Export a list of units that only contains groups
        result = export_utils.export_package_groups_and_cats('/working/dir', group_unit)
        self.assertEqual(1, result[1]['num_package_groups_exported'])
        self.assertEqual(0, result[1]['num_package_categories_exported'])
        mock_comps_xml.assert_called_once_with('/working/dir', group_unit, [])


class TestExportCompleteRepo(unittest.TestCase):
    """
    Tests export_complete_repo in export_utils, which exports all units associated with a repository
    and generates the expected metadata. It simply glues all the type exporters together
    """
    def setUp(self):
        self.export_rpm = export_utils.export_rpm
        self.get_rpm_units = export_utils.get_rpm_units
        self.export_groups = export_utils.export_package_groups_and_cats
        self.export_distro = export_utils.export_distribution
        self.export_errata = export_utils.export_errata
        export_utils.export_rpm = mock.Mock(return_value=({}, {}))
        export_utils.get_rpm_units = mock.Mock()
        export_utils.export_package_groups_and_cats = mock.Mock()
        export_utils.export_distribution = mock.Mock()
        export_utils.export_errata = mock.Mock()

    def tearDown(self):
        export_utils.export_rpm = self.export_rpm
        export_utils.export_package_groups_and_cats = self.export_groups
        export_utils.export_distribution = self.export_distro
        export_utils.export_errata = self.export_errata
        export_utils.get_rpm_units = self.get_rpm_units

    @mock.patch('pulp_rpm.yum_plugin.metadata.generate_yum_metadata', autospec=True)
    def test_skip_list(self, mock_metadata):
        """
        Test that unit types in the skip list are actually skipped
        """
        # Setup
        skip_list = [ids.TYPE_ID_RPM, ids.TYPE_ID_PKG_GROUP, ids.TYPE_ID_DISTRO, ids.TYPE_ID_ERRATA]
        config = PluginCallConfiguration({}, {constants.SKIP_KEYWORD: skip_list})
        mock_conduit = mock.Mock(spec=RepoPublishConduit)
        mock_metadata.return_value = (None, None)

        # Test
        export_utils.export_complete_repo('repo_id', '/working/dir', mock_conduit, config, None)
        self.assertEqual(0, export_utils.export_rpm.call_count)
        self.assertEqual(0, export_utils.export_package_groups_and_cats.call_count)
        self.assertEqual(0, export_utils.export_distribution.call_count)
        self.assertEqual(0, export_utils.export_errata.call_count)

    @mock.patch('pulp_rpm.yum_plugin.metadata.generate_yum_metadata', autospec=True)
    def test_export_complete_repo(self, mock_metadata):
        """
        Test that export_complete_repo calls all the correct helper methods
        """
        # Setup
        config = PluginCallConfiguration({}, {})
        mock_conduit = mock.Mock(spec=RepoPublishConduit)
        mock_metadata.return_value = (None, None)
        export_utils.export_rpm.return_value = ({}, {})
        export_utils.export_package_groups_and_cats.return_value = (None, {})

        # Test
        summary, details = export_utils.export_complete_repo('repo_id', '/working/dir', mock_conduit,
                                                             config, None)
        self.assertEqual(1, export_utils.export_rpm.call_count)
        self.assertEqual(1, export_utils.export_package_groups_and_cats.call_count)
        self.assertEqual(1, export_utils.export_distribution.call_count)
        self.assertEqual(1, export_utils.export_errata.call_count)
        self.assertEqual({}, summary)
        self.assertEqual({'errors': {}}, details)

    @mock.patch('pulp_rpm.yum_plugin.metadata.generate_yum_metadata', autospec=True)
    def test_metadata_errors(self, mock_metadata):
        """
        Test that metadata errors from the call to metadata.generate_yum_metadata are placed in the
        details dictionary
        """
        # Setup
        skip_list = [ids.TYPE_ID_RPM, ids.TYPE_ID_PKG_GROUP, ids.TYPE_ID_DISTRO, ids.TYPE_ID_ERRATA]
        config = PluginCallConfiguration({}, {constants.SKIP_KEYWORD: skip_list})
        mock_conduit = mock.Mock(spec=RepoPublishConduit)
        mock_metadata.return_value = (None, ['error'])

        # Test
        summary, details = export_utils.export_complete_repo('repo_id', '/working/dir', mock_conduit,
                                                             config, None)
        self.assertEqual({}, summary)
        self.assertEqual({'errors': {'metadata_errors': ['error']}}, details)


class TestExportIncrementalContent(unittest.TestCase):
    """
    Tests exporting an incremental for a repository, which means the rpm packages (and their metadata
    as JSON) associated with the repo in the given date range, as well as the errata as JSON
    """
    def setUp(self):
        self.export_rpm = export_utils.export_rpm
        self.export_errata = export_utils.export_errata
        self.export_rpm_json = export_utils.export_rpm_json
        self.export_errata_json = export_utils.export_errata_json
        export_utils.export_rpm = mock.Mock(return_value=({}, {}))
        export_utils.export_errata = mock.Mock()
        export_utils.export_rpm_json = mock.Mock()
        export_utils.export_errata_json = mock.Mock()

    def tearDown(self):
        export_utils.export_rpm = self.export_rpm
        export_utils.export_errata = self.export_errata
        export_utils.export_rpm_json = self.export_rpm_json
        export_utils.export_errata_json = self.export_errata_json

    def test_export_incremental(self):
        # Setup
        mock_conduit = mock.Mock(spec=RepoPublishConduit)
        mock_conduit.get_units.return_value = ['unit']
        expected_units = ['unit', 'unit', 'unit']

        # Test
        export_utils.export_incremental_content('/working/dir', mock_conduit, {'fake': 'filter'})

        # Confirm the conduit was called for each content type
        self.assertEqual(4, mock_conduit.get_units.call_count)
        call_list = mock_conduit.get_units.call_args_list
        self.assertEqual([ids.TYPE_ID_RPM], call_list[0][1]['criteria'].type_ids)
        self.assertEqual([ids.TYPE_ID_SRPM], call_list[1][1]['criteria'].type_ids)
        self.assertEqual([ids.TYPE_ID_DRPM], call_list[2][1]['criteria'].type_ids)
        self.assertEqual([ids.TYPE_ID_ERRATA], call_list[3][1]['criteria'].type_ids)

        # Test that each helper method was called correctly
        export_utils.export_rpm.assert_called_once_with('/working/dir', expected_units, None)
        export_utils.export_rpm_json.assert_called_once_with('/working/dir/rpm_json', expected_units)
        export_utils.export_errata_json.assert_called_once_with('/working/dir/errata_json', ['unit'],
                                                                None)


class TestExportRpmJson(unittest.TestCase):
    """
    Tests export_rpm_json in export_utils
    """
    @mock.patch('os.makedirs', autospec=True)
    @mock.patch('os.path.isdir', autospec=True)
    def test_working_dir_missing(self, mock_isdir, mock_makedirs):
        """
        Test that when the working directory does not currently exist, it is created
        """
        # Setup
        working_dir = '/some/working/dir'
        mock_isdir.return_value = False

        # Test
        export_utils.export_rpm_json(working_dir, [])
        mock_isdir.assert_called_once_with(working_dir)
        mock_makedirs.assert_called_once_with(working_dir)

    @mock.patch('json.dump', autospec=True)
    @mock.patch('__builtin__.open', autospec=True)
    @mock.patch('os.makedirs', autospec=True)
    @mock.patch('os.path.isdir', autospec=True)
    def test_export_rpm_json(self, mock_isdir, mock_makedirs, mock_open, mock_dump):
        """
        Test that rpm metadata is correctly exported as JSON documents
        """
        # Setup
        metadata = {'repodata': None, 'key': 'value', '_removed_key': 'removed_value'}
        rpm1_key = {'name': 'test1', 'version': '1.0', 'release': '1', 'arch': 'noarch'}
        rpm2_key = {'name': 'test2', 'version': '1.0', 'release': '1', 'arch': 'noarch'}
        rpm1 = AssociatedUnit(ids.TYPE_ID_RPM, rpm1_key, metadata.copy(), None, None, None, None, None)
        rpm2 = AssociatedUnit(ids.TYPE_ID_RPM, rpm2_key, metadata.copy(), None, None, None, None, None)
        rpm_units = [rpm1, rpm2]
        expected_paths = ['/working/dir/test1-1.0-1.noarch.json', '/working/dir/test2-1.0-1.noarch.json']

        # Test
        export_utils.export_rpm_json('/working/dir', rpm_units)
        mock_isdir.assert_called_once_with('/working/dir')
        self.assertEqual(0, mock_makedirs.call_count)
        self.assertEqual(2, mock_open.call_count)
        self.assertEqual(2, mock_dump.call_count)

        self.assertEqual((expected_paths[0], 'w'), mock_open.call_args_list[0][0])
        self.assertEqual((expected_paths[1], 'w'), mock_open.call_args_list[1][0])

        # Expected result is that repodata and anything with a leading _ is removed from the metadata
        metadata.pop('_removed_key')
        metadata.pop('repodata')
        expected_dict1 = {'unit_key': rpm1_key, 'unit_metadata': metadata}
        expected_dict2 = {'unit_key': rpm2_key, 'unit_metadata': metadata}
        self.assertEqual(expected_dict1, mock_dump.call_args_list[0][0][0])
        self.assertEqual(expected_dict2, mock_dump.call_args_list[1][0][0])


class TestExportErrataJson(unittest.TestCase):
    """
    Tests export_errata_json in export_utils
    """
    @mock.patch('os.makedirs', autospec=True)
    @mock.patch('os.path.isdir', autospec=True)
    def test_working_dir_missing(self, mock_isdir, mock_makedirs):
        """
        Test that when the working directory does not currently exist, it is created
        """
        # Setup
        working_dir = '/some/working/dir'
        mock_isdir.return_value = False

        # Test
        export_utils.export_errata_json(working_dir, [])
        mock_isdir.assert_called_once_with(working_dir)
        mock_makedirs.assert_called_once_with(working_dir)

    @mock.patch('json.dump', autospec=True)
    @mock.patch('__builtin__.open', autospec=True)
    @mock.patch('os.makedirs', autospec=True)
    @mock.patch('os.path.isdir', autospec=True)
    def test_export_errata_json(self, mock_isdir, mock_makedirs, mock_open, mock_dump):
        """
        Test that errata units are correctly exported as JSON documents
        """
        # Setup
        unit_key = {'id': 'RHEA-8675309'}
        unit_metadata = {'key': 'value', '_to_remove': 'value2'}
        errata = AssociatedUnit(ids.TYPE_ID_ERRATA, unit_key, unit_metadata.copy(), None, None,
                                None, None, None)
        unit_metadata.pop('_to_remove')
        expected_dict = {'unit_key': unit_key, 'unit_metadata': unit_metadata}
        expected_path = '/working/dir/RHEA-8675309.json'

        # Test
        export_utils.export_errata_json('/working/dir', [errata])
        mock_isdir.assert_called_once_with('/working/dir')
        self.assertEqual(0, mock_makedirs.call_count)
        self.assertEqual(1, mock_open.call_count)
        self.assertEqual(1, mock_dump.call_count)
        mock_open.assert_called_once_with(expected_path, 'w')
        self.assertEqual(expected_dict, mock_dump.call_args[0][0])


class TestGetRpmUnits(unittest.TestCase):
    def test_get_rpm_units_skip(self):
        """
        Test that when rpm types are in the skip list, they are actually skipped
        """
        # Setup
        mock_conduit = mock.Mock(spec=RepoPublishConduit)
        skip_list = (ids.TYPE_ID_RPM, ids.TYPE_ID_SRPM, ids.TYPE_ID_DRPM)

        # Test
        export_utils.get_rpm_units(mock_conduit, skip_list)
        self.assertEqual(0, mock_conduit.get_units.call_count)

    def test_get_rpm_units(self):
        """
        Test that the conduit is called for each type id
        """
        # Setup
        mock_conduit = mock.Mock(spec=RepoPublishConduit)
        mock_conduit.get_units.return_value = ['unit']

        # Test
        rpm_units = export_utils.get_rpm_units(mock_conduit)
        call_list = mock_conduit.get_units.call_args_list
        self.assertEqual(3, len(rpm_units))
        self.assertEqual(3, mock_conduit.get_units.call_count)
        self.assertEqual([models.RPM.TYPE], call_list[0][1]['criteria'].type_ids)
        self.assertEqual([models.SRPM.TYPE], call_list[1][1]['criteria'].type_ids)
        self.assertEqual([models.DRPM.TYPE], call_list[2][1]['criteria'].type_ids)


class TestPublishIsos(unittest.TestCase):
    def setUp(self):
        """
        Mock out everything so nothing is actually written or removed
        """
        self.create_iso = generate_iso.create_iso
        self.isdir = os.path.isdir
        self.makedirs = os.makedirs
        self.rmtree = shutil.rmtree
        self.symlink = os.symlink
        self.walk = os.walk

        generate_iso.create_iso = mock.Mock()
        os.path.isdir = mock.Mock(spec=os.path.isdir)
        os.makedirs = mock.Mock(spec=os.makedirs)
        shutil.rmtree = mock.Mock(spec=shutil.rmtree)
        os.symlink = mock.Mock(spec=os.symlink)
        os.walk = mock.Mock(spec=os.walk, return_value=[(None, [], [])])

    def tearDown(self):
        generate_iso.create_iso = self.create_iso
        os.path.isdir = self.isdir
        os.makedirs = self.makedirs
        shutil.rmtree = self.rmtree
        os.symlink = self.symlink
        os.walk = self.walk

    def test_make_https_dir(self):
        """
        Tests the the https publishing directory is created by publish_isos if it does not exist
        """
        # Setup
        os.path.isdir.return_value = False

        # Confirm that when https_dir is not None and the directory doesn't exist, it is created
        export_utils.publish_isos('/working/dir', 'prefix', https_dir='/https/dir')
        os.makedirs.assert_called_once_with('/https/dir')

    def test_make_http_dir(self):
        """
        Tests the the http publishing directory is created by publish_isos if it does not exist
        """
        # Setup
        os.path.isdir.return_value = False

        # Confirm that when https_dir is not None and the directory doesn't exist, it is created
        export_utils.publish_isos('/working/dir', 'prefix', http_dir='/http/dir')
        os.makedirs.assert_called_once_with('/http/dir')

    def test_removing_dirs(self):
        """
        Tests that publish_isos cleans out all the directories in the working directory except the ISOs.
        Since storing stuff in the working directory is bad form and should eventually change, this
        """
        # Setup
        os.walk.return_value = [('/root', ['dir1', 'dir2'], [])]

        # Test that for each directory, rmtree is called
        export_utils.publish_isos('/working/dir', 'prefix')
        self.assertEqual(2, shutil.rmtree.call_count)
        self.assertEqual('/root/dir1', shutil.rmtree.call_args_list[0][0][0])
        self.assertEqual('/root/dir2', shutil.rmtree.call_args_list[1][0][0])

    def test_linking_https_iso_images(self):
        """
        Tests that each file in the working directory (after it is cleaned up) is symlinked to the https
        publishing directory
        """
        # Setup
        os.walk.return_value = [('/root', [], ['file1', 'file2'])]
        expected_call1 = ('/root/file1', '/https/dir/file1')
        expected_call2 = ('/root/file2', '/https/dir/file2')

        # Test that for each file, os.symlink is called correctly
        export_utils.publish_isos('/working/dir', 'prefix', https_dir='/https/dir')
        self.assertEqual(2, os.symlink.call_count)
        self.assertEqual(expected_call1, os.symlink.call_args_list[0][0])
        self.assertEqual(expected_call2, os.symlink.call_args_list[1][0])

    def test_linking_http_iso_images(self):
        """
        Tests that each file in the working directory (after it is cleaned up) is symlinked to the http
        publishing directory
        """
        # Setup
        os.walk.return_value = [('/root', [], ['file1', 'file2'])]
        expected_call1 = ('/root/file1', '/http/dir/file1')
        expected_call2 = ('/root/file2', '/http/dir/file2')

        # Test that for each file, os.symlink is called correctly
        export_utils.publish_isos('/working/dir', 'prefix', http_dir='/http/dir')
        self.assertEqual(2, os.symlink.call_count)
        self.assertEqual(expected_call1, os.symlink.call_args_list[0][0])
        self.assertEqual(expected_call2, os.symlink.call_args_list[1][0])
