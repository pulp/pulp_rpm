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
import math

from pulp_rpm.common import constants
from pulp_rpm.plugins.importers.iso_importer import configuration
from rpm_support_base import PulpRPMTests
import importer_mocks

CONFIG_SSL_CLIENT_CERT = 'ssl_client_cert'
CONFIG_SSL_CLIENT_KEY  = 'ssl_client_key'

class TestValidate(PulpRPMTests):
    """
    Test the validate() method.
    """
    def test_invalid_config(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_FEED_URL: "http://test.com/feed",
                                                    constants.CONFIG_MAX_SPEED: "A Thousand",
                                                    constants.CONFIG_NUM_THREADS: 7})
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, 'The configuration parameter <max_speed> must be set to a positive '
                                        'numerical value, but is currently set to <A Thousand>.')

    def test_validate(self):
        config = importer_mocks.get_basic_config(
            **{constants.CONFIG_FEED_URL: "http://test.com/feed", constants.CONFIG_MAX_SPEED: 56.6,
               constants.CONFIG_NUM_THREADS: 3})
        status, error_message = configuration.validate(config)
        self.assertTrue(status)
        self.assertEqual(error_message, None)


class TestValidateFeedUrl(PulpRPMTests):
    def test_valid(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_FEED_URL: "http://test.com/feed"})
        status, error_message = configuration.validate(config)
        self.assertTrue(status)
        self.assertEqual(error_message, None)

    def test_invalid_config(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_FEED_URL: 42})
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, '<feed_url> must be a string.')


class TestValidateMaxSpeed(PulpRPMTests):
    def test_validate(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_MAX_SPEED: 1.0})
        status, error_message = configuration.validate(config)
        self.assertTrue(status)
        self.assertEqual(error_message, None)

    def test_invalid_config(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_MAX_SPEED: -1.0})
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, 'The configuration parameter <max_speed> must be set to a positive '
                                        'numerical value, but is currently set to <-1.0>.')

    def test_invalid_str(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_MAX_SPEED: '-42.0'})
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, 'The configuration parameter <max_speed> must be set to a positive '
                                        'numerical value, but is currently set to <-42.0>.')

    def test_str(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_MAX_SPEED: '512.0'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status)
        self.assertEqual(error_message, None)


class TestValidateNumThreads(PulpRPMTests):
    def test_validate(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_NUM_THREADS: 11})
        status, error_message = configuration.validate(config)
        self.assertTrue(status)
        self.assertEqual(error_message, None)

    def test_float(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_NUM_THREADS: math.pi})
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, 'The configuration parameter <num_threads> must be set to a positive '
                                        'integer, but is currently set to <%s>.'%math.pi)

    def test_float_str(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_NUM_THREADS: '%s'%math.e})
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, 'The configuration parameter <num_threads> must be set to a positive '
                                        'integer, but is currently set to <%s>.'%math.e)

    def test_validate_str(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_NUM_THREADS: '2'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status)
        self.assertEqual(error_message, None)

    def test_zero(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_NUM_THREADS: 0})
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, 'The configuration parameter <num_threads> must be set to a positive '
                                        'integer, but is currently set to <0>.')


class TestValidateProxyPassword(PulpRPMTests):
    def test_password_is_non_string(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_PROXY_PASSWORD: 7,
                                                    constants.CONFIG_PROXY_USER: "the_dude"})
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, "The configuration parameter <proxy_password> should be a string, "
                                        "but it was <type 'int'>.")

    def test_password_requires_url(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_PROXY_PASSWORD: 'duderino',
                                                    constants.CONFIG_PROXY_USER: 'the_dude'})
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, 'The configuration parameter <proxy_password> requires the '
                                        '<proxy_url> parameter to also be set.')

    def test_password_requires_username(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_PROXY_PASSWORD: 'duderino'})
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, 'The configuration parameter <proxy_password> requires the '
                                        '<proxy_user> parameter to also be set.')

    def test_validate(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_PROXY_PASSWORD: 'duderino',
                                                    constants.CONFIG_PROXY_USER: 'the_dude',
                                                    constants.CONFIG_PROXY_URL: 'http://fake.com/'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status)
        self.assertEqual(error_message, None)


