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
import unittest

from pulp.client import arg_utils, parsers
from pulp.client.commands import options as std_options
from pulp.client.commands.repo.cudl import CreateRepositoryCommand
from pulp.client.commands.repo.importer_config import ImporterConfigMixin
from pulp.client.extensions.extensions import PulpCliOption, PulpCliOptionGroup
from pulp.common import constants as pulp_constants
from pulp.common.plugins import importer_constants
import mock

from pulp_rpm.common import constants, ids
from pulp_rpm.extension.admin.iso import create_update
import rpm_support_base


def mock_convert_file_contents(file_keys, args):
    """
    Mock the pulp.client.arg_utils.convert_file_contents() function to stick "This is a file." as any file.
    """
    for key in file_keys:
        if key in args:
            args[key] = 'This is a file.'


class TestISODistributorConfigMixin(unittest.TestCase):
    """
    Test the ISODistributorConfigMixin class.
    """
    @mock.patch('pulp_rpm.extension.admin.iso.create_update.ISODistributorConfigMixin.'
                'add_option_group', create=True)
    def test___init__(self, add_option_group):
        """
        Ensure that the __init__() method sets all of the correct properties.
        """
        distributor_config_mixin = create_update.ISODistributorConfigMixin()

        # There should be publishing and authorization groups added to the CLI
        self.assertTrue(isinstance(distributor_config_mixin.publishing_group, PulpCliOptionGroup))

        # Inspect the --serve-http option
        self.assertTrue(isinstance(distributor_config_mixin.opt_http, PulpCliOption))
        self.assertEqual(distributor_config_mixin.opt_http.name, '--serve-http')
        # Make sure we have a description
        self.assertTrue(distributor_config_mixin.opt_http.description)
        self.assertEqual(distributor_config_mixin.opt_http.required, False)
        self.assertEqual(distributor_config_mixin.opt_http.parse_func, parsers.parse_boolean)

        # Inspect the --serve-https option
        self.assertTrue(isinstance(distributor_config_mixin.opt_https, PulpCliOption))
        self.assertEqual(distributor_config_mixin.opt_https.name, '--serve-https')
        # Make sure we have a description
        self.assertTrue(distributor_config_mixin.opt_https.description)
        self.assertEqual(distributor_config_mixin.opt_https.required, False)
        self.assertEqual(distributor_config_mixin.opt_https.parse_func, parsers.parse_boolean)

        # Inspect the --auth-ca option
        self.assertTrue(isinstance(distributor_config_mixin.opt_auth_ca, PulpCliOption))
        self.assertEqual(distributor_config_mixin.opt_auth_ca.name, '--auth-ca')
        # Make sure we have a description
        self.assertTrue(distributor_config_mixin.opt_auth_ca.description)
        self.assertEqual(distributor_config_mixin.opt_auth_ca.required, False)
        # We didn't set a parser on auth_ca, since it's a path
        self.assertEqual(distributor_config_mixin.opt_auth_ca.parse_func, None)

        # The HTTP, HTTPS, and CA options should be in the publishing group
        self.assertEqual(set(distributor_config_mixin.publishing_group.options),
                         set([distributor_config_mixin.opt_http, distributor_config_mixin.opt_https,
                              distributor_config_mixin.opt_auth_ca]))

        # Lastly, the add_option_group mock should have been called once
        self.assertEqual(add_option_group.call_count, 1)
        self.assertEqual(add_option_group.mock_calls[0][1][0],
                         distributor_config_mixin.publishing_group)

    @mock.patch('pulp_rpm.extension.admin.iso.create_update.ISODistributorConfigMixin.add_option_group',
                mock.MagicMock(), create=True)
    @mock.patch('pulp_rpm.extension.admin.iso.create_update.arg_utils.convert_file_contents',
                mock_convert_file_contents)
    def test__parse_distributor_config_all_set(self):
        """
        Test the _parse_distributor_config() method with all three options set to stuff.
        """
        mixin = create_update.ISODistributorConfigMixin()
        user_input = {mixin.opt_http.keyword: 'true', mixin.opt_https.keyword: 'false',
                      mixin.opt_auth_ca.keyword: '/path/to/file'}

        config = mixin._parse_distributor_config(user_input)

        self.assertEqual(config[constants.CONFIG_SERVE_HTTP], 'true')
        self.assertEqual(config[constants.CONFIG_SERVE_HTTPS], 'false')
        self.assertEqual(config[constants.CONFIG_SSL_AUTH_CA_CERT], 'This is a file.')

    @mock.patch('pulp_rpm.extension.admin.iso.create_update.ISODistributorConfigMixin.add_option_group',
                mock.MagicMock(), create=True)
    def test__parse_distributor_config_bad_file_path(self):
        """
        Test the _parse_distributor_config() method with a non-existing file path for the
        SSL authorization CA.
        """
        mixin = create_update.ISODistributorConfigMixin()
        user_input = {mixin.opt_auth_ca.keyword: '/path/to/nowhere'}

        self.assertRaises(arg_utils.InvalidConfig, mixin._parse_distributor_config,
                          user_input)

    @mock.patch('pulp_rpm.extension.admin.iso.create_update.ISODistributorConfigMixin.add_option_group',
                mock.MagicMock(), create=True)
    def test__parse_distributor_config_only_http_set(self):
        """
        Test the _parse_distributor_config() method with only the http setting set.
        """
        mixin = create_update.ISODistributorConfigMixin()
        user_input = {mixin.opt_http.keyword: 'false'}

        config = mixin._parse_distributor_config(user_input)

        self.assertEqual(len(config), 1)
        self.assertEqual(config[constants.CONFIG_SERVE_HTTP], 'false')


