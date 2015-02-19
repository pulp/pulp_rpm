import shutil
import tempfile
import unittest
import os

import mock
from pulp.server.exceptions import PulpDataException
from pulp.plugins.model import RepositoryGroup
from pulp.plugins.config import PluginCallConfiguration

from pulp_rpm.plugins.distributors.export_distributor import export_utils
from pulp_rpm.plugins.distributors.export_distributor.groupdistributor import GroupISODistributor, \
    entry_point
from pulp_rpm.common.ids import (TYPE_ID_DISTRO, TYPE_ID_PKG_GROUP, TYPE_ID_ERRATA, TYPE_ID_DRPM,
                                 TYPE_ID_SRPM, TYPE_ID_RPM, TYPE_ID_PKG_CATEGORY,
                                 TYPE_ID_DISTRIBUTOR_GROUP_EXPORT)


class TestEntryPoint(unittest.TestCase):
    def test_entry_point(self):
        distributor, config = entry_point()
        self.assertEquals(distributor, GroupISODistributor)


class TestGroupISODistributor(unittest.TestCase):
    """
    Tests the metadata and validate_config methods for GroupISODistributor
    """

    def setUp(self):
        self.working_dir = tempfile.mkdtemp()
        self.repo = RepositoryGroup('test', 'foo', 'bar', {}, ['zoo', 'zoo2'])
        self.repo.working_dir = self.working_dir
        self.config = PluginCallConfiguration(None, None)
        self.conduit = mock.Mock()

    def tearDown(self):
        shutil.rmtree(self.working_dir)
        self.distributor = None

    def test_metadata(self):
        metadata = GroupISODistributor.metadata()
        expected_types = [TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM, TYPE_ID_ERRATA,
                          TYPE_ID_DISTRO, TYPE_ID_PKG_CATEGORY, TYPE_ID_PKG_GROUP]
        self.assertEquals(metadata['id'], TYPE_ID_DISTRIBUTOR_GROUP_EXPORT)
        self.assertEqual(set(expected_types), set(metadata['types']))

    def test_validate_config(self):
        # Setup
        validate_config = export_utils.validate_export_config
        export_utils.validate_export_config = mock.MagicMock()
        distributor = GroupISODistributor()

        # All validate_config should do is hand the config argument to the export_utils validator
        distributor.validate_config(None, 'config', None)
        export_utils.validate_export_config.assert_called_once_with('config')

        # Clean up
        export_utils.validate_export_config = validate_config

    @mock.patch('pulp_rpm.plugins.distributors.export_distributor.groupdistributor.'
                'ExportRepoGroupPublisher')
    @mock.patch(
        'pulp_rpm.plugins.distributors.export_distributor.export_utils.validate_export_config')
    def test_publish_group(self, mock_validate, export_publisher):
        mock_validate.return_value = (True, None)
        distributor = GroupISODistributor()
        export_publisher.return_value = mock.Mock()
        export_publisher.return_value.publish.return_value = 'foo'

        self.assertEquals('foo', distributor.publish_group(self.repo, self.conduit, self.config))

    @mock.patch(
        'pulp_rpm.plugins.distributors.export_distributor.export_utils.validate_export_config')
    def test_publish_repo_invalid_config(self, mock_validate):
        mock_validate.return_value = (False, 'bar')
        distributor = GroupISODistributor()

        self.assertRaises(PulpDataException, distributor.publish_group, self.repo, self.conduit,
                          self.config)

    def test_cancel_publish_repo(self):
        """
        Test cancel_publish_repo, which is not currently fully supported
        """
        distributor = GroupISODistributor()
        distributor._publisher = mock.Mock()

        distributor.cancel_publish_repo()

        self.assertTrue(distributor._publisher.cancel.called)

    @mock.patch('pulp_rpm.plugins.distributors.export_distributor.groupdistributor.configuration')
    def test_distributor_removed(self, mock_configuration):
        master_dir = os.path.join(self.working_dir, 'master')
        http_dir = os.path.join(self.working_dir, 'http')
        https_dir = os.path.join(self.working_dir, 'https')
        repo_working_dir = os.path.join(self.working_dir, 'repodir')
        self.repo.working_dir = repo_working_dir

        mock_configuration.get_master_publish_dir.return_value = master_dir
        mock_configuration.HTTP_EXPORT_GROUP_DIR = http_dir
        mock_configuration.HTTPS_EXPORT_GROUP_DIR = https_dir
        http_dir = os.path.join(http_dir, self.repo.id)
        https_dir = os.path.join(https_dir, self.repo.id)
        os.makedirs(http_dir)
        os.makedirs(https_dir)
        os.makedirs(master_dir)
        os.makedirs(repo_working_dir)

        distributor = GroupISODistributor()
        distributor.distributor_removed(self.repo, self.config)
        self.assertFalse(os.path.exists(http_dir))
        self.assertFalse(os.path.exists(https_dir))
        self.assertFalse(os.path.exists(master_dir))
