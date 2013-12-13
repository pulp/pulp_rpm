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

import mock

from distributor_mocks import get_basic_config
from pulp_rpm.common import constants
from pulp_rpm.plugins import configuration_utils
from pulp_rpm.plugins.distributors.iso_distributor import configuration


class TestValidate(unittest.TestCase):
    """
    Assert correct behavior from the configuration.validate() function.
    """
    @mock.patch('pulp_rpm.plugins.distributors.iso_distributor.configuration._validate_ssl_cert',
                side_effect=configuration._validate_ssl_cert)
    @mock.patch('pulp_rpm.plugins.configuration_utils.validate_non_required_bool',
                side_effect=configuration_utils.validate_non_required_bool)
    def test_validate_calls_correct_helpers(self, _validate_required_bool, _validate_ssl_cert):
        """
        Test that validate() uses all the right helpers.
        """
        config = get_basic_config(**{constants.CONFIG_SERVE_HTTP: True, constants.CONFIG_SERVE_HTTPS: False})

        valid, msg = configuration.validate(config)

        # Assert the return values
        self.assertEqual(valid, True)
        self.assertEqual(msg, None)

        # Assert that _validate_required_bool was called twice with the correct parameters
        self.assertEqual(_validate_required_bool.call_count, 2)
        self.assertEqual(_validate_required_bool.mock_calls[0][1][0], config)
        self.assertEqual(_validate_required_bool.mock_calls[0][1][1], constants.CONFIG_SERVE_HTTP)
        self.assertEqual(_validate_required_bool.mock_calls[1][1][0], config)
        self.assertEqual(_validate_required_bool.mock_calls[1][1][1], constants.CONFIG_SERVE_HTTPS)

        # Assert that _validate_ssl_cert was called once with the right parameters
        _validate_ssl_cert.assert_called_once_with(config, constants.CONFIG_SSL_AUTH_CA_CERT)

    def test_validate_fails(self):
        """
        Test that validate() handles a bad config correctly.
        """
        config = get_basic_config(**{constants.CONFIG_SERVE_HTTP: True, constants.CONFIG_SERVE_HTTPS: False,
                                     constants.CONFIG_SSL_AUTH_CA_CERT: 'Invalid cert.'})

        valid, msg = configuration.validate(config)

        # We passed a valid config, so validate() should have indicated that everything was cool
        self.assertFalse(valid)
        self.assertEqual(msg, 'The SSL certificate <ssl_auth_ca_cert> is not a valid certificate.')

    def test_validate_passes(self):
        """
        Test that validate() handles a good config correctly.
        """
        config = get_basic_config(**{constants.CONFIG_SERVE_HTTP: True, constants.CONFIG_SERVE_HTTPS: False})

        valid, msg = configuration.validate(config)

        # We passed a valid config, so validate() should have indicated that everything was cool
        self.assertTrue(valid)
        self.assertEqual(msg, None)


class TestValidateSSLCert(unittest.TestCase):
    """
    Test the _validate_ssl_cert() function.
    """
    def test_bad_cert(self):
        """
        Assert that a bad cert raises an error.
        """
        config = get_basic_config(**{constants.CONFIG_SSL_AUTH_CA_CERT: 'You cannot be serious.'})

        try:
            configuration._validate_ssl_cert(config, constants.CONFIG_SSL_AUTH_CA_CERT)
            self.fail('The validator should have raised an Exception, but it did not.')
        except configuration_utils.ValidationError, e:
            self.assertEqual(str(e), 'The SSL certificate <ssl_auth_ca_cert> is not a valid certificate.')

    @mock.patch('pulp_rpm.yum_plugin.util.validate_cert', return_value=True)
    def test_good_cert(self, validate_cert):
        """
        Assert that a good cert passes the check.
        """
        cert = 'Good Cert (well, once mock is done with it!)'
        config = get_basic_config(**{constants.CONFIG_SSL_AUTH_CA_CERT: cert})

        # This should not raise an Exception
        configuration._validate_ssl_cert(config, constants.CONFIG_SSL_AUTH_CA_CERT)

        # Make sure the mock was called
        validate_cert.assert_called_once_with(cert)

    def test_no_cert(self):
        """
        Assert that certificates are not required.
        """
        config = get_basic_config(**{})

        # This should not raise an Exception
        configuration._validate_ssl_cert(config, constants.CONFIG_SSL_AUTH_CA_CERT)