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
import os
import shutil
import tempfile

from pulp_rpm.common import constants, ids
from pulp_rpm.plugins.importers.iso_importer import importer, sync
from rpm_support_base import PulpRPMTests
import importer_mocks

from pulp.plugins.model import Repository, Unit
import mock


class TestEntryPoint(PulpRPMTests):
    def test_entry_point(self):
        iso_importer, config = importer.entry_point()
        self.assertEqual(iso_importer, importer.ISOImporter)
        self.assertEqual(config, {})


class TestISOImporter(PulpRPMTests):
    """
    Test the ISOImporter object.
    """
    def setUp(self):
        importer_mocks.ISOCurl._curls = []
        self.temp_dir = tempfile.mkdtemp()
        self.iso_importer = importer.ISOImporter()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_cancel_sync_repo(self):
        """
        Make sure the cancel sync gets passed on.
        """
        self.iso_importer.iso_sync = mock.MagicMock(spec=sync.ISOSyncRun)

        # We can pass None for both arguments, because cancel_sync_repo doesn't use its args
        self.iso_importer.cancel_sync_repo(None, None)

        # Assert that the mock cancel has been called once, with no args
        self.iso_importer.iso_sync.cancel_sync.assert_called_once_with()

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
        self.iso_importer.import_units(None, None, import_conduit, None, units=None)

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
        actual_unit_names = [tuple(call)[0][0].unit_key['name'] \
                             for call in import_conduit.associate_unit.call_args_list]
        self.assertEqual(actual_unit_names, expected_unit_names)

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
        self.iso_importer.import_units(None, None, import_conduit, None,
                                       units=[source_units[i] for i in range(0, 3, 2)])

        # There should have been two calls to the import_conduit. None to get_source_units(), and
        # two to associate units.
        self.assertEqual(len(import_conduit.get_source_units.call_args_list), 0)

        # There are two Units, so there should be two calls to associate_unit since we passed which
        # units we wanted to import. Let's make sure the two calls were made with the
        # correct Units.
        self.assertEqual(len(import_conduit.associate_unit.call_args_list), 2)
        expected_unit_names = ['test.iso', 'test3.iso']
        actual_unit_names = [tuple(call)[0][0].unit_key['name'] \
                             for call in import_conduit.associate_unit.call_args_list]
        self.assertEqual(actual_unit_names, expected_unit_names)

    def test_metadata(self):
        """
        Simple test to make sure the metadata function doesn't die or anything.
        """
        metadata = importer.ISOImporter.metadata()
        self.assertEqual(metadata, {'id': ids.TYPE_ID_IMPORTER_ISO, 'display_name': 'ISO Importer',
                                    'types': [ids.TYPE_ID_ISO]})

    @mock.patch('pulp.common.download.downloaders.curl.pycurl.Curl', side_effect=importer_mocks.ISOCurl)
    @mock.patch('pulp.common.download.downloaders.curl.pycurl.CurlMulti', side_effect=importer_mocks.CurlMulti)
    def test_sync_repo(self, curl_multi, curl):
        repo = mock.MagicMock(spec=Repository)
        working_dir = os.path.join(self.temp_dir, "working")
        os.mkdir(working_dir)
        pkg_dir = os.path.join(self.temp_dir, 'content')
        os.mkdir(pkg_dir)
        repo.working_dir = working_dir
        sync_conduit = importer_mocks.get_sync_conduit(type_id=ids.TYPE_ID_ISO, pkg_dir=pkg_dir)
        config = importer_mocks.get_basic_config(
            feed_url='http://fake.com/iso_feed/', max_speed='500.0',
            ssl_client_cert="Trust me, I'm who I say I am.", ssl_client_key="Secret Key",
            ssl_ca_cert="Uh, I guess that's the right server.",
            proxy_url='http://proxy.com', proxy_port='1234', proxy_user="the_dude",
            proxy_password='bowling')

        # Now run the sync
        report = self.iso_importer.sync_repo(repo, sync_conduit, config)

        # There should now be three Units in the DB, one for each of the three ISOs that our mocks
        # got us.
        units = [tuple(call)[1][0] for call in sync_conduit.save_unit.mock_calls]
        self.assertEqual(len(units), 3)
        expected_units = {
            'test.iso': {
                'checksum': 'f02d5a72cd2d57fa802840a76b44c6c6920a8b8e6b90b20e26c03876275069e0',
                'size': 16, 'contents': 'This is a file.\n'},
            'test2.iso': {
                'checksum': 'c7fbc0e821c0871805a99584c6a384533909f68a6bbe9a2a687d28d9f3b10c16',
                'size': 22, 'contents': 'This is another file.\n'},
            'test3.iso': {
                'checksum': '94f7fe923212286855dea858edac1b4a292301045af0ddb275544e5251a50b3c',
                'size': 34, 'contents': 'Are you starting to get the idea?\n'}}
        for unit in units:
            expected_unit = expected_units[unit.unit_key['name']]
            self.assertEqual(unit.unit_key['checksum'], expected_unit['checksum'])
            self.assertEqual(unit.unit_key['size'], expected_unit['size'])
            expected_storage_path = os.path.join(
                pkg_dir, unit.unit_key['name'], unit.unit_key['checksum'],
                str(unit.unit_key['size']), unit.unit_key['name'])
            self.assertEqual(unit.storage_path, expected_storage_path)
            with open(unit.storage_path) as data:
                contents = data.read()
            self.assertEqual(contents, expected_unit['contents'])

    def test_upload_unit(self):
        """
        This method should raise NotImplemented.
        """
        self.assertRaises(NotImplementedError, self.iso_importer.upload_unit, None, None, None, None, None,
                          None, None)

    def test_validate_config(self):
        """
        We already have a seperate test module for config validation, but we can get 100% test coverage with
        this!
        """
        config = importer_mocks.get_basic_config(
            **{constants.CONFIG_FEED_URL: "http://test.com/feed", constants.CONFIG_MAX_SPEED: 128.8})
        # We'll pass None for the parameters that don't get used by validate_config
        status, error_message = self.iso_importer.validate_config(None, config, None)
        self.assertTrue(status)
        self.assertEqual(error_message, None)

        config = importer_mocks.get_basic_config(**{constants.CONFIG_FEED_URL: "http://test.com/feed",
                                                    constants.CONFIG_MAX_SPEED: -42})
        status, error_message = self.iso_importer.validate_config(None, config, None)
        self.assertFalse(status)
        self.assertEqual(error_message, 'The configuration parameter <max_speed> must be set to a positive '
                                        'numerical value, but is currently set to <-42.0>.')
