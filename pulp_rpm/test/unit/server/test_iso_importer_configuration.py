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
    def test_empty_config(self):
        # An empty config is actually valid
        config = importer_mocks.get_basic_config()
        status, error_message = configuration.validate(config)
        self.assertTrue(status)
        self.assertEqual(error_message, None)

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
    def test_invalid_config(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_FEED_URL: 42})
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, '<feed_url> must be a string.')

    def test_required_when_other_parameters_are_present(self):
        for parameters in [
            {constants.CONFIG_MAX_SPEED: '1024'}, {constants.CONFIG_NUM_THREADS: 2},
            {constants.CONFIG_PROXY_PASSWORD: 'flock_of_seagulls',
             constants.CONFIG_PROXY_USER: 'big_kahuna_burger', constants.CONFIG_PROXY_URL: 'http://test.com'},
            {constants.CONFIG_PROXY_URL: 'http://test.com', constants.CONFIG_PROXY_PORT: '3037'},
            {constants.CONFIG_PROXY_URL: 'http://test.com'},
            {constants.CONFIG_SSL_CA_CERT: 'cert'},
            {constants.CONFIG_SSL_CLIENT_CERT: 'cert'},
            {constants.CONFIG_SSL_CLIENT_CERT: 'cert', constants.CONFIG_SSL_CLIENT_KEY: 'key'}]:
                # Each of the above configurations should cause the validator to complain about the feed_url
                # missing
                config = importer_mocks.get_basic_config(**parameters)
                status, error_message = configuration.validate(config)
                self.assertFalse(status)
                self.assertEqual(
                    error_message,
                    'The configuration parameter <feed_url> is required when any of the following other '
                    'parameters are defined: max_speed, num_threads, proxy_password, proxy_port, proxy_url, '
                    'proxy_user, ssl_ca_cert, ssl_client_cert, ssl_client_key')

    def test_valid(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_FEED_URL: "http://test.com/feed"})
        status, error_message = configuration.validate(config)
        self.assertTrue(status)
        self.assertEqual(error_message, None)


class TestValidateMaxSpeed(PulpRPMTests):
    def test_validate(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_MAX_SPEED: 1.0,
                                                    constants.CONFIG_FEED_URL: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status)
        self.assertEqual(error_message, None)

    def test_invalid_config(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_MAX_SPEED: -1.0,
                                                    constants.CONFIG_FEED_URL: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, 'The configuration parameter <max_speed> must be set to a positive '
                                        'numerical value, but is currently set to <-1.0>.')

    def test_invalid_str(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_MAX_SPEED: '-42.0',
                                                    constants.CONFIG_FEED_URL: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, 'The configuration parameter <max_speed> must be set to a positive '
                                        'numerical value, but is currently set to <-42.0>.')

    def test_str(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_MAX_SPEED: '512.0',
                                                    constants.CONFIG_FEED_URL: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status)
        self.assertEqual(error_message, None)


class TestValidateNumThreads(PulpRPMTests):
    def test_float(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_NUM_THREADS: math.pi,
                                                    constants.CONFIG_FEED_URL: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, 'The configuration parameter <num_threads> must be set to a positive '
                                        'integer, but is currently set to <%s>.'%math.pi)

    def test_float_str(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_NUM_THREADS: '%s'%math.e,
                                                    constants.CONFIG_FEED_URL: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, 'The configuration parameter <num_threads> must be set to a positive '
                                        'integer, but is currently set to <%s>.'%math.e)

    def test_validate(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_NUM_THREADS: 11,
                                                    constants.CONFIG_FEED_URL: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status)
        self.assertEqual(error_message, None)

    def test_validate_str(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_NUM_THREADS: '2',
                                                    constants.CONFIG_FEED_URL: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status)
        self.assertEqual(error_message, None)

    def test_zero(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_NUM_THREADS: 0,
                                                    constants.CONFIG_FEED_URL: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, 'The configuration parameter <num_threads> must be set to a positive '
                                        'integer, but is currently set to <0>.')


