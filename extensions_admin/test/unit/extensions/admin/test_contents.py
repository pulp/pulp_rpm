import mock

from pulp.bindings.responses import Response
from pulp.client.commands.criteria import DisplayUnitAssociationsCommand
from pulp.client.extensions.core import PulpPrompt

from pulp_rpm.extensions.admin import contents
from pulp_rpm.devel.client_base import PulpClientTests


class PackageSearchCommandTests(PulpClientTests):
    def test_structure(self):
        command = contents.PackageSearchCommand(None, self.context)
        self.assertTrue(isinstance(command, DisplayUnitAssociationsCommand))
        self.assertEqual(command.context, self.context)

    @mock.patch('pulp_rpm.extensions.admin.criteria_utils.parse_key_value')
    def test_parse_key_value_override(self, mock_parse):
        command = contents.PackageSearchCommand(None, self.context)
        command._parse_key_value('test-data')
        mock_parse.assert_called_once_with('test-data')

    @mock.patch('pulp_rpm.extensions.admin.criteria_utils.parse_sort')
    def test_parse_sort(self, mock_parse):
        command = contents.PackageSearchCommand(None, self.context)
        command._parse_sort('test-data')
        mock_parse.assert_called_once_with(DisplayUnitAssociationsCommand, 'test-data')

    @mock.patch('pulp.bindings.repository.RepositoryUnitAPI.search')
    def test_run_search(self, mock_search):
        # Setup
        mock_out = mock.MagicMock()
        units = [{'a': 'a', 'metadata': 'm'}]
        mock_search.return_value = Response(200, units)

        user_input = {
            'repo-id': 'repo-1',
            DisplayUnitAssociationsCommand.ASSOCIATION_FLAG.keyword: True,
        }

        # Test
        command = contents.BaseSearchCommand(None, self.context)
        command.run_search(['fake-type'], out_func=mock_out, **user_input)

        # Verify
        expected = {
            'type_ids': ['fake-type'],
            DisplayUnitAssociationsCommand.ASSOCIATION_FLAG.keyword: True,
        }
        mock_search.assert_called_once_with('repo-1', **expected)
        mock_out.assert_called_once_with(units)

    @mock.patch('pulp.bindings.repository.RepositoryUnitAPI.search')
    def test_run_search_no_details(self, mock_search):
        # Setup
        mock_out = mock.MagicMock()
        units = [{'a': 'a', 'metadata': 'm'}]
        mock_search.return_value = Response(200, units)

        user_input = {
            'repo-id': 'repo-1',
            DisplayUnitAssociationsCommand.ASSOCIATION_FLAG.keyword: False,
        }

        # Test
        command = contents.BaseSearchCommand(None, self.context)
        command.run_search(['fake-type'], out_func=mock_out, **user_input)

        # Verify
        expected = {
            'type_ids': ['fake-type'],
            DisplayUnitAssociationsCommand.ASSOCIATION_FLAG.keyword: False,
        }
        mock_search.assert_called_once_with('repo-1', **expected)
        mock_out.assert_called_once_with(['m'])  # only the metadata due to no details

    @mock.patch('pulp.bindings.repository.RepositoryUnitAPI.search')
    def test_run_search_with_field_filters(self, mock_search):
        # Setup
        mock_out = mock.MagicMock()
        units = [{'a': 'a', 'metadata': 'm'}]
        mock_search.return_value = Response(200, units)

        user_input = {
            'repo-id': 'repo-1',
            DisplayUnitAssociationsCommand.ASSOCIATION_FLAG.keyword: False,
        }

        # Test
        command = contents.BaseSearchCommand(None, self.context)
        command.run_search([contents.TYPE_RPM], out_func=mock_out, **user_input)

        # Verify
        expected = {
            'type_ids': [contents.TYPE_RPM],
            DisplayUnitAssociationsCommand.ASSOCIATION_FLAG.keyword: False,
        }
        mock_search.assert_called_once_with('repo-1', **expected)
        mock_out.assert_called_once_with(['m'], contents.FIELDS_BY_TYPE[contents.TYPE_RPM])

    def test_reformat_rpm_provides_requires(self):
        # Setup
        test_rpm = {
            'provides': [{'name': 'name.1',
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
            'requires': [{'name': 'name.1',
                          'version': 'version.1',
                          'release': 'release.1',
                          'epoch': 'epoch.1',
                          'flags': 'GT'},
                         ]
        }

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

    def test_reformat_rpm_no_provides(self):
        """
        When a user doesn't specify provides in the --fields option, reformat_rpm should not
        attempt to reformat the field
        """
        # Setup a test rpm without a provides field
        test_rpm = {
            'requires': [
                {'name': 'name.1',
                 'version': 'version.1',
                 'release': 'release.1',
                 'epoch': 'epoch.1',
                 'flags': 'GT'},
            ]

        }

        # Test
        command = contents.PackageSearchCommand(None, self.context)
        command._reformat_rpm_provides_requires(test_rpm)

        # Verify requires was reformatted into a single string
        self.assertTrue(isinstance(test_rpm['requires'][0], basestring))
        self.assertEqual(test_rpm['requires'][0], 'name.1 > version.1-release.1-epoch.1')
        # Confirm there's no 'provides' field
        self.assertFalse('provides' in test_rpm)

    def test_reformat_rpm_no_requires(self):
        """
        When a user doesn't specify requires in the --fields option, reformat_rpm should not
        attempt to reformat the field
        """
        # Set up an rpm without a requires field
        test_rpm = {
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
            ]
        }

        # Test
        command = contents.PackageSearchCommand(None, self.context)
        command._reformat_rpm_provides_requires(test_rpm)

        # Verify
        self.assertTrue(isinstance(test_rpm['provides'][0],
                                   basestring))
        self.assertTrue(isinstance(test_rpm['provides'][1],
                                   basestring))

        self.assertEqual(test_rpm['provides'][0],
                         'name.1-version.1-release.1-epoch.1')
        self.assertEqual(test_rpm['provides'][1],
                         'name.2')
        # Confirm there's no 'required' field
        self.assertFalse('requires' in test_rpm)

    def test_reformat_rpm_no_requires_provides(self):
        """
        When a user doesn't specify provides and requires in the --fields option, reformat_rpm
        should not try and reformat those fields
        """
        test_rpm = {}

        # Test
        command = contents.PackageSearchCommand(None, self.context)
        command._reformat_rpm_provides_requires(test_rpm)

        # Verify no fields showed up uninvited
        self.assertFalse('provides' in test_rpm)
        self.assertFalse('requires' in test_rpm)

    def test_reformat_rpm_no_requires_details(self):
        """
        Since details wraps the requires field in a metadata dict, test that when the requires field
        isn't specified, reformat_rpm doesn't try and reformat the non-existent field.
        """
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
        self.assertEqual(test_rpm[contents.ASSOCIATION_METADATA_KEYWORD]['provides'][0],
                         'name.1-version.1-release.1-epoch.1')
        self.assertEqual(test_rpm[contents.ASSOCIATION_METADATA_KEYWORD]['provides'][1],
                         'name.2')
        self.assertFalse('requires' in test_rpm[contents.ASSOCIATION_METADATA_KEYWORD])

    def test_reformat_rpm_no_provides_details(self):
        """
        Since details wraps the provides field in a metadata dict, test that when the provides field
        isn't specified, reformat_rpm doesn't try and reformat the non-existent field.
        """
        test_rpm = {contents.ASSOCIATION_METADATA_KEYWORD: {
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
        self.assertTrue(isinstance(test_rpm[contents.ASSOCIATION_METADATA_KEYWORD]['requires'][0],
                                   basestring))
        self.assertEqual(test_rpm[contents.ASSOCIATION_METADATA_KEYWORD]['requires'][0],
                         'name.1 > version.1-release.1-epoch.1')
        self.assertFalse('provides' in test_rpm[contents.ASSOCIATION_METADATA_KEYWORD])

    def test_reformat_rpm_no_requires_provides_details(self):
        """
        Test that reformat_rpm correctly handles no 'provides' or 'requires' fields inside the
        metadata dict.
        """
        test_rpm = {contents.ASSOCIATION_METADATA_KEYWORD: {}}

        # Test
        command = contents.PackageSearchCommand(None, self.context)
        command._reformat_rpm_provides_requires(test_rpm)

        # Verify no fields showed up uninvited
        self.assertFalse('provides' in test_rpm[contents.ASSOCIATION_METADATA_KEYWORD])
        self.assertFalse('requires' in test_rpm[contents.ASSOCIATION_METADATA_KEYWORD])


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


class SearchPackageEnvironmentsCommand(PulpClientTests):
    def test_structure(self):
        command = contents.SearchPackageEnvironmentsCommand(self.context)
        self.assertTrue(isinstance(command, contents.BaseSearchCommand))
        self.assertEqual(command.context, self.context)
        self.assertEqual(command.name, 'environment')
        self.assertEqual(command.description, contents.DESC_ENVIRONMENTS)


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

    @mock.patch('pulp.bindings.repository.RepositoryUnitAPI.search')
    def test_run_search_errata(self, mock_search):
        """
        Test that when the --erratum-id argument isn't used, the default
        render_document_list output function is called
        """
        # Setup
        mock_out = mock.MagicMock()
        units = [{'a': 'a', 'metadata': 'm'}]
        mock_search.return_value = Response(200, units)

        user_input = {
            'repo-id': 'repo-1',
            'erratum-id': None,
            DisplayUnitAssociationsCommand.ASSOCIATION_FLAG.keyword: False,
        }

        # Test
        self.context.prompt.render_document_list = mock_out
        command = contents.SearchErrataCommand(self.context)
        command.errata(**user_input)

        # Verify
        expected = {
            'type_ids': [contents.TYPE_ERRATUM],
            'erratum-id': None,
            DisplayUnitAssociationsCommand.ASSOCIATION_FLAG.keyword: False,
        }
        mock_search.assert_called_once_with('repo-1', **expected)
        # Because there's only one type_id and contents.FIELDS_BY_TYPE[FIELDS_ERRATA] is
        # defined, the output function should be called with the metadata and FIELDS_ERRATA
        mock_out.assert_called_once_with(['m'], contents.FIELDS_ERRATA)

    @mock.patch('pulp.bindings.repository.RepositoryUnitAPI.search')
    def test_run_search_errata_details(self, mock_search):
        """
        Test that when the --erratum-id argument is used, the custom output
        function write_erratum_detail is called instead of render_document_list
        """
        # Setup
        mock_out = mock.MagicMock()
        units = [{'a': 'a', 'metadata': 'm'}]
        mock_search.return_value = Response(200, units)

        user_input = {
            'repo-id': 'repo-1',
            'erratum-id': 'RHEA-0000:0000',
            DisplayUnitAssociationsCommand.ASSOCIATION_FLAG.keyword: False
        }

        # Test
        command = contents.SearchErrataCommand(self.context)
        command.write_erratum_detail = mock_out
        command.errata(**user_input)

        # Verify
        expected = {
            'type_ids': [contents.TYPE_ERRATUM],
            'filters': {'id': 'RHEA-0000:0000'},
        }
        mock_search.assert_called_once_with('repo-1', **expected)
        # Because there's only one type_id and contents.FIELDS_BY_TYPE[FIELDS_ERRATA] is
        # defined, the write_erratum_detail should be called with the metadata and FIELDS_ERRATA
        mock_out.assert_called_once_with(['m'], contents.FIELDS_ERRATA)

    def test_write_erratum_detail(self):
        errata_list = [
            {
                'issued': '2012-01-27 16:08:08',
                'references': [
                    {
                        'href': 'www.example.com',
                        'type': 'enhancement',
                        'id': 'example_reference',
                        'title': 'Example Reference'
                    }
                ],
                '_content_type_id': 'erratum',
                'id': 'RHEA-2012:0003',
                'from': 'errata@redhat.com',
                'severity': '',
                'title': 'Bird_Erratum',
                '_ns': 'units_erratum',
                'version': '1',
                'reboot_suggested': False,
                'type': 'security',
                'pkglist': [
                    {
                        'packages': [
                            {
                                'src': 'http://www.fedoraproject.org',
                                'name': 'crow',
                                'sum': None,
                                'filename': 'crow-0.8-1.el9.noarch.rpm',
                                'epoch': 1,
                                'version': '0.8',
                                'release': '1.el9',
                                'arch': 'noarch'
                            }
                        ],
                        'name': '1',
                        'short': ''
                    },
                    {
                        'packages': [
                            {
                                'src': 'http://www.fedoraproject.org',
                                'name': 'crow',
                                'sum': None,
                                'filename': 'crow-0.9-1.el10.noarch.rpm',
                                'epoch': 1,
                                'version': '0.9',
                                'release': '1.el10',
                                'arch': 'noarch'
                            }
                        ],
                        'name': '1',
                        'short': ''
                    }
                ],
                'status': 'stable',
                'updated': '',
                'description': 'Bird_Erratum',
                '_last_updated': 1402514111,
                'pushcount': '',
                '_storage_path': None,
                'rights': '',
                'solution': '',
                'summary': '',
                'release': '1',
                '_id': '0058de26-29e6-4ba8-b230-7e1a3e261894'
            }
        ]
        self.context.prompt = mock.MagicMock(spec=PulpPrompt)
        command = contents.SearchErrataCommand(self.context)

        # Test that the formatter handles an errata list and calls write
        command.write_erratum_detail(errata_list)
        self.assertEqual(1, self.context.prompt.write.call_count)

        # subclass str so we can use our own equality test. This lets us just
        # check for the substring we are interested in.
        class AnyStringWith(str):
            def __eq__(self, other):
                return self in other

        # Test that both packages are printed (RHBZ #1171278)
        self.context.prompt.write.\
            assert_called_once_with(AnyStringWith("crow-1:0.8-1.el9.noarch"), skip_wrap=True)
        self.context.prompt.write.\
            assert_called_once_with(AnyStringWith("crow-1:0.9-1.el10.noarch"), skip_wrap=True)
