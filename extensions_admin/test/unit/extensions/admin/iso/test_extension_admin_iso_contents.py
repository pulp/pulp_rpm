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

from copy import deepcopy

import mock

from pulp.client.commands.options import OPTION_REPO_ID
from pulp_rpm.common import ids
from pulp_rpm.devel.client_base import PulpClientTests
from pulp_rpm.extensions.admin.iso.contents import ISOSearchCommand


class TestISOSearchCommand(PulpClientTests):
    """
    Test the ISOSearchCommand class.
    """
    def setUp(self):
        super(TestISOSearchCommand, self).setUp()

        # Let's simulate the response from the backend for searching the ISOs. This data was taken from a live
        # Pulp server
        fake_isos = mock.MagicMock()
        fake_isos.response_body = [
            {u'updated': u'2013-06-13T00:16:19Z', u'repo_id': u'cdn', u'created': u'2013-06-13T00:16:19Z',
             u'_ns': u'repo_content_units', u'unit_id': u'2aaa7976-6a2a-4d79-9f13-a72fe4a40ef4',
             u'metadata': {
                u'_storage_path': u'/var/lib/pulp/content/iso/SHA1SUM/'
                                  u'705406710465312e060e2668abbc3d01cce7f7ad1a0ed4cceeee212f0cbe6689/960/'
                                  u'SHA1SUM',
                u'name': u'SHA1SUM',
                u'checksum': u'705406710465312e060e2668abbc3d01cce7f7ad1a0ed4cceeee212f0cbe6689',
                u'_content_type_id': u'iso', u'_id': u'2aaa7976-6a2a-4d79-9f13-a72fe4a40ef4',
                u'_ns': u'units_iso', u'size': 960},
             u'unit_type_id': u'iso', u'owner_type': u'importer',
             u'_id': {u'$oid': u'51b8d713b1a8a11c292579c1'}, u'id': u'51b8d713b1a8a11c292579c1',
             u'owner_id': u'iso_importer'},
            {u'updated': u'2013-06-13T00:16:20Z', u'repo_id': u'cdn', u'created': u'2013-06-13T00:16:20Z',
             u'_ns': u'repo_content_units', u'unit_id': u'fb43a929-77a8-4f31-a95d-510bdb4379f0',
             u'metadata': {
                u'_storage_path': u'/var/lib/pulp/content/iso/SHA256SUM/'
                                  u'26b8fc26aa337c23592cb67e7c05fc0eff4e0d2eb5d70e74c6b27d57becce313/984/'
                                  u'SHA256SUM',
                u'name': u'SHA256SUM',
                u'checksum': u'26b8fc26aa337c23592cb67e7c05fc0eff4e0d2eb5d70e74c6b27d57becce313',
                u'_content_type_id': u'iso', u'_id': u'fb43a929-77a8-4f31-a95d-510bdb4379f0',
                u'_ns': u'units_iso', u'size': 984},
             u'unit_type_id': u'iso', u'owner_type': u'importer',
             u'_id': {u'$oid': u'51b8d714b1a8a11c292579c2'}, u'id': u'51b8d714b1a8a11c292579c2',
             u'owner_id': u'iso_importer'}]
        self.context.server.repo_unit.search = mock.MagicMock(return_value=fake_isos)
        # Let's mock the render_document_list method so we can inspect it
        self.context.prompt.render_document_list = mock.MagicMock()

    def test___init__(self):
        """
        Test the constructor.
        """
        name = 'name'

        search_command = ISOSearchCommand(self.context, name=name)

        self.assertEqual(search_command.context, self.context)
        self.assertEqual(search_command.name, name)
        self.assertEqual(search_command.method, search_command.search_isos)

    def test_search_isos_with_details(self):
        """
        Test the search_isos command when the user passed the --details flag.
        """
        search_command = ISOSearchCommand(self.context)
        self.cli.add_command(search_command)

        self.cli.run('search --details --repo-id a_repo'.split())

        # There should be one call to the search binding. We'll need to build out the options that we will
        # expect to be passed to the search binding. To do that, we'll find all possible options and set them to
        # None
        expected_search_params = dict()
        for option in search_command.options:
            expected_search_params[option.keyword] = None
        for option in search_command.option_groups[0].options:
            expected_search_params[option.keyword] = None

        # Now let's fill out the --details flag as being set True, add the ISO type ID, and remove repo-id
        expected_search_params[search_command.ASSOCIATION_FLAG.keyword] = True
        expected_search_params['type_ids'] = [ids.TYPE_ID_ISO]
        del expected_search_params['repo-id']

        # Now we can assert the correct call
        self.context.server.repo_unit.search.assert_called_once_with('a_repo', **expected_search_params)

        # render_document_list should have been called once, with the details left in
        massaged_isos = deepcopy(self.context.server.repo_unit.search.return_value.response_body)
        for iso in massaged_isos:
            for key in iso['metadata'].keys():
                if key not in ISOSearchCommand.ISO_FIELDS:
                    del iso['metadata'][key]
        expected_filters = ['metadata', 'updated', 'repo_id', 'created', 'unit_id', 'unit_type_id',
                            'owner_type', 'id', 'owner_id']
        self.context.prompt.render_document_list.assert_called_once_with(
            massaged_isos, filters=expected_filters, order=expected_filters)

    def test_search_isos_without_details(self):
        """
        Test the search_isos command when the user did not pass the --details flag.
        """
        search_command = ISOSearchCommand(self.context)
        user_input = {OPTION_REPO_ID.keyword: 'a_repo'}

        search_command.search_isos(**user_input)

        # There should be one call to the search binding
        expected_search_params = deepcopy(user_input)
        expected_search_params['type_ids'] = [ids.TYPE_ID_ISO]
        expected_search_params.pop(OPTION_REPO_ID.keyword)
        self.context.server.repo_unit.search.assert_called_once_with('a_repo', **expected_search_params)

        # render_document_list should have been called once, with the details removed 
        massaged_isos = [
            iso['metadata'] for iso in self.context.server.repo_unit.search.return_value.response_body]
        expected_filters = ISOSearchCommand.ISO_FIELDS
        self.context.prompt.render_document_list.assert_called_once_with(
            massaged_isos, filters=expected_filters, order=expected_filters)
