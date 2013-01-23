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

from pulp_rpm.common.constants import STATE_COMPLETE
from pulp_rpm.common.ids import TYPE_ID_ISO
from pulp_rpm.plugins.importers.iso_importer.bumper import ISOBumper
from pulp_rpm.plugins.importers.iso_importer.sync import ISOSyncRun
from rpm_support_base import PulpRPMTests
import importer_mocks

from mock import call, MagicMock, patch
from pulp.plugins.model import Repository

class TestISOSyncRun(PulpRPMTests):
    """
    Test the ISOSyncRun object.
    """
    def setUp(self):
        self.iso_sync_run = ISOSyncRun()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_cancel_sync(self):
        """
        Test what happens if cancel_sync is called when there is no Bumper.
        """
        FakeBumper = MagicMock(spec_set=ISOBumper)

        self.iso_sync_run.bumper = FakeBumper()
        self.iso_sync_run.cancel_sync()
        self.iso_sync_run.bumper.cancel_download.assert_called_once_with()

    # TODO: Can we think of a way to assert that the correct Curl calls were made? It might be
    #       possible by either refactoring the mock, or by having the mock maintain a list of the
    #       curl Mocks it generated.
    # TODO: Remove the mocks on the progress report, once we have written it
    @patch('pulp_rpm.plugins.importers.iso_importer.bumper.pycurl.Curl',
           side_effect=importer_mocks.ISOCurl)
    @patch('pulp_rpm.plugins.importers.iso_importer.bumper.pycurl.CurlMulti',
           side_effect=importer_mocks.CurlMulti)
    @patch('pulp_rpm.plugins.importers.iso_importer.sync.SyncProgressReport', autospec=True)
    def test_perform_sync(self, progress_report, curl_multi, curl):
        """
        Assert that we perform all of the correct calls to various things during perform_sync().
        """
        repo = MagicMock(spec=Repository)
        working_dir = os.path.join(self.temp_dir, "working")
        os.mkdir(working_dir)
        pkg_dir = os.path.join(self.temp_dir, 'content')
        os.mkdir(pkg_dir)
        repo.working_dir = working_dir
        sync_conduit = importer_mocks.get_sync_conduit(type_id=TYPE_ID_ISO, pkg_dir=pkg_dir)
        config = importer_mocks.get_basic_config(
            feed_url='http://fake.com/iso_feed/', max_speed='500.0', num_threads='5',
            ssl_client_cert="Trust me, I'm who I say I am.", ssl_client_key="Secret Key",
            ssl_ca_cert="Uh, I guess that's the right server.",
            proxy_url='http://proxy.com', proxy_port='1234', proxy_user="the_dude",
            proxy_password='bowling')

        report = self.iso_sync_run.perform_sync(repo, sync_conduit, config)

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
