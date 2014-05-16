import os
import shutil
import tempfile
import unittest

import mock
from pulp.devel.unit.util import touch
from pulp.plugins.model import Repository
from pulp.plugins.config import PluginCallConfiguration
from pulp.plugins.conduits.repo_publish import RepoPublishConduit
from pulp.server.exceptions import PulpDataException

from pulp_rpm.plugins.distributors.export_distributor import export_utils
from pulp_rpm.plugins.distributors.export_distributor.distributor import ISODistributor, entry_point
from pulp_rpm.common.ids import (TYPE_ID_DISTRO, TYPE_ID_PKG_GROUP, TYPE_ID_ERRATA, TYPE_ID_DRPM,
                                 TYPE_ID_SRPM, TYPE_ID_RPM, TYPE_ID_PKG_CATEGORY,
                                 TYPE_ID_DISTRIBUTOR_EXPORT)


class TestEntryPoint(unittest.TestCase):

    def test_entry_point(self):
        distributor, config = entry_point()
        self.assertEquals(distributor, ISODistributor)


class TestISODistributor(unittest.TestCase):

    def setUp(self):
        self.working_dir = tempfile.mkdtemp()
        self.repo = Repository('test')
        self.repo.working_dir = self.working_dir
        self.config = PluginCallConfiguration(None, None)
        self.conduit = RepoPublishConduit(self.repo.id, TYPE_ID_DISTRIBUTOR_EXPORT)

    def tearDown(self):
        shutil.rmtree(self.working_dir)
        self.distributor = None

    def test_metadata(self):
        """
        Test the overridden metadata method in ISODistributor
        """
        metadata = ISODistributor.metadata()
        expected_types = [TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM, TYPE_ID_ERRATA,
                          TYPE_ID_DISTRO, TYPE_ID_PKG_CATEGORY, TYPE_ID_PKG_GROUP]
        self.assertEquals(metadata['id'], TYPE_ID_DISTRIBUTOR_EXPORT)
        self.assertEqual(set(expected_types), set(metadata['types']))

    def test_validate_config(self):
        """
        Test the validate_config method in ISODistributor, which just hands the config off to a
        helper method in export_utils
        """
        # Setup
        validate_config = export_utils.validate_export_config
        export_utils.validate_export_config = mock.MagicMock()
        distributor = ISODistributor()

        # Test. All validate_config should do is hand the config argument to the export_utils
        # validator
        distributor.validate_config(None, 'config', None)
        export_utils.validate_export_config.assert_called_once_with('config')

        # Clean up
        export_utils.validate_export_config = validate_config

    @mock.patch('pulp_rpm.plugins.distributors.export_distributor.distributor.ExportRepoPublisher')
    @mock.patch('pulp_rpm.plugins.distributors.export_distributor.export_utils.validate_export_config')
    def test_publish_repo(self, mock_validate, export_publisher):

        mock_validate.return_value = (True, None)
        distributor = ISODistributor()
        export_publisher.return_value = mock.Mock()
        export_publisher.return_value.publish.return_value = 'foo'

        self.assertEquals('foo', distributor.publish_repo(self.repo, self.conduit, self.config))

    @mock.patch('pulp_rpm.plugins.distributors.export_distributor.export_utils.validate_export_config')
    def test_publish_repo_invalid_config(self, mock_validate):

        mock_validate.return_value = (False, 'bar')
        distributor = ISODistributor()

        self.assertRaises(PulpDataException, distributor.publish_repo, self.repo, self.conduit,
                          self.config)

    def test_cancel_publish_repo(self):
        """
        Test cancel_publish_repo, which is not currently fully supported
        """
        distributor = ISODistributor()
        distributor._publisher = mock.Mock()

        distributor.cancel_publish_repo()

        self.assertTrue(distributor._publisher.cancel.called)

    def test_set_progress(self):
        """
        Test set_progress, which simply checks if the progress_callback is None before calling it
        """
        # Setup
        mock_callback = mock.Mock()
        distributor = ISODistributor()

        # Test
        distributor.set_progress('id', 'status', mock_callback)
        mock_callback.assert_called_once_with('id', 'status')

    def test_set_progress_no_callback(self):
        """
        Assert that set_progress don't not attempt to call the callback when it is None
        """
        # Setup
        distributor = ISODistributor()

        # Test
        try:
            distributor.set_progress('id', 'status', None)
        except AttributeError:
            self.fail('set_progress should not try to call None')

    @mock.patch('pulp_rpm.plugins.distributors.export_distributor.distributor.configuration')
    def test_distributor_removed(self, mock_configuration):
        master_dir = os.path.join(self.working_dir, 'master')
        http_dir = os.path.join(self.working_dir, 'http')
        https_dir = os.path.join(self.working_dir, 'https')
        repo_working_dir = os.path.join(self.working_dir, 'repodir')
        self.repo.working_dir = repo_working_dir

        mock_configuration.get_master_publish_dir.return_value = master_dir
        mock_configuration.HTTP_EXPORT_DIR = http_dir
        mock_configuration.HTTPS_EXPORT_DIR = https_dir
        http_dir = os.path.join(http_dir, self.repo.id)
        https_dir = os.path.join(https_dir, self.repo.id)
        os.makedirs(http_dir)
        os.makedirs(https_dir)
        os.makedirs(master_dir)
        os.makedirs(repo_working_dir)

        distributor = ISODistributor()
        distributor.distributor_removed(self.repo, self.config)
        self.assertFalse(os.path.exists(http_dir))
        self.assertFalse(os.path.exists(https_dir))
        self.assertFalse(os.path.exists(master_dir))
        self.assertFalse(os.path.exists(repo_working_dir))