class TestValidateProxyPassword(PulpRPMTests):
    def test_password_is_non_string(self):
        parameters = {constants.CONFIG_PROXY_PASSWORD: 7, constants.CONFIG_PROXY_USER: "the_dude",
                      constants.CONFIG_FEED_URL: 'http://test.com'}
        config = importer_mocks.get_basic_config(**parameters)
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, "The configuration parameter <proxy_password> should be a string, "
                                        "but it was <type 'int'>.")

    def test_password_requires_username(self):
        parameters = {
            constants.CONFIG_PROXY_PASSWORD: 'duderino', constants.CONFIG_FEED_URL: 'http://test.com',
            constants.CONFIG_PROXY_URL: 'http://test.com'}
        config = importer_mocks.get_basic_config(**parameters)
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, 'The configuration parameter <proxy_password> requires the '
                                        '<proxy_user> parameter to also be set.')

    def test_validate(self):
        parameters = {constants.CONFIG_PROXY_PASSWORD: 'duderino', constants.CONFIG_PROXY_USER: 'the_dude',
                      constants.CONFIG_PROXY_URL: 'http://fake.com/',
                      constants.CONFIG_FEED_URL: 'http://test.com'}
        config = importer_mocks.get_basic_config(**parameters)
        status, error_message = configuration.validate(config)
        self.assertTrue(status)
        self.assertEqual(error_message, None)


class TestValidateProxyPort(PulpRPMTests):
    def test_float(self):
        parameters = {constants.CONFIG_PROXY_PORT: math.pi, constants.CONFIG_PROXY_URL: 'http://test.com',
                      constants.CONFIG_FEED_URL: 'http://test.com'}
        config = importer_mocks.get_basic_config(**parameters)
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, 'The configuration parameter <proxy_port> must be set to a positive '
                                        'integer, but is currently set to <%s>.'%math.pi)

    def test_float_str(self):
        parameters = {
            constants.CONFIG_PROXY_PORT: '%s'%math.e, constants.CONFIG_PROXY_URL: 'http://proxy.com',
            constants.CONFIG_FEED_URL: 'http://test.com'}
        config = importer_mocks.get_basic_config(**parameters)
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, 'The configuration parameter <proxy_port> must be set to a positive '
                                        'integer, but is currently set to <%s>.'%math.e)

    def test_validate(self):
        parameters = {constants.CONFIG_PROXY_PORT: 8088, constants.CONFIG_PROXY_URL: 'http://proxy.com',
                      constants.CONFIG_FEED_URL: 'http://test.com'}
        config = importer_mocks.get_basic_config(**parameters)
        status, error_message = configuration.validate(config)
        self.assertTrue(status)
        self.assertEqual(error_message, None)

    def test_validate_str(self):
        parameters = {constants.CONFIG_PROXY_PORT: '3128', constants.CONFIG_PROXY_URL: 'http://test.com',
                      constants.CONFIG_FEED_URL: 'http://test.com'}
        config = importer_mocks.get_basic_config(**parameters)
        status, error_message = configuration.validate(config)
        self.assertTrue(status)
        self.assertEqual(error_message, None)

    def test_zero(self):
        parameters = {constants.CONFIG_PROXY_PORT: 0, constants.CONFIG_PROXY_URL: 'http://test.com',
                      constants.CONFIG_FEED_URL: 'http://test.com'}
        config = importer_mocks.get_basic_config(**parameters)
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, 'The configuration parameter <proxy_port> must be set to a positive '
                                        'integer, but is currently set to <0>.')


