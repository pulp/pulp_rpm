# Copyright (c) 2012 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

import copy
import os

import mock

from pulp_rpm.extensions.admin.upload import package
from pulp.bindings.responses import Response
from pulp.client.commands.options import OPTION_REPO_ID
from pulp.client.commands.repo.upload import UploadCommand, FileBundle
from pulp_rpm.common.ids import TYPE_ID_RPM, TYPE_ID_SRPM
from pulp_rpm.devel.client_base import PulpClientTests
from pulp_rpm.extensions.admin.upload.package import FLAG_SKIP_EXISTING
from pulp_rpm.extensions.admin.repo_options import OPT_CHECKSUM_TYPE


DATA_DIR = os.path.abspath(os.path.dirname(__file__)) + '/../../../data'
RPM_DIR = DATA_DIR + '/simple_repo_no_comps'
RPM_FILENAME = 'pulp-test-package-0.3.1-1.fc11.x86_64.rpm'


class CreatePackageCommandTests(PulpClientTests):

    def setUp(self):
        super(CreatePackageCommandTests, self).setUp()
        self.upload_manager = mock.MagicMock()
        self.command = package._CreatePackageCommand(self.context, self.upload_manager,
                                                     TYPE_ID_RPM, package.SUFFIX_RPM,
                                                     package.NAME_RPM, package.DESC_RPM)

    def test_structure(self):
        self.assertTrue(isinstance(self.command, UploadCommand))
        self.assertEqual(self.command.name, package.NAME_RPM)
        self.assertEqual(self.command.description, package.DESC_RPM)
        self.assertTrue(FLAG_SKIP_EXISTING in self.command.options)
        self.assertEqual(self.command.suffix, package.SUFFIX_RPM)
        self.assertEqual(self.command.type_id, TYPE_ID_RPM)

    def test_determine_type_id(self):
        type_id = self.command.determine_type_id(None)
        self.assertEqual(type_id, TYPE_ID_RPM)

    def test_matching_files_in_dir(self):
        rpms = self.command.matching_files_in_dir(RPM_DIR)
        self.assertEqual(1, len(rpms))
        self.assertEqual(os.path.basename(rpms[0]), RPM_FILENAME)

    def test_generate_unit_key_and_metadata(self):
        filename = os.path.join(RPM_DIR, RPM_FILENAME)
        unit_key, metadata = self.command.generate_unit_key_and_metadata(filename)

        self.assertEqual(unit_key, {})
        self.assertEqual(metadata, {})

    def test_generate_unit_key_and_metadata_with_checksum(self):
        filename = os.path.join(RPM_DIR, RPM_FILENAME)
        command_kwargs = {'checksum-type': 'sha1'}
        unit_key, metadata = self.command.generate_unit_key_and_metadata(filename, **command_kwargs)

        self.assertEqual(unit_key, {})
        self.assertEqual(metadata, {'checksum-type': 'sha1'})

    def test_create_upload_list_skip_existing(self):
        # Setup

        # The bundle needs to point to a real file since the unit key is derived from it
        # when the existing check needs to occur.
        filename = os.path.join(RPM_DIR, RPM_FILENAME)
        orig_file_bundles = [FileBundle(filename)]
        user_args = {
            FLAG_SKIP_EXISTING.keyword : True,
            OPTION_REPO_ID.keyword : 'repo-1'
        }

        # The format doesn't matter, it's just that the server doesn't return None.
        # This will indicate that the first file already exists but after that, None
        # will be returned indicating the second doesn't exist and should be present
        # in the returned upload list.
        search_results = [{}]
        def search_simulator(repo_id, **criteria):
            response = Response(200, copy.copy(search_results))
            if len(search_results):
                search_results.pop(0)
            return response

        mock_search = mock.MagicMock()
        mock_search.side_effect = search_simulator
        self.bindings.repo_unit.search = mock_search

        # Test
        upload_file_bundles = self.command.create_upload_list(orig_file_bundles, **user_args)

        # Verify
        self.assertEqual(0, len(upload_file_bundles))
        self.assertEqual(1, mock_search.call_count)

        for file_bundle_index in range(0, 1):
            call_args = mock_search.call_args_list[file_bundle_index]
            self.assertEqual(call_args[0][0], 'repo-1')
            expected_filters = {
                'name' : 'pulp-test-package',
                'epoch' : '0',
                'version' : '0.3.1',
                'release' : '1.fc11',
                'arch' : 'x86_64',
                'checksumtype' : 'sha256',
                'checksum' : '6bce3f26e1fc0fc52ac996f39c0d0e14fc26fb8077081d5b4dbfb6431b08aa9f',
            }
            expected_filters.update(orig_file_bundles[file_bundle_index].unit_key)
            expected_criteria_args = {
                'type_ids' : [TYPE_ID_RPM],
                'filters' : expected_filters,
            }
            self.assertEqual(expected_criteria_args, call_args[1])

    def test_create_upload_list_no_skip_existing(self):
        # Setup

        # Filename in the bundle doesn't matter since the file itself isn't checked
        # for any data.
        orig_file_bundles = [FileBundle('a'), FileBundle('b')]
        user_args = {
            FLAG_SKIP_EXISTING.keyword : False,
            OPTION_REPO_ID.keyword : 'repo-1'
        }

        self.bindings.repo_unit.search = mock.MagicMock()

        # Test
        upload_file_bundles = self.command.create_upload_list(orig_file_bundles, **user_args)

        # Verify
        self.assertEqual(orig_file_bundles, upload_file_bundles)
        self.assertEqual(0, self.bindings.repo_unit.search.call_count)


class CreateRpmCommandTests(PulpClientTests):

    def setUp(self):
        super(CreateRpmCommandTests, self).setUp()
        self.upload_manager = mock.MagicMock()
        self.command = package.CreateRpmCommand(self.context, self.upload_manager)

    def test_structure(self):
        self.assertTrue(isinstance(self.command, package._CreatePackageCommand))
        self.assertEqual(self.command.name, package.NAME_RPM)
        self.assertEqual(self.command.description, package.DESC_RPM)
        self.assertEqual(self.command.suffix, package.SUFFIX_RPM)
        self.assertEqual(self.command.type_id, TYPE_ID_RPM)
        self.assertTrue(OPT_CHECKSUM_TYPE in self.command.options)


class CreateSrpmCommandTests(PulpClientTests):

    def setUp(self):
        super(CreateSrpmCommandTests, self).setUp()
        self.upload_manager = mock.MagicMock()
        self.command = package.CreateSrpmCommand(self.context, self.upload_manager)

    def test_structure(self):
        self.assertTrue(isinstance(self.command, package._CreatePackageCommand))
        self.assertEqual(self.command.name, package.NAME_SRPM)
        self.assertEqual(self.command.description, package.DESC_SRPM)
        self.assertEqual(self.command.suffix, package.SUFFIX_SRPM)
        self.assertEqual(self.command.type_id, TYPE_ID_SRPM)
        self.assertTrue(OPT_CHECKSUM_TYPE in self.command.options)