class TestValidateProxyPort(PulpRPMTests):
    def test_validate(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_PROXY_PORT: 8088,
                                                    constants.CONFIG_PROXY_URL: 'http://proxy.com'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status)
        self.assertEqual(error_message, None)

    def test_float(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_PROXY_PORT: math.pi,
                                                    constants.CONFIG_PROXY_URL: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, 'The configuration parameter <proxy_port> must be set to a positive '
                                        'integer, but is currently set to <%s>.'%math.pi)

    def test_float_str(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_PROXY_PORT: '%s'%math.e,
                                                    constants.CONFIG_PROXY_URL: 'http://proxy.com'})
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, 'The configuration parameter <proxy_port> must be set to a positive '
                                        'integer, but is currently set to <%s>.'%math.e)

    def test_port_requires_url(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_PROXY_PORT: 3128})
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, 'The configuration parameter <proxy_port> requires the '
                                        '<proxy_url> parameter to also be set.')

    def test_validate_str(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_PROXY_PORT: '3128',
                                                    constants.CONFIG_PROXY_URL: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status)
        self.assertEqual(error_message, None)

    def test_zero(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_PROXY_PORT: 0,
                                                    constants.CONFIG_PROXY_URL: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, 'The configuration parameter <proxy_port> must be set to a positive '
                                        'integer, but is currently set to <0>.')


class TestValidateProxyURL(PulpRPMTests):
    def test_url_is_non_string(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_PROXY_URL: 7})
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, "The configuration parameter <proxy_url> should be a string, "
                                        "but it was <type 'int'>.")

    def test_validate(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_PROXY_URL: 'http://fake.com/'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status)
        self.assertEqual(error_message, None)


class TestValidateProxyUsername(PulpRPMTests):
    def test_username_is_non_string(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_PROXY_PASSWORD: 'bowling',
                                                    constants.CONFIG_PROXY_USER: 185,
                                                    constants.CONFIG_PROXY_URL: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, "The configuration parameter <proxy_user> should be a string, "
                                        "but it was <type 'int'>.")

    def test_username_requires_url(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_PROXY_PASSWORD: 'duderino',
                                                    constants.CONFIG_PROXY_USER: 'the_dude'})
        status, error_message = configuration._validate_proxy_username(config)
        self.assertFalse(status)
        self.assertEqual(error_message, 'The configuration parameter <proxy_user> requires the '
                                        '<proxy_url> parameter to also be set.')

    def test_username_requires_password(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_PROXY_USER: 'the_dude'})
        status, error_message = configuration._validate_proxy_username(config)
        self.assertFalse(status)
        self.assertEqual(error_message, 'The configuration parameter <proxy_user> requires the '
                                        '<proxy_password> parameter to also be set.')

    def test_validate(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_PROXY_PASSWORD: 'duderino',
                                                    constants.CONFIG_PROXY_USER: 'the_dude',
                                                    constants.CONFIG_PROXY_URL: 'http://fake.com/'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status)
        self.assertEqual(error_message, None)


class TestValidateSSLOptions(PulpRPMTests):
    def test_ca_cert_is_non_string(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_SSL_CA_CERT: 7})
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, "The configuration parameter <ssl_ca_cert> should be a string, "
                                        "but it was <type 'int'>.")

    def test_client_cert_is_non_string(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_SSL_CLIENT_CERT: 8})
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, "The configuration parameter <ssl_client_cert> should be a string, "
                                        "but it was <type 'int'>.")

    def test_client_key_is_non_string(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_SSL_CLIENT_KEY: 9})
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, "The configuration parameter <ssl_client_key> should be a string, "
                                        "but it was <type 'int'>.")

    def test_client_key_requires_client_cert(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_SSL_CLIENT_KEY: 'Client Key!'})
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, 'The configuration parameter <ssl_client_key> requires the '
                                        '<ssl_client_cert> parameter to also be set.')

    def test_validate(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_SSL_CA_CERT: 'CA Certificate!',
                                                    constants.CONFIG_SSL_CLIENT_CERT: 'Client Certificate!'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status)
        self.assertEqual(error_message, None)