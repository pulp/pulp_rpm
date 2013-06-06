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
from pulp.bindings.responses import Response
from pulp.client.commands.criteria import DisplayUnitAssociationsCommand

from pulp_rpm.extension.admin import contents
from rpm_support_base import PulpClientTests


class PackageSearchCommandTests(PulpClientTests):

    def test_structure(self):
        command = contents.PackageSearchCommand(None, self.context)
        self.assertTrue(isinstance(command, DisplayUnitAssociationsCommand))
        self.assertEqual(command.context, self.context)

    @mock.patch('pulp_rpm.extension.criteria_utils.parse_key_value')
    def test_parse_key_value_override(self, mock_parse):
        command = contents.PackageSearchCommand(None, self.context)
        command._parse_key_value('test-data')
        mock_parse.assert_called_once_with('test-data')

    @mock.patch('pulp_rpm.extension.criteria_utils.parse_sort')
    def test_parse_sort(self, mock_parse):
        command = contents.PackageSearchCommand(None, self.context)
        command._parse_sort('test-data')
        mock_parse.assert_called_once_with(DisplayUnitAssociationsCommand, 'test-data')

    @mock.patch('pulp.bindings.repository.RepositoryUnitAPI.search')
    def test_run_search(self, mock_search):
        # Setup
        mock_out = mock.MagicMock()
        units = [{'a' : 'a', 'metadata' : 'm'}]
        mock_search.return_value = Response(200, units)

        user_input = {
            'repo-id' : 'repo-1',
            DisplayUnitAssociationsCommand.ASSOCIATION_FLAG.keyword : True,
        }

        # Test
        command = contents.BaseSearchCommand(None, self.context)
        command.run_search(['fake-type'], out_func=mock_out, **user_input)

        # Verify
        expected = {
            'type_ids' : ['fake-type'],
             DisplayUnitAssociationsCommand.ASSOCIATION_FLAG.keyword : True,
        }
        mock_search.assert_called_once_with('repo-1', **expected)
        mock_out.assert_called_once_with(units)

    @mock.patch('pulp.bindings.repository.RepositoryUnitAPI.search')
    def test_run_search_no_details(self, mock_search):
        # Setup
        mock_out = mock.MagicMock()
        units = [{'a' : 'a', 'metadata' : 'm'}]
        mock_search.return_value = Response(200, units)

        user_input = {
            'repo-id' : 'repo-1',
            DisplayUnitAssociationsCommand.ASSOCIATION_FLAG.keyword : False,
            }

        # Test
        command = contents.BaseSearchCommand(None, self.context)
        command.run_search(['fake-type'], out_func=mock_out, **user_input)

        # Verify
        expected = {
            'type_ids' : ['fake-type'],
            DisplayUnitAssociationsCommand.ASSOCIATION_FLAG.keyword : False,
            }
        mock_search.assert_called_once_with('repo-1', **expected)
        mock_out.assert_called_once_with(['m'])  # only the metadata due to no details

    def test_reformat_rpm_provides_requires(self):
        # Setup
        test_rpm = {'provides' : [
                        {'name' : 'name.1',
                         'version' : 'version.1',
                         'release' : 'release.1',
                         'epoch' : 'epoch.1',
                         'flags' : None,},
                        {'name' : 'name.2',
                         'version' : None,
                         'release' : None,
                         'epoch' : None,
                         'flags' : None},
                    ],
                    'requires' : [
                        {'name' : 'name.1',
                         'version' : 'version.1',
                         'release' : 'release.1',
                         'epoch' : 'epoch.1',
                         'flags' : 'GT'},
                    ]}

        # Test
        command = contents.PackageSearchCommand(None, self.context)
        command._reformat_rpm_provides_requires(test_rpm)

        # Verify
        self.assertTrue(isinstance(test_rpm['provides'][0], basestring))
        self.assertTrue(isinstance(test_rpm['provides'][1], basestring))
        self.assertTrue(isinstance(test_rpm['requires'][0], basestring))

        self.assertEqual(test_rpm['provides'][0], 'name.1-version.1-release.1-epoch.1')
        self.assertEqual(test_rpm['provides'][1], 'name.2')
        self.assertEqual(test_rpm['requires'][0], 'name.1 > version.1-release.1-epoch.1')

    def test_reformat_rpm_provides_requires_details(self):
        """
        When the details flag is set, package_search manually applies a filter for the unit data.
        Everything except for the association information is placed in a dict called metadata. This
        tests that the provides and requires sections are reformatted with this second structure.
        """
        # Setup
        test_rpm = {contents.ASSOCIATION_METADATA_KEYWORD: {
            'provides': [
                {'name': 'name.1',
                 'version': 'version.1',
                 'release': 'release.1',
                 'epoch': 'epoch.1',
                 'flags': None},
                {'name': 'name.2',
                 'version': None,
                 'release': None,
                 'epoch': None,
                 'flags': None},
            ],
            'requires': [
                {'name': 'name.1',
                 'version': 'version.1',
                 'release': 'release.1',
                 'epoch': 'epoch.1',
                 'flags': 'GT'},
            ]

        }}

        # Test
        command = contents.PackageSearchCommand(None, self.context)
        command._reformat_rpm_provides_requires(test_rpm)

        # Verify
        self.assertTrue(isinstance(test_rpm[contents.ASSOCIATION_METADATA_KEYWORD]['provides'][0],
                                   basestring))
        self.assertTrue(isinstance(test_rpm[contents.ASSOCIATION_METADATA_KEYWORD]['provides'][1],
                                   basestring))
        self.assertTrue(isinstance(test_rpm[contents.ASSOCIATION_METADATA_KEYWORD]['requires'][0],
                                   basestring))

        self.assertEqual(test_rpm[contents.ASSOCIATION_METADATA_KEYWORD]['provides'][0],
                         'name.1-version.1-release.1-epoch.1')
        self.assertEqual(test_rpm[contents.ASSOCIATION_METADATA_KEYWORD]['provides'][1],
                         'name.2')
        self.assertEqual(test_rpm[contents.ASSOCIATION_METADATA_KEYWORD]['requires'][0],
                         'name.1 > version.1-release.1-epoch.1')


