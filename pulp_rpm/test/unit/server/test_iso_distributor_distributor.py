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
"""
Tests for pulp_rpm.plugins.distributors.iso_distributor.distributor
"""
import csv
import os
import shutil
import tempfile

from pulp_rpm.common import constants, ids
from pulp_rpm.plugins.distributors.iso_distributor import distributor
from rpm_support_base import PulpRPMTests
import distributor_mocks

from mock import MagicMock, patch
from pulp.plugins.model import Repository, Unit

class TestEntryPoint(PulpRPMTests):
    """
    Test the entry_point method. This is really just to get good coverage numbers, but hey.
    """
    def test_entry_point(self):
        iso_distributor, config = distributor.entry_point()
        self.assertEqual(iso_distributor, distributor.ISODistributor)
        self.assertEqual(config, {})

class TestISODistributor(PulpRPMTests):
    """
    Test the ISODistributor object.
    """
    def setUp(self):
        self.existing_units = [
            Unit(ids.TYPE_ID_ISO, {'name': 'test.iso', 'size': 1, 'checksum': 'sum1'},
                 {}, '/path/test.iso'),
            Unit(ids.TYPE_ID_ISO,{'name': 'test2.iso', 'size': 2, 'checksum': 'sum2'},
                 {}, '/path/test2.iso'),
            Unit(ids.TYPE_ID_ISO, {'name': 'test3.iso', 'size': 3, 'checksum': 'sum3'},
                 {}, '/path/test3.iso')]
        self.iso_distributor = distributor.ISODistributor()
        self.temp_dir = tempfile.mkdtemp()

        # Monkeypatch the publishing location so we don't try to write to /var
        self._original_iso_http_dir = constants.ISO_HTTP_DIR
        self._original_iso_https_dir = constants.ISO_HTTPS_DIR
        constants.ISO_HTTP_DIR = os.path.join(self.temp_dir, 'published', 'http', 'isos')
        constants.ISO_HTTPS_DIR = os.path.join(self.temp_dir, 'published', 'https', 'isos')

    def tearDown(self):
        # Undo our monkeypatch and clean up our temp dir
        constants.ISO_HTTP_DIR = self._original_iso_http_dir
        constants.ISO_HTTPS_DIR = self._original_iso_https_dir
        shutil.rmtree(self.temp_dir)

    def test_metadata(self):
        metadata = distributor.ISODistributor.metadata()
        self.assertEqual(metadata['id'], ids.TYPE_ID_DISTRIBUTOR_ISO)
        self.assertEqual(metadata['display_name'], 'ISO Distributor')
        self.assertEqual(metadata['types'], [ids.TYPE_ID_ISO])

    @patch('pulp_rpm.repo_auth.protected_repo_utils.ProtectedRepoUtils.delete_protected_repo')
    def test_publish_repo(self, delete_protected_repo):
        repo = MagicMock(spec=Repository)
        repo.id = 'lebowski'
        repo.working_dir = self.temp_dir
        publish_conduit = distributor_mocks.get_publish_conduit(existing_units=self.existing_units)
        config = distributor_mocks.get_basic_config(**{constants.CONFIG_SERVE_HTTP: True,
                                                       constants.CONFIG_SERVE_HTTPS: True})

        # We haven't implemented reporting yet, so we don't yet assert anything about the report
        # here.
        report = self.iso_distributor.publish_repo(repo, publish_conduit, config)

        # Let's verify that the publish directory looks right
        publishing_paths = [os.path.join(directory, 'lebowski') \
                          for directory in [constants.ISO_HTTP_DIR, constants.ISO_HTTPS_DIR]]
        for publishing_path in publishing_paths:
            for unit in self.existing_units:
                expected_symlink_path = os.path.join(publishing_path, unit.unit_key['name'])
                self.assertTrue(os.path.islink(expected_symlink_path))
                expected_symlink_destination = os.path.join('/', 'path', unit.unit_key['name'])
                self.assertEqual(os.path.realpath(expected_symlink_path),
                                 expected_symlink_destination)

            # Now let's have a look at the PULP_MANIFEST file to make sure it was generated and
            # published correctly.
            manifest_filename = os.path.join(publishing_path, constants.ISO_MANIFEST_FILENAME)
            manifest_rows = []
            with open(manifest_filename) as manifest_file:
                manifest = csv.reader(manifest_file)
                for row in manifest:
                    manifest_rows.append(row)
            expected_manifest_rows = [['test.iso', 'sum1', '1'], ['test2.iso', 'sum2', '2'],
                                      ['test3.iso', 'sum3', '3']]
            self.assertEqual(manifest_rows, expected_manifest_rows)

        # We should have called to delete the protected repo
        self.assertEqual(delete_protected_repo.call_count, 1)
        self.assertEqual(delete_protected_repo.mock_calls[0][1][0], repo.id)

    def test_validate_config(self):
        # validate_config doesn't use the repo or related_repos args, so we'll just pass None for
        # ease
        config = distributor_mocks.get_basic_config(**{constants.CONFIG_SERVE_HTTP: True,
                                                       constants.CONFIG_SERVE_HTTPS: True})
        status, error_message = self.iso_distributor.validate_config(None, config, None)
        self.assertTrue(status)
        self.assertEqual(error_message, None)

        # Try setting the HTTP one to a string, which should be OK as long as it's still True
        config = distributor_mocks.get_basic_config(**{constants.CONFIG_SERVE_HTTP: "True",
                                                       constants.CONFIG_SERVE_HTTPS: True})
        status, error_message = self.iso_distributor.validate_config(None, config, None)
        self.assertTrue(status)
        self.assertEqual(error_message, None)
        
        # Now try setting the HTTPS one to an invalid string
        config = distributor_mocks.get_basic_config(**{constants.CONFIG_SERVE_HTTP: True,
                                                       constants.CONFIG_SERVE_HTTPS: "Heyo!"})
        status, error_message = self.iso_distributor.validate_config(None, config, None)
        self.assertFalse(status)
        self.assertEqual(error_message,
                         'The value for <serve_https> must be either "true" or "false"')