class TestISORepoCreateCommand(rpm_support_base.PulpClientTests):
    """
    Test the ISORepoCreateCommand class.
    """
    @mock.patch('pulp_rpm.extension.admin.iso.create_update.ISODistributorConfigMixin.'
                '__init__', side_effect=create_update.ISODistributorConfigMixin.__init__,
                autospec=True)
    @mock.patch('pulp.client.commands.repo.importer_config.ImporterConfigMixin.__init__',
                side_effect=ImporterConfigMixin.__init__, autospec=True)
    @mock.patch('pulp.client.commands.repo.cudl.CreateRepositoryCommand.__init__',
                side_effect=CreateRepositoryCommand.__init__, autospec=True)
    def test___init__(self, create_repo_init, importer_config_init,
                      distributor_config_init):
        """
        Test the __init__() method, ensuring that it calls the __init__() methods for all
        its superclasses.
        """
        create_command = create_update.ISORepoCreateCommand(self.context)

        create_repo_init.assert_called_once_with(create_command, self.context)
        importer_config_init.assert_called_once_with(
            create_command, include_sync=True, include_ssl=True, include_proxy=True,
            include_throttling=True, include_unit_policy=True)
        distributor_config_init.assert_called_once_with(create_command)

        # Make sure we don't present the --retain-old-count option to the user
        self.assertEqual(len(create_command.unit_policy_group.options), 1)

    @mock.patch('pulp_rpm.extension.admin.iso.create_update.ISORepoCreateCommand.'
                'populate_unit_policy',
                side_effect=create_update.ISORepoCreateCommand.populate_unit_policy,
                autospec=True)
    def test_populate_unit_policy(self, populate_unit_policy):
        """
        Make sure that we are only adding the --remove-missing option (and not the
        --remove-old-count option).
        """
        create_command = create_update.ISORepoCreateCommand(self.context)

        populate_unit_policy.assert_called_once_with(create_command)
        self.assertEqual(create_command.unit_policy_group.options,
                         [create_command.options_bundle.opt_remove_missing])

    def test_run_bad_config(self):
        """
        Test the run() function with a bad config.
        """
        create_command = create_update.ISORepoCreateCommand(self.context)
        user_input = {
            std_options.OPTION_REPO_ID.keyword: 'repo_id',
            create_command.options_bundle.opt_feed_cert.keyword: '/wrong/path'}
        # Set up a mock on create_and_configure, so we can make sure it doesn't get called
        self.context.server.repo.create_and_configure = mock.MagicMock()
        create_command.prompt = mock.MagicMock()

        fail_code = create_command.run(**user_input)

        # create_and_configure() shouldn't get called
        self.assertEqual(self.context.server.repo.create_and_configure.call_count, 0)

        # We should have told the user that there was FAIL
        self.assertEqual(create_command.prompt.render_success_message.call_count, 0)
        self.assertEqual(create_command.prompt.render_failure_message.call_count, 1)
        self.assertEqual(create_command.prompt.render_failure_message.mock_calls[0][2]['tag'],
                         'create-failed')
        self.assertEqual(fail_code, os.EX_DATAERR)

    @mock.patch('pulp_rpm.extension.admin.iso.create_update.arg_utils.convert_file_contents',
                mock_convert_file_contents)
    def test_run_good_config_all_options(self):
        """
        Test the run() function with a good config, with all options set.
        """
        create_command = create_update.ISORepoCreateCommand(self.context)
        user_input = {
            std_options.OPTION_REPO_ID.keyword: 'repo_id',
            std_options.OPTION_DESCRIPTION.keyword: 'description',
            std_options.OPTION_NAME.keyword: 'name',
            std_options.OPTION_NOTES.keyword: {'a_note': 'note'},
            create_command.opt_http.keyword: 'true',
            create_command.opt_https.keyword: 'false',
            create_command.opt_auth_ca.keyword: '/path/to/file',
            create_command.options_bundle.opt_feed.keyword: 'http://feed.com/isos',
            create_command.options_bundle.opt_validate.keyword: 'true',
            create_command.options_bundle.opt_proxy_host.keyword: 'proxy.host.com',
            create_command.options_bundle.opt_proxy_port.keyword: '1234',
            create_command.options_bundle.opt_proxy_user.keyword: 'proxy_user',
            create_command.options_bundle.opt_proxy_pass.keyword: 'password',
            create_command.options_bundle.opt_max_speed.keyword: '56.6',
            create_command.options_bundle.opt_max_downloads.keyword: '4',
            create_command.options_bundle.opt_feed_ca_cert.keyword: '/path/to/cert',
            create_command.options_bundle.opt_verify_feed_ssl.keyword: 'true',
            create_command.options_bundle.opt_feed_cert.keyword: '/path/to/other/cert',
            create_command.options_bundle.opt_feed_key.keyword: '/path/to/key',
            create_command.options_bundle.opt_remove_missing.keyword: 'true'}
        # Set up a mock on create_and_configure, so we can intercept the call and inspect
        self.context.server.repo.create_and_configure = mock.MagicMock()
        create_command.prompt = mock.MagicMock()

        create_command.run(**user_input)

        # Assert that we passed all of the correct arguments to create_and_configure()
        self.assertEqual(self.context.server.repo.create_and_configure.call_count, 1)
        args = self.context.server.repo.create_and_configure.mock_calls[0][1]
        self.assertEqual(args[0], 'repo_id')
        self.assertEqual(args[1], 'name')
        self.assertEqual(args[2], 'description')

        # Inspect the repo notes
        expected_notes = {'a_note': 'note',
                          pulp_constants.REPO_NOTE_TYPE_KEY: constants.REPO_NOTE_ISO}
        # Our note was modified to include the repo type
        self.assertEqual(args[3], expected_notes)

        # Inspect the importer config
        self.assertEqual(args[4], ids.TYPE_ID_IMPORTER_ISO)
        expected_importer_config = {
            importer_constants.KEY_FEED: 'http://feed.com/isos',
            importer_constants.KEY_MAX_DOWNLOADS: '4',
            importer_constants.KEY_MAX_SPEED: '56.6',
            importer_constants.KEY_PROXY_HOST: 'proxy.host.com',
            importer_constants.KEY_PROXY_PASS: 'password',
            importer_constants.KEY_PROXY_PORT: '1234',
            importer_constants.KEY_PROXY_USER: 'proxy_user',
            importer_constants.KEY_SSL_CA_CERT: 'This is a file.',
            importer_constants.KEY_SSL_CLIENT_CERT: 'This is a file.',
            importer_constants.KEY_SSL_CLIENT_KEY: 'This is a file.',
            importer_constants.KEY_SSL_VALIDATION: 'true',
            importer_constants.KEY_UNITS_REMOVE_MISSING: 'true',
            importer_constants.KEY_VALIDATE: 'true'}
        self.assertEqual(args[5], expected_importer_config)

        # Inspect the distributors
        expected_distributor_config = {
            constants.CONFIG_SERVE_HTTP: 'true', constants.CONFIG_SERVE_HTTPS: 'false',
            constants.CONFIG_SSL_AUTH_CA_CERT: 'This is a file.'}
        expected_distributor = {
            'distributor_type': ids.TYPE_ID_DISTRIBUTOR_ISO,
            'distributor_config': expected_distributor_config,
            'auto_publish': True, 'distributor_id': ids.TYPE_ID_DISTRIBUTOR_ISO}
        self.assertEqual(args[6], [expected_distributor])

        # We should have told the user that the repo was created successfully
        self.assertEqual(create_command.prompt.render_success_message.call_count, 1)
        self.assertEqual(create_command.prompt.render_success_message.mock_calls[0][2]['tag'],
                         'repo-created')

    @mock.patch('pulp_rpm.extension.admin.iso.create_update.arg_utils.convert_file_contents',
                mock_convert_file_contents)
    def test_run_good_config_subset_of_options(self):
        """
        Test the run() function with a good config, with only a subset of options set.
        This helps us to know that we only send the options that the user set.
        """
        create_command = create_update.ISORepoCreateCommand(self.context)
        user_input = {
            std_options.OPTION_REPO_ID.keyword: 'repo_id',
            create_command.options_bundle.opt_feed.keyword: 'https://feed.com/isos',
            create_command.options_bundle.opt_feed_cert.keyword: '/path/to/other/cert',
            create_command.options_bundle.opt_feed_key.keyword: '/path/to/key'}
        # Set up a mock on create_and_configure, so we can intercept the call and inspect
        self.context.server.repo.create_and_configure = mock.MagicMock()
        create_command.prompt = mock.MagicMock()

        create_command.run(**user_input)

        # Assert that we passed all of the correct arguments to create_and_configure()
        self.assertEqual(self.context.server.repo.create_and_configure.call_count, 1)
        args = self.context.server.repo.create_and_configure.mock_calls[0][1]
        self.assertEqual(args[0], 'repo_id')
        self.assertEqual(args[1], None)
        self.assertEqual(args[2], None)

        # Inspect the repo notes
        expected_notes = {pulp_constants.REPO_NOTE_TYPE_KEY: constants.REPO_NOTE_ISO}
        # Our note was modified to include the repo type
        self.assertEqual(args[3], expected_notes)

        # Inspect the importer config
        self.assertEqual(args[4], ids.TYPE_ID_IMPORTER_ISO)
        expected_importer_config = {
            importer_constants.KEY_FEED: 'https://feed.com/isos',
            importer_constants.KEY_SSL_CLIENT_CERT: 'This is a file.',
            importer_constants.KEY_SSL_CLIENT_KEY: 'This is a file.'}
        self.assertEqual(args[5], expected_importer_config)

        # Inspect the distributors
        expected_distributor_config = {}
        expected_distributor = {
            'distributor_type': ids.TYPE_ID_DISTRIBUTOR_ISO,
            'distributor_config': expected_distributor_config,
            'auto_publish': True, 'distributor_id': ids.TYPE_ID_DISTRIBUTOR_ISO}
        self.assertEqual(args[6], [expected_distributor])

        # We should have told the user that the repo was created successfully
        self.assertEqual(create_command.prompt.render_success_message.call_count, 1)
        self.assertEqual(create_command.prompt.render_success_message.mock_calls[0][2]['tag'],
                         'repo-created')