class SearchRpmsCommand(PulpClientTests):

    def test_structure(self):
        command = contents.SearchRpmsCommand(self.context)
        self.assertTrue(isinstance(command, contents.PackageSearchCommand))
        self.assertEqual(command.context, self.context)
        self.assertEqual(command.name, 'rpm')
        self.assertEqual(command.description, contents.DESC_RPMS)


class SearchSrpmsCommand(PulpClientTests):

    def test_structure(self):
        command = contents.SearchSrpmsCommand(self.context)
        self.assertTrue(isinstance(command, contents.PackageSearchCommand))
        self.assertEqual(command.context, self.context)
        self.assertEqual(command.name, 'srpm')
        self.assertEqual(command.description, contents.DESC_SRPMS)


class SearchDrpmsCommand(PulpClientTests):

    def test_structure(self):
        command = contents.SearchDrpmsCommand(self.context)
        self.assertTrue(isinstance(command, contents.BaseSearchCommand))
        self.assertEqual(command.context, self.context)
        self.assertEqual(command.name, 'drpm')
        self.assertEqual(command.description, contents.DESC_DRPMS)


class SearchPackageGroupsCommand(PulpClientTests):

    def test_structure(self):
        command = contents.SearchPackageGroupsCommand(self.context)
        self.assertTrue(isinstance(command, contents.BaseSearchCommand))
        self.assertEqual(command.context, self.context)
        self.assertEqual(command.name, 'group')
        self.assertEqual(command.description, contents.DESC_GROUPS)


class SearchPackageCategoriesCommand(PulpClientTests):

    def test_structure(self):
        command = contents.SearchPackageCategoriesCommand(self.context)
        self.assertTrue(isinstance(command, contents.BaseSearchCommand))
        self.assertEqual(command.context, self.context)
        self.assertEqual(command.name, 'category')
        self.assertEqual(command.description, contents.DESC_CATEGORIES)


class SearchDistributionsCommand(PulpClientTests):

    def test_structure(self):
        command = contents.SearchDistributionsCommand(self.context)
        self.assertTrue(isinstance(command, contents.BaseSearchCommand))
        self.assertEqual(command.context, self.context)
        self.assertEqual(command.name, 'distribution')
        self.assertEqual(command.description, contents.DESC_DISTRIBUTIONS)


class SearchErrataCommand(PulpClientTests):

    def test_structure(self):
        command = contents.SearchErrataCommand(self.context)
        self.assertTrue(isinstance(command, contents.BaseSearchCommand))
        self.assertEqual(command.context, self.context)
        self.assertEqual(command.name, 'errata')
        self.assertEqual(command.description, contents.DESC_ERRATA)
