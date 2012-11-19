# -*- coding: utf-8 -*-
#
# Copyright © 2012 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

import mock
from pulp.client.commands.criteria import UnitAssociationCriteriaCommand

from pulp_rpm.extension.admin import contents
from rpm_support_base import PulpClientTests


# mostly legit test data, with a few very large fields stripped out
RPM_DOCUMENTS = (
    {
        "updated": "2012-11-03T00:53:14Z",
        "repo_id": "pulp",
        "created": "2012-11-03T00:53:14Z",
        "_ns": "repo_content_units",
        "unit_id": "b7f835fc-f06e-4db5-830a-ade95221de50",
        "metadata": {
            "_id": "b7f835fc-f06e-4db5-830a-ade95221de50",
            "checksumtype": "sha256",
            "license": "LGPLv2",
            "_ns": "units_rpm",
            "_content_type_id": "rpm",
            "filename": "gofer-0.74-1.fc17.noarch.rpm",
            "epoch": "0",
            "version": "0.74",
            "relativepath": "gofer-0.74-1.fc17.noarch.rpm",
            "arch": "noarch",
            "checksum": "bbc593911abdf79e48243c186d690ec572c6954ad908ada6fef226df0fff55ca",
            "release": "1.fc17",
            "vendor": "",
            "buildhost": "localhost",
            "name": "gofer"
        },
        "unit_type_id": "rpm",
        "owner_type": "importer",
        "_id": {
            "$oid": "509432bae19a00ee71000059"
        },
        "id": "509432bae19a00ee71000059",
        "owner_id": "yum_importer"
    },
)


class TestContentCommand(PulpClientTests):
    @mock.patch('pulp.bindings.repository.RepositoryUnitAPI.search')
    def test_basic_call(self, mock_search):
        contents._content_command(self.context, ['rpm'], **{'repo-id':'repo1', 'limit':1})
        mock_search.assert_called_once_with('repo1', type_ids=['rpm'], limit=1)

    @mock.patch('pulp.bindings.repository.RepositoryUnitAPI.search')
    def test_details_false(self, mock_search):
        mock_search.return_value.response_body = RPM_DOCUMENTS

        contents._content_command(self.context, ['rpm'], **{'repo-id':'repo1', 'limit':1})
        mock_search.assert_called_once_with('repo1', type_ids=['rpm'], limit=1)

        # make sure it outputs the unit only with attributes in order
        self.assertTrue(self.recorder.lines[0].startswith('Arch:'))
        self.assertTrue(self.recorder.lines[1].startswith('Buildhost:'))
        self.assertTrue(self.recorder.lines[2].startswith('Checksum:'))

    @mock.patch('pulp.bindings.repository.RepositoryUnitAPI.search')
    def test_details_true(self, mock_search):
        mock_search.return_value.response_body = RPM_DOCUMENTS

        contents._content_command(
            self.context, ['rpm'], **{'repo-id':'repo1', 'limit':1,
            UnitAssociationCriteriaCommand.ASSOCIATION_FLAG.keyword:True}
        )

        # make sure we get the unit and association data
        self.assertTrue([l for l in self.recorder.lines if l.startswith('Metadata:')])
        self.assertTrue([l for l in self.recorder.lines if l.startswith('  Arch:')])
        self.assertTrue([l for l in self.recorder.lines if l.startswith('Repo Id:')])
        self.assertTrue([l for l in self.recorder.lines if l.startswith('Updated:')])


class TestRPMsCommand(PulpClientTests):
    def setUp(self):
        super(TestRPMsCommand, self).setUp()
        self.command = contents.SearchRpmsCommand(self.context)

    @mock.patch.object(contents, '_content_command')
    def test_basic_call(self, mock_content_command):
        self.command.rpm(**{UnitAssociationCriteriaCommand.ASSOCIATION_FLAG.keyword: False})

        # make sure it calls the generic command
        self.assertEqual(mock_content_command.call_count, 1)
        self.assertEqual(mock_content_command.call_args[0][1], [contents.TYPE_RPM])
        self.assertEqual(
            mock_content_command.call_args[1][UnitAssociationCriteriaCommand.ASSOCIATION_FLAG.keyword],
            False)

    @mock.patch.object(contents, '_content_command')
    def test_out_func_details_false(self, mock_content_command):
        self.command.rpm(**{UnitAssociationCriteriaCommand.ASSOCIATION_FLAG.keyword: False})

        # just using the mock to get our hands on the out_func
        out_func = mock_content_command.call_args[1]['out_func']
        out_func([d['metadata'] for d in RPM_DOCUMENTS])

        # make sure it outputs the document with attributes in order
        self.assertTrue(self.recorder.lines[0].startswith('Arch:'))
        self.assertTrue(self.recorder.lines[1].startswith('Buildhost:'))
        self.assertTrue(self.recorder.lines[2].startswith('Checksum:'))

    @mock.patch.object(contents, '_content_command')
    def test_out_func_details_true(self, mock_content_command):
        self.command.rpm(**{UnitAssociationCriteriaCommand.ASSOCIATION_FLAG.keyword: True})

        # just using the mock to get our hands on the out_func
        out_func = mock_content_command.call_args[1]['out_func']
        out_func(RPM_DOCUMENTS)

        # make sure the first item out the door is "Metadata"
        self.assertTrue(self.recorder.lines[0].startswith('Metadata:'))
        self.assertTrue(self.recorder.lines[1].startswith('  Arch:'))
        # make sure we get the association data
        self.assertTrue([l for l in self.recorder.lines if l.startswith('Repo Id:')])
        self.assertTrue([l for l in self.recorder.lines if l.startswith('Updated:')])