class TestValidateProxyURL(PulpRPMTests):
    def test_required_when_other_parameters_are_present(self):
        for parameters in [
            {constants.CONFIG_PROXY_PASSWORD: 'flock_of_seagulls',
             constants.CONFIG_PROXY_USER: 'big_kahuna_burger', constants.CONFIG_FEED_URL: 'http://fake.com'},
            {constants.CONFIG_PROXY_PORT: '3037', constants.CONFIG_FEED_URL: 'http://fake.com'}]:
                # Each of the above configurations should cause the validator to complain about the proxy_url
                # missing
                config = importer_mocks.get_basic_config(**parameters)
                status, error_message = configuration.validate(config)
                self.assertFalse(status)
                self.assertEqual(
                    error_message,
                    'The configuration parameter <proxy_url> is required when any of the following other '
                    'parameters are defined: proxy_password, proxy_port, proxy_user')

    def test_url_is_non_string(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_PROXY_URL: 7,
                                                    constants.CONFIG_FEED_URL: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, "The configuration parameter <proxy_url> should be a string, "
                                        "but it was <type 'int'>.")

    def test_validate(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_PROXY_URL: 'http://fake.com/',
                                                    constants.CONFIG_FEED_URL: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status)
        self.assertEqual(error_message, None)


class TestValidateProxyUsername(PulpRPMTests):
    def test_username_is_non_string(self):
        parameters = {constants.CONFIG_PROXY_PASSWORD: 'bowling', constants.CONFIG_PROXY_USER: 185,
                      constants.CONFIG_PROXY_URL: 'http://test.com',
                      constants.CONFIG_FEED_URL: 'http://test2.com'}
        config = importer_mocks.get_basic_config(**parameters)
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, "The configuration parameter <proxy_user> should be a string, "
                                        "but it was <type 'int'>.")

    def test_username_requires_password(self):
        parameters = {constants.CONFIG_PROXY_USER: 'the_dude', constants.CONFIG_FEED_URL: 'http://fake.com',
                      constants.CONFIG_PROXY_URL: 'http://fake.com'}
        config = importer_mocks.get_basic_config(**parameters)
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, 'The configuration parameter <proxy_user> requires the '
                                        '<proxy_password> parameter to also be set.')

    def test_validate(self):
        params = {constants.CONFIG_PROXY_PASSWORD: 'duderino', constants.CONFIG_PROXY_USER: 'the_dude',
                  constants.CONFIG_PROXY_URL: 'http://fake.com/',
                  constants.CONFIG_FEED_URL: 'http://test.com'}
        config = importer_mocks.get_basic_config(**params)
        status, error_message = configuration.validate(config)
        self.assertTrue(status)
        self.assertEqual(error_message, None)


class TestValidateSSLOptions(PulpRPMTests):
    def test_ca_cert_is_non_string(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_SSL_CA_CERT: 7,
                                                    constants.CONFIG_FEED_URL: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, "The configuration parameter <ssl_ca_cert> should be a string, "
                                        "but it was <type 'int'>.")

    def test_client_cert_is_non_string(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_SSL_CLIENT_CERT: 8,
                                                    constants.CONFIG_FEED_URL: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, "The configuration parameter <ssl_client_cert> should be a string, "
                                        "but it was <type 'int'>.")

    def test_client_key_is_non_string(self):
        params = {constants.CONFIG_SSL_CLIENT_KEY: 9, constants.CONFIG_SSL_CLIENT_CERT: 'cert!',
                  constants.CONFIG_FEED_URL: 'http://test.com'}
        config = importer_mocks.get_basic_config(**params)
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, "The configuration parameter <ssl_client_key> should be a string, "
                                        "but it was <type 'int'>.")

    def test_client_key_requires_client_cert(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_SSL_CLIENT_KEY: 'Client Key!',
                                                    constants.CONFIG_FEED_URL: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, 'The configuration parameter <ssl_client_key> requires the '
                                        '<ssl_client_cert> parameter to also be set.')

    def test_validate(self):
        params = {
            constants.CONFIG_SSL_CA_CERT: 'CA Certificate!',
            constants.CONFIG_SSL_CLIENT_CERT: 'Client Certificate!',
            constants.CONFIG_FEED_URL: 'http://test.com'}
        config = importer_mocks.get_basic_config(**params)
        status, error_message = configuration.validate(config)
        self.assertTrue(status)
        self.assertEqual(error_message, None)