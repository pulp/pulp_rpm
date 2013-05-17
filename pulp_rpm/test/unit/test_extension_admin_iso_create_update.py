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

import unittest

from pulp.client import parsers
from pulp.client.extensions.extensions import PulpCliOption, PulpCliOptionGroup
import mock

from pulp_rpm.common import constants
from pulp_rpm.extension.admin.iso import create_update


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
    @mock.patch('pulp_rpm.extension.admin.iso.create_update.ISODistributorConfigMixin.add_option_group',
                create=True)
    def test___init__(self, add_option_group):
        """
        Ensure that the __init__() method sets all of the correct properties.
        """
        distributor_config_mixin = create_update.ISODistributorConfigMixin()

        # There should be publishing and authorization groups added to the CLI
        self.assertTrue(isinstance(distributor_config_mixin.publishing_group, PulpCliOptionGroup))
        self.assertTrue(isinstance(distributor_config_mixin.authorization_group, PulpCliOptionGroup))

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

        # The HTTP and HTTPS options should be in the publishing group
        self.assertEqual(set(distributor_config_mixin.publishing_group.options),
                         set([distributor_config_mixin.opt_http, distributor_config_mixin.opt_https]))
        # The --auth-ca option should be in the auth group
        self.assertEqual(distributor_config_mixin.authorization_group.options,
                         [distributor_config_mixin.opt_auth_ca])

        # Lastly, the add_option_group mock should have been called twice, once for each group
        self.assertEqual(add_option_group.call_count, 2)
        self.assertEqual(set([mock_call[1][0] for mock_call in add_option_group.mock_calls]),
                         set([distributor_config_mixin.publishing_group,
                              distributor_config_mixin.authorization_group]))

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
    @mock.patch('pulp_rpm.extension.admin.iso.create_update.arg_utils.convert_file_contents',
                mock_convert_file_contents)
    def test__parse_distributor_config_only_http_set(self):
        """
        Test the _parse_distributor_config() method with only the http setting set.
        """
        mixin = create_update.ISODistributorConfigMixin()
        user_input = {mixin.opt_http.keyword: 'false'}

        config = mixin._parse_distributor_config(user_input)

        self.assertEqual(len(config), 1)
        self.assertEqual(config[constants.CONFIG_SERVE_HTTP], 'false')