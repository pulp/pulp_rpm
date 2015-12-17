import os
import shutil
import tempfile

from pulp.common.plugins import importer_constants
from pulp.plugins.model import Repository, Unit
from pulp.server import constants as server_constants
import mock

from pulp_rpm.common import ids
from pulp_rpm.devel import importer_mocks
from pulp_rpm.devel.rpm_support_base import PulpRPMTests
from pulp_rpm.devel.skip import skip_broken
from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.importers.iso import importer, sync


class TestEntryPoint(PulpRPMTests):
    @mock.patch('pulp.common.config.read_json_config')
    def test_entry_point(self, mock_read_config):
        mock_read_config.return_value = {}

        iso_importer, config = importer.entry_point()

        self.assertEqual(iso_importer, importer.ISOImporter)
        self.assertEqual(config, {})

        mock_read_config.assert_called_once_with('server/plugins.conf.d/iso_importer.json')


class TestISOImporter(PulpRPMTests):
    """
    Test the ISOImporter object.
    """

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.iso_importer = importer.ISOImporter()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_cancel_sync_repo(self):
        """
        Make sure the cancel sync gets passed on.
        """
        self.iso_importer.iso_sync = mock.MagicMock(spec=sync.ISOSyncRun)

        self.iso_importer.cancel_sync_repo()

        # Assert that the mock cancel has been called once, with no args
        self.iso_importer.iso_sync.cancel_sync.assert_called_once_with()

    def test_import_units__units_empty_list(self):
        """
        Make sure that when an empty list is passed, we import zero units.
        """
        source_units = [Unit(ids.TYPE_ID_ISO, {'name': 'test.iso'}, {}, '/path/test.iso'),
                        Unit(ids.TYPE_ID_ISO, {'name': 'test2.iso'}, {}, '/path/test2.iso'),
                        Unit(ids.TYPE_ID_ISO, {'name': 'test3.iso'}, {}, '/path/test3.iso')]
        import_conduit = importer_mocks.get_import_conduit(source_units=source_units)
        # source_repo, dest_repo, and config aren't used by import_units, so we'll just set them to
        # None for simplicity. Let's pass an empty list as the units we want to import
        units_to_import = []
        imported_units = self.iso_importer.import_units(None, None, import_conduit, None,
                                                        units=units_to_import)

        # There should have been zero calls to the import_conduit. None to get_source_units(), and
        # none to associate units.
        self.assertEqual(len(import_conduit.get_source_units.call_args_list), 0)
        self.assertEqual(len(import_conduit.associate_unit.call_args_list), 0)

        # Make sure that the returned units are correct
        self.assertEqual(imported_units, units_to_import)

    def test_import_units__units_none(self):
        """
        Make sure that when units=None, we import all units from the import_conduit.
        """
        source_units = [Unit(ids.TYPE_ID_ISO, {'name': 'test.iso'}, {}, '/path/test.iso'),
                        Unit(ids.TYPE_ID_ISO, {'name': 'test2.iso'}, {}, '/path/test2.iso'),
                        Unit(ids.TYPE_ID_ISO, {'name': 'test3.iso'}, {}, '/path/test3.iso')]
        import_conduit = importer_mocks.get_import_conduit(source_units=source_units)
        # source_repo, dest_repo, and config aren't used by import_units, so we'll just set them to
        # None for simplicity.
        imported_units = self.iso_importer.import_units(None, None, import_conduit, None,
                                                        units=None)

        # There should have been four calls to the import_conduit. One to get_source_units(), and
        # three to associate units.
        # get_source_units should have a UnitAssociationCriteria that specified ISOs, so we'll
        # assert that behavior.
        self.assertEqual(len(import_conduit.get_source_units.call_args_list), 1)
        get_source_units_args = tuple(import_conduit.get_source_units.call_args_list[0])[1]
        self.assertEqual(get_source_units_args['criteria']['type_ids'], [ids.TYPE_ID_ISO])

        # There are three Units, so there should be three calls to associate_unit since we didn't
        # pass which units we wanted to import. Let's make sure the three calls were made with the
        # correct Units.
        self.assertEqual(len(import_conduit.associate_unit.call_args_list), 3)
        expected_unit_names = ['test.iso', 'test2.iso', 'test3.iso']
        actual_unit_names = [tuple(call)[0][0].unit_key['name']
                             for call in import_conduit.associate_unit.call_args_list]
        self.assertEqual(actual_unit_names, expected_unit_names)

        # The three Units should have been returned
        self.assertEqual(imported_units, source_units)

    def test_import_units__units_some(self):
        """
        Make sure that when units are passed, we import only those units.
        """
        source_units = [Unit(ids.TYPE_ID_ISO, {'name': 'test.iso'}, {}, '/path/test.iso'),
                        Unit(ids.TYPE_ID_ISO, {'name': 'test2.iso'}, {}, '/path/test2.iso'),
                        Unit(ids.TYPE_ID_ISO, {'name': 'test3.iso'}, {}, '/path/test3.iso')]
        import_conduit = importer_mocks.get_import_conduit(source_units=source_units)
        # source_repo, dest_repo, and config aren't used by import_units, so we'll just set them to
        # None for simplicity. Let's use test.iso and test3.iso, leaving out test2.iso.
        units_to_import = [source_units[i] for i in range(0, 3, 2)]
        imported_units = self.iso_importer.import_units(None, None, import_conduit, None,
                                                        units=units_to_import)

        # There should have been two calls to the import_conduit. None to get_source_units(), and
        # two to associate units.
        self.assertEqual(len(import_conduit.get_source_units.call_args_list), 0)

        # There are two Units, so there should be two calls to associate_unit since we passed which
        # units we wanted to import. Let's make sure the two calls were made with the
        # correct Units.
        self.assertEqual(len(import_conduit.associate_unit.call_args_list), 2)
        expected_unit_names = ['test.iso', 'test3.iso']
        actual_unit_names = [tuple(call)[0][0].unit_key['name']
                             for call in import_conduit.associate_unit.call_args_list]
        self.assertEqual(actual_unit_names, expected_unit_names)

        # Make sure that the returned units are correct
        self.assertEqual(imported_units, units_to_import)

    def test_metadata(self):
        """
        Simple test to make sure the metadata function doesn't die or anything.
        """
        metadata = importer.ISOImporter.metadata()
        self.assertEqual(metadata, {'id': ids.TYPE_ID_IMPORTER_ISO, 'display_name': 'ISO Importer',
                                    'types': [ids.TYPE_ID_ISO]})

    @skip_broken
    @mock.patch('pulp_rpm.plugins.importers.iso.sync.ISOSyncRun')
    def test_sync_calls_sync(self, mock_sync_run):
        repo = Repository('repo1')
        sync_conduit = importer_mocks.get_sync_conduit(pkg_dir='/a/b/c')
        config = importer_mocks.get_basic_config(**{
            importer_constants.KEY_FEED: 'http://fake.com/iso_feed/'})

        self.iso_importer.sync_repo(repo, sync_conduit, config)

        # make sure the sync workflow is called with the right stuff
        mock_sync_run.assert_called_once_with(sync_conduit, config)
        mock_sync_run.return_value.perform_sync.assert_called_once_with()

    @skip_broken
    def test_sync_no_feed(self):
        repo = mock.MagicMock(spec=Repository)
        pkg_dir = os.path.join(self.temp_dir, 'content')
        sync_conduit = importer_mocks.get_sync_conduit(pkg_dir=pkg_dir)
        config = {importer_constants.KEY_FEED: None}
        config = importer_mocks.get_basic_config(**config)

        # Now run the sync
        self.assertRaises(ValueError, self.iso_importer.sync_repo, repo, sync_conduit, config)

    @skip_broken
    @mock.patch('os.remove', side_effect=os.remove)
    def test_upload_unit_named_PULP_MANIFEST(self, remove):
        """
        We had a bug[0] due to the ISOImporter allowing units to be uploaded named PULP_MANIFEST.
        This test asserts that that is no longer allowed.

        [0] https://bugzilla.redhat.com/show_bug.cgi?id=973678
        """
        # Set up the test
        file_data = 'This is a PULP_MANIFEST file. The upload should be rejected.\n'
        working_dir = os.path.join(self.temp_dir, "working")
        os.mkdir(working_dir)
        pkg_dir = os.path.join(self.temp_dir, 'content')
        os.mkdir(pkg_dir)
        repo = mock.MagicMock(spec=Repository)
        repo.working_dir = working_dir
        # We'll set validation off so the checksum doesn't matter
        unit_key = {'name': 'PULP_MANIFEST', 'size': len(file_data), 'checksum': "Doesn't matter"}
        metadata = {}
        temp_file_location = os.path.join(self.temp_dir, unit_key['name'])
        with open(temp_file_location, 'w') as temp_file:
            temp_file.write(file_data)
        sync_conduit = importer_mocks.get_sync_conduit(pkg_dir=pkg_dir)
        # Just so we don't have to care about the checksum
        config = importer_mocks.get_basic_config(**{importer_constants.KEY_VALIDATE: 'false'})

        report = self.iso_importer.upload_unit(repo, ids.TYPE_ID_ISO, unit_key, metadata,
                                               temp_file_location, sync_conduit, config)

        self.assertEqual(report['success_flag'], False)
        self.assertEqual(report['summary'], 'An ISO may not be named PULP_MANIFEST, as it '
                                            'conflicts with the name of the manifest during '
                                            'publishing.')

        # init_unit() should have been called
        expected_rel_path = os.path.join(unit_key['name'], unit_key['checksum'],
                                         str(unit_key['size']), unit_key['name'])
        modified_metadata = metadata.copy()
        modified_metadata[server_constants.PULP_USER_METADATA_FIELDNAME] = {}
        sync_conduit.init_unit.assert_called_once_with(ids.TYPE_ID_ISO, unit_key, modified_metadata,
                                                       expected_rel_path)

        # The file should have been deleted
        self.assertFalse(os.path.exists(temp_file_location))
        would_be_destination = os.path.join(pkg_dir, expected_rel_path)
        self.assertFalse(os.path.exists(would_be_destination))
        # The file should have been removed from there
        remove.assert_called_once_with(would_be_destination)

        # The conduit's save_unit method should not have been called
        self.assertEqual(sync_conduit.save_unit.call_count, 0)

    @skip_broken
    @mock.patch('pulp_rpm.plugins.db.models.ISO.validate', side_effect=models.ISO.validate,
                autospec=True)
    def test_upload_unit_validate_false(self, validate):
        """
        Assert correct behavior from upload_unit() when the validation setting is False.
        """
        # Set up the test
        file_data = 'This is a file.\n'
        working_dir = os.path.join(self.temp_dir, "working")
        os.mkdir(working_dir)
        pkg_dir = os.path.join(self.temp_dir, 'content')
        os.mkdir(pkg_dir)
        repo = mock.MagicMock(spec=Repository)
        repo.working_dir = working_dir
        # Set the checksum incorrect. The upload should be successful no matter what since
        # validation will be set to False
        unit_key = {'name': 'test.iso', 'size': 16, 'checksum': 'Wrong'}
        metadata = {}
        temp_file_location = os.path.join(self.temp_dir, 'test.iso')
        with open(temp_file_location, 'w') as temp_file:
            temp_file.write(file_data)
        sync_conduit = importer_mocks.get_sync_conduit(pkg_dir=pkg_dir)
        config = importer_mocks.get_basic_config(**{importer_constants.KEY_VALIDATE: 'false'})

        # Run the upload. This should be successful, since we have set validation off.
        report = self.iso_importer.upload_unit(repo, ids.TYPE_ID_ISO, unit_key, metadata,
                                               temp_file_location, sync_conduit, config)

        # The import should have been successful
        self.assertEqual(report['success_flag'], True)
        self.assertEqual(report['summary'], None)

        # The conduit's init_unit method should have been called
        expected_rel_path = os.path.join(unit_key['name'], unit_key['checksum'],
                                         str(unit_key['size']), unit_key['name'])
        modified_metadata = metadata.copy()
        modified_metadata[server_constants.PULP_USER_METADATA_FIELDNAME] = {}
        sync_conduit.init_unit.assert_called_once_with(ids.TYPE_ID_ISO, unit_key, modified_metadata,
                                                       expected_rel_path)

        # The file should have been moved to its final destination
        self.assertFalse(os.path.exists(temp_file_location))
        expected_destination = os.path.join(pkg_dir, expected_rel_path)
        self.assertTrue(os.path.exists(expected_destination))
        with open(expected_destination) as iso_file:
            self.assertEqual(iso_file.read(), file_data)

        # validate() should still have been called, but with the full_validation=False flag
        # We need to get the ISO itself for our assertion, since it is technically the first
        # argument
        iso = validate.mock_calls[0][1][0]
        validate.assert_called_once_with(iso, full_validation=False)

        # The conduit's save_unit method should have been called
        self.assertEqual(sync_conduit.save_unit.call_count, 1)
        saved_unit = sync_conduit.save_unit.mock_calls[0][1][0]
        self.assertEqual(saved_unit.unit_key, unit_key)

    @skip_broken
    @mock.patch('pulp_rpm.plugins.db.models.ISO.validate')
    @mock.patch('os.remove', side_effect=os.remove)
    def test_upload_unit_validate_true_bad_checksum(self, remove, validate):
        """
        Test behavior with a bad checksum.
        """
        # Set up the test
        file_data = 'This is a file.\n'
        error_message = 'uh oh'
        validate.side_effect = ValueError(error_message)
        working_dir = os.path.join(self.temp_dir, "working")
        os.mkdir(working_dir)
        pkg_dir = os.path.join(self.temp_dir, 'content')
        os.mkdir(pkg_dir)
        repo = mock.MagicMock(spec=Repository)
        repo.working_dir = working_dir
        # Set the checksum incorrect. The upload should fail.
        unit_key = {'name': 'test.iso', 'size': 16, 'checksum': 'Wrong'}
        metadata = {}
        temp_file_location = os.path.join(self.temp_dir, 'test.iso')
        with open(temp_file_location, 'w') as temp_file:
            temp_file.write(file_data)
        sync_conduit = importer_mocks.get_sync_conduit(pkg_dir=pkg_dir)
        config = importer_mocks.get_basic_config(**{importer_constants.KEY_VALIDATE: 'true'})

        # Run the upload. This should fail due to the bad checksum
        report = self.iso_importer.upload_unit(repo, ids.TYPE_ID_ISO, unit_key, metadata,
                                               temp_file_location, sync_conduit, config)

        self.assertEqual(report['success_flag'], False)
        self.assertEqual(report['summary'], error_message)
        # The conduit's init_unit method should have been called
        expected_rel_path = os.path.join(unit_key['name'], unit_key['checksum'],
                                         str(unit_key['size']), unit_key['name'])
        modified_metadata = metadata.copy()
        modified_metadata[server_constants.PULP_USER_METADATA_FIELDNAME] = {}
        sync_conduit.init_unit.assert_called_once_with(ids.TYPE_ID_ISO, unit_key, modified_metadata,
                                                       expected_rel_path)

        # The file should have been deleted
        self.assertFalse(os.path.exists(temp_file_location))
        would_be_destination = os.path.join(pkg_dir, expected_rel_path)
        self.assertFalse(os.path.exists(would_be_destination))
        # The file should have been removed from there
        remove.assert_called_once_with(would_be_destination)

        # validate() should have been called with the full_validation=True flag
        validate.assert_called_once_with(full_validation=True)

        # The conduit's save_unit method should not have been called
        self.assertEqual(sync_conduit.save_unit.call_count, 0)

    @skip_broken
    def test_upload_unit_validate_true_good_checksum(self):
        """
        Test behavior with good arguments.
        """
        # Set up the test
        file_data = 'This is a file.\n'
        working_dir = os.path.join(self.temp_dir, "working")
        os.mkdir(working_dir)
        pkg_dir = os.path.join(self.temp_dir, 'content')
        os.mkdir(pkg_dir)
        repo = mock.MagicMock(spec=Repository)
        repo.working_dir = working_dir
        unit_key = {'name': 'test.iso', 'size': 16,
                    'checksum': 'f02d5a72cd2d57fa802840a76b44c6c6920a8b8e6b90b20e26c03876275069e0'}
        metadata = {}
        temp_file_location = os.path.join(self.temp_dir, 'test.iso')
        with open(temp_file_location, 'w') as temp_file:
            temp_file.write(file_data)
        sync_conduit = importer_mocks.get_sync_conduit(pkg_dir=pkg_dir)
        config = importer_mocks.get_basic_config(**{importer_constants.KEY_VALIDATE: 'true'})

        # Run the upload. This should be successful
        report = self.iso_importer.upload_unit(repo, ids.TYPE_ID_ISO, unit_key, metadata,
                                               temp_file_location, sync_conduit, config)

        self.assertEqual(report['success_flag'], True)
        self.assertEqual(report['summary'], None)
        # The conduit's init_unit method should have been called
        expected_rel_path = os.path.join(unit_key['name'], unit_key['checksum'],
                                         str(unit_key['size']), unit_key['name'])
        modified_metadata = metadata.copy()
        modified_metadata[server_constants.PULP_USER_METADATA_FIELDNAME] = {}
        sync_conduit.init_unit.assert_called_once_with(ids.TYPE_ID_ISO, unit_key, modified_metadata,
                                                       expected_rel_path)

        # The file should have been moved to its final destination
        self.assertFalse(os.path.exists(temp_file_location))
        expected_destination = os.path.join(pkg_dir, expected_rel_path)
        self.assertTrue(os.path.exists(expected_destination))
        with open(expected_destination) as iso_file:
            self.assertEqual(iso_file.read(), file_data)

        # The conduit's save_unit method should have been called
        self.assertEqual(sync_conduit.save_unit.call_count, 1)
        saved_unit = sync_conduit.save_unit.mock_calls[0][1][0]
        self.assertEqual(saved_unit.unit_key, unit_key)

    @skip_broken
    @mock.patch('pulp_rpm.plugins.db.models.ISO.validate', side_effect=models.ISO.validate,
                autospec=True)
    @mock.patch('os.remove', side_effect=os.remove)
    def test_upload_unit_validate_unset(self, remove, validate):
        """
        Assert correct behavior from upload_unit() when the validation setting is not set. This
        should default to validating the upload.
        """
        # Set up the test
        file_data = 'This is a file.\n'
        working_dir = os.path.join(self.temp_dir, "working")
        os.mkdir(working_dir)
        pkg_dir = os.path.join(self.temp_dir, 'content')
        os.mkdir(pkg_dir)
        repo = mock.MagicMock(spec=Repository)
        repo.working_dir = working_dir
        # Set the checksum incorrect. The upload should be unsuccessful since the default is to
        # validate
        unit_key = {'name': 'test.iso', 'size': 16, 'checksum': 'Wrong'}
        metadata = {}
        temp_file_location = os.path.join(self.temp_dir, 'test.iso')
        with open(temp_file_location, 'w') as temp_file:
            temp_file.write(file_data)
        sync_conduit = importer_mocks.get_sync_conduit(pkg_dir=pkg_dir)
        # validate isn't set, so default should happen
        config = importer_mocks.get_basic_config()

        # Run the upload. This should report a failure
        report = self.iso_importer.upload_unit(repo, ids.TYPE_ID_ISO, unit_key, metadata,
                                               temp_file_location, sync_conduit, config)

        self.assertEqual(report['success_flag'], False)
        self.assertEqual(
            report['summary'],
            ('Downloading <test.iso> failed checksum validation. The manifest specified the '
             'checksum to be Wrong, but it was '
             'f02d5a72cd2d57fa802840a76b44c6c6920a8b8e6b90b20e26c03876275069e0.'))

        # The conduit's init_unit method should have been called
        expected_rel_path = os.path.join(unit_key['name'], unit_key['checksum'],
                                         str(unit_key['size']), unit_key['name'])
        modified_metadata = metadata.copy()
        modified_metadata[server_constants.PULP_USER_METADATA_FIELDNAME] = {}
        sync_conduit.init_unit.assert_called_once_with(ids.TYPE_ID_ISO, unit_key, modified_metadata,
                                                       expected_rel_path)

        # The file should have been moved to its final destination
        self.assertFalse(os.path.exists(temp_file_location))
        would_be_destination = os.path.join(pkg_dir, expected_rel_path)
        self.assertFalse(os.path.exists(would_be_destination))
        # The file should have been removed
        remove.assert_called_once_with(would_be_destination)

        # validate() should have been called with the full_validation=True flag
        iso = validate.mock_calls[0][1][0]
        validate.assert_called_once_with(iso, full_validation=True)

        # The conduit's save_unit method should have been called
        self.assertEqual(sync_conduit.save_unit.call_count, 0)

    def test_validate_config(self):
        """
        We already have a seperate test module for config validation, but we can get 100% test
        coverage with
        this!
        """
        config = importer_mocks.get_basic_config(
            **{importer_constants.KEY_FEED: "http://test.com/feed",
               importer_constants.KEY_MAX_SPEED: 128.8})
        # We'll pass None for the parameters that don't get used by validate_config
        status, error_message = self.iso_importer.validate_config(None, config)
        self.assertTrue(status)
        self.assertEqual(error_message, None)

        config = importer_mocks.get_basic_config(
            **{importer_constants.KEY_FEED: "http://test.com/feed",
               importer_constants.KEY_MAX_SPEED: -42})
        status, error_message = self.iso_importer.validate_config(None, config)
        self.assertFalse(status)
        self.assertEqual(error_message,
                         'The configuration parameter <max_speed> must be set to a positive '
                         'numerical value, but is currently set to <-42.0>.')
