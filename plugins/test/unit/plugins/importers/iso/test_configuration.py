# -*- coding: utf-8 -*-

import math

from pulp.common.plugins import importer_constants

from pulp_rpm.plugins.importers.iso import configuration
from pulp_rpm.devel.rpm_support_base import PulpRPMTests
from pulp_rpm.devel import importer_mocks

CONFIG_SSL_CLIENT_CERT = 'ssl_client_cert'
CONFIG_SSL_CLIENT_KEY = 'ssl_client_key'


class TestValidate(PulpRPMTests):
    """
    Test the validate() method.
    """

    def test_empty_config(self):
        # An empty config is actually valid
        config = importer_mocks.get_basic_config()
        status, error_message = configuration.validate(config)
        self.assertTrue(status is True)
        self.assertEqual(error_message, None)

    def test_invalid_config(self):
        config = importer_mocks.get_basic_config(
            **{importer_constants.KEY_FEED: "http://test.com/feed",
               importer_constants.KEY_MAX_SPEED: "A Thousand",
               importer_constants.KEY_MAX_DOWNLOADS: 7})
        status, error_message = configuration.validate(config)
        self.assertTrue(status is False)
        self.assertEqual(error_message,
                         'The configuration parameter <max_speed> must be set to a positive '
                         'numerical value, but is currently set to <A Thousand>.')

    def test_validate(self):
        config = importer_mocks.get_basic_config(
            **{importer_constants.KEY_FEED: "http://test.com/feed",
               importer_constants.KEY_MAX_SPEED: 56.6,
               importer_constants.KEY_MAX_DOWNLOADS: 3})
        status, error_message = configuration.validate(config)
        self.assertTrue(status is True)
        self.assertEqual(error_message, None)


class TestValidateFeedUrl(PulpRPMTests):
    def test_invalid_config(self):
        config = importer_mocks.get_basic_config(**{importer_constants.KEY_FEED: 42})
        status, error_message = configuration.validate(config)
        self.assertTrue(status is False)
        self.assertEqual(error_message,
                         '<%(feed)s> must be a string.' % {'feed': importer_constants.KEY_FEED})
 
    def test_valid(self):
        config = importer_mocks.get_basic_config(
            **{importer_constants.KEY_FEED: "http://test.com/feed"})
        status, error_message = configuration.validate(config)
        self.assertTrue(status is True)
        self.assertEqual(error_message, None)


class TestValidateMaxSpeed(PulpRPMTests):
    def test_validate(self):
        config = importer_mocks.get_basic_config(**{importer_constants.KEY_MAX_SPEED: 1.0,
                                                    importer_constants.KEY_FEED: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status is True)
        self.assertEqual(error_message, None)

    def test_invalid_config(self):
        config = importer_mocks.get_basic_config(**{importer_constants.KEY_MAX_SPEED: -1.0,
                                                    importer_constants.KEY_FEED: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status is False)
        self.assertEqual(error_message,
                         'The configuration parameter <max_speed> must be set to a positive '
                         'numerical value, but is currently set to <-1.0>.')

    def test_invalid_str(self):
        config = importer_mocks.get_basic_config(**{importer_constants.KEY_MAX_SPEED: '-42.0',
                                                    importer_constants.KEY_FEED: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status is False)
        self.assertEqual(
            error_message, 'The configuration parameter <max_speed> must be set to a positive '
                           'numerical value, but is currently set to <-42.0>.')

    def test_str(self):
        config = importer_mocks.get_basic_config(**{importer_constants.KEY_MAX_SPEED: '512.0',
                                                    importer_constants.KEY_FEED: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status is True)
        self.assertEqual(error_message, None)


class TestValidateNumThreads(PulpRPMTests):
    def test_float(self):
        config = importer_mocks.get_basic_config(**{importer_constants.KEY_MAX_DOWNLOADS: math.pi,
                                                    importer_constants.KEY_FEED: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status is False)
        expected_message = (
            'The configuration parameter <%(num_threads)s> must be set to a positive '
            'integer, but is currently set to <%(pi)s>.')
        expected_message = expected_message % {'num_threads': importer_constants.KEY_MAX_DOWNLOADS,
                                               'pi': math.pi}
        self.assertEqual(error_message, expected_message)

    def test_float_str(self):
        config = importer_mocks.get_basic_config(
            **{importer_constants.KEY_MAX_DOWNLOADS: '%s' % math.e,
               importer_constants.KEY_FEED: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status is False)
        expected_message = (
            'The configuration parameter <%(num_threads)s> must be set to a positive '
            'integer, but is currently set to <%(e)s>.')
        expected_message = expected_message % {'num_threads': importer_constants.KEY_MAX_DOWNLOADS,
                                               'e': math.e}
        self.assertEqual(error_message, expected_message)

    def test_validate(self):
        config = importer_mocks.get_basic_config(**{importer_constants.KEY_MAX_DOWNLOADS: 11,
                                                    importer_constants.KEY_FEED: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status is True)
        self.assertEqual(error_message, None)

    def test_validate_str(self):
        config = importer_mocks.get_basic_config(**{importer_constants.KEY_MAX_DOWNLOADS: '2',
                                                    importer_constants.KEY_FEED: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status is True)
        self.assertEqual(error_message, None)

    def test_zero(self):
        config = importer_mocks.get_basic_config(**{importer_constants.KEY_MAX_DOWNLOADS: 0,
                                                    importer_constants.KEY_FEED: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status is False)
        expected_message = (
            'The configuration parameter <%(num_threads)s> must be set to a positive '
            'integer, but is currently set to <0>.')
        expected_message = expected_message % {'num_threads': importer_constants.KEY_MAX_DOWNLOADS}
        self.assertEqual(error_message, expected_message)


class TestValidateProxyPassword(PulpRPMTests):
    def test_password_is_non_string(self):
        parameters = {importer_constants.KEY_PROXY_PASS: 7,
                      importer_constants.KEY_PROXY_USER: "the_dude",
                      importer_constants.KEY_FEED: 'http://test.com'}
        config = importer_mocks.get_basic_config(**parameters)
        status, error_message = configuration.validate(config)
        self.assertTrue(status is False)
        self.assertEqual(error_message,
                         "The configuration parameter <proxy_password> should be a string, "
                         "but it was <type 'int'>.")

    def test_password_requires_username(self):
        parameters = {
            importer_constants.KEY_PROXY_PASS: 'duderino',
            importer_constants.KEY_FEED: 'http://test.com',
            importer_constants.KEY_PROXY_HOST: 'http://test.com'}
        config = importer_mocks.get_basic_config(**parameters)
        status, error_message = configuration.validate(config)
        self.assertTrue(status is False)
        expected_message = (
            'The configuration parameter <%(proxy_pass)s> requires the <%(proxy_user)s> '
            'parameter to also be set.')
        expected_message = expected_message % {'proxy_pass': importer_constants.KEY_PROXY_PASS,
                                               'proxy_user': importer_constants.KEY_PROXY_USER}
        self.assertEqual(error_message, expected_message)

    def test_validate(self):
        parameters = {importer_constants.KEY_PROXY_PASS: 'duderino',
                      importer_constants.KEY_PROXY_USER: 'the_dude',
                      importer_constants.KEY_PROXY_HOST: 'http://fake.com/',
                      importer_constants.KEY_FEED: 'http://test.com'}
        config = importer_mocks.get_basic_config(**parameters)
        status, error_message = configuration.validate(config)
        self.assertTrue(status is True)
        self.assertEqual(error_message, None)


class TestValidateProxyPort(PulpRPMTests):
    def test_float(self):
        parameters = {importer_constants.KEY_PROXY_PORT: math.pi,
                      importer_constants.KEY_PROXY_HOST: 'http://test.com',
                      importer_constants.KEY_FEED: 'http://test.com'}
        config = importer_mocks.get_basic_config(**parameters)
        status, error_message = configuration.validate(config)
        self.assertTrue(status is False)
        self.assertEqual(error_message,
                         'The configuration parameter <proxy_port> must be set to a positive '
                         'integer, but is currently set to <%s>.' % math.pi)

    def test_float_str(self):
        parameters = {
            importer_constants.KEY_PROXY_PORT: '%s' % math.e,
            importer_constants.KEY_PROXY_HOST: 'http://proxy.com',
            importer_constants.KEY_FEED: 'http://test.com'}
        config = importer_mocks.get_basic_config(**parameters)
        status, error_message = configuration.validate(config)
        self.assertTrue(status is False)
        self.assertEqual(error_message,
                         'The configuration parameter <proxy_port> must be set to a positive '
                         'integer, but is currently set to <%s>.' % math.e)

    def test_validate(self):
        parameters = {importer_constants.KEY_PROXY_PORT: 8088,
                      importer_constants.KEY_PROXY_HOST: 'http://proxy.com',
                      importer_constants.KEY_FEED: 'http://test.com'}
        config = importer_mocks.get_basic_config(**parameters)
        status, error_message = configuration.validate(config)
        self.assertTrue(status is True)
        self.assertEqual(error_message, None)

    def test_validate_str(self):
        parameters = {importer_constants.KEY_PROXY_PORT: '3128',
                      importer_constants.KEY_PROXY_HOST: 'http://test.com',
                      importer_constants.KEY_FEED: 'http://test.com'}
        config = importer_mocks.get_basic_config(**parameters)
        status, error_message = configuration.validate(config)
        self.assertTrue(status is True)
        self.assertEqual(error_message, None)

    def test_zero(self):
        parameters = {importer_constants.KEY_PROXY_PORT: 0,
                      importer_constants.KEY_PROXY_HOST: 'http://test.com',
                      importer_constants.KEY_FEED: 'http://test.com'}
        config = importer_mocks.get_basic_config(**parameters)
        status, error_message = configuration.validate(config)
        self.assertTrue(status is False)
        self.assertEqual(error_message,
                         'The configuration parameter <proxy_port> must be set to a positive '
                         'integer, but is currently set to <0>.')


class TestValidateProxyURL(PulpRPMTests):
    def test_required_when_other_parameters_are_present(self):
        for parameters in [
            {importer_constants.KEY_PROXY_PASS: 'flock_of_seagulls',
             importer_constants.KEY_PROXY_USER: 'big_kahuna_burger',
             importer_constants.KEY_FEED: 'http://fake.com'},
            {importer_constants.KEY_PROXY_PORT: '3037',
             importer_constants.KEY_FEED: 'http://fake.com'}]:
            # Each of the above configurations should cause the validator to complain about the
            # proxy_url
            # missing
            config = importer_mocks.get_basic_config(**parameters)
            status, error_message = configuration.validate(config)
            self.assertTrue(status is False)
            expected_message = (
                'The configuration parameter <%(proxy_host)s> is required when any of the '
                'following '
                'other parameters are defined: %(proxy_pass)s, %(proxy_port)s, %(proxy_user)s.')
            expected_message = expected_message % {'proxy_pass': importer_constants.KEY_PROXY_PASS,
                                                   'proxy_user': importer_constants.KEY_PROXY_USER,
                                                   'proxy_port': importer_constants.KEY_PROXY_PORT,
                                                   'proxy_host': importer_constants.KEY_PROXY_HOST}
            self.assertEqual(error_message, expected_message)

    def test_url_is_non_string(self):
        config = importer_mocks.get_basic_config(**{importer_constants.KEY_PROXY_HOST: 7,
                                                    importer_constants.KEY_FEED: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status is False)
        expected_message = (
            "The configuration parameter <%(proxy_host)s> should be a string, but it was "
            "<type 'int'>.")
        expected_message = expected_message % {'proxy_host': importer_constants.KEY_PROXY_HOST}
        self.assertEqual(error_message, expected_message)

    def test_validate(self):
        config = importer_mocks.get_basic_config(
            **{importer_constants.KEY_PROXY_HOST: 'http://fake.com/',
               importer_constants.KEY_FEED: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status is True)
        self.assertEqual(error_message, None)


class TestValidateProxyUsername(PulpRPMTests):
    def test_username_is_non_string(self):
        parameters = {importer_constants.KEY_PROXY_PASS: 'bowling',
                      importer_constants.KEY_PROXY_USER: 185,
                      importer_constants.KEY_PROXY_HOST: 'http://test.com',
                      importer_constants.KEY_FEED: 'http://test2.com'}
        config = importer_mocks.get_basic_config(**parameters)
        status, error_message = configuration.validate(config)
        self.assertTrue(status is False)
        expected_message = (
            "The configuration parameter <%(proxy_user)s> should be a string, but it was "
            "<type 'int'>.")
        expected_message = expected_message % {'proxy_user': importer_constants.KEY_PROXY_USER}
        self.assertEqual(error_message, expected_message)

    def test_username_requires_password(self):
        parameters = {importer_constants.KEY_PROXY_USER: 'the_dude',
                      importer_constants.KEY_FEED: 'http://fake.com',
                      importer_constants.KEY_PROXY_HOST: 'http://fake.com'}
        config = importer_mocks.get_basic_config(**parameters)
        status, error_message = configuration.validate(config)
        self.assertTrue(status is False)
        expected_message = ('The configuration parameter <%(proxy_user)s> requires the '
                            '<%(proxy_pass)s> parameter to also be set.')
        expected_message = expected_message % {'proxy_user': importer_constants.KEY_PROXY_USER,
                                               'proxy_pass': importer_constants.KEY_PROXY_PASS}
        self.assertEqual(error_message, expected_message)

    def test_validate(self):
        params = {importer_constants.KEY_PROXY_PASS: 'duderino',
                  importer_constants.KEY_PROXY_USER: 'the_dude',
                  importer_constants.KEY_PROXY_HOST: 'http://fake.com/',
                  importer_constants.KEY_FEED: 'http://test.com'}
        config = importer_mocks.get_basic_config(**params)
        status, error_message = configuration.validate(config)
        self.assertTrue(status is True)
        self.assertEqual(error_message, None)


class TestValidateRemoveMissingUnits(PulpRPMTests):
    def test_invalid_config(self):
        config = importer_mocks.get_basic_config(
            **{importer_constants.KEY_UNITS_REMOVE_MISSING: 'trizue',
               importer_constants.KEY_FEED: 'http://feed.com'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status is False)
        expected_message = ('The configuration parameter <%(remove_missing)s> may only be set to a '
                            'boolean value, but is currently set to <trizue>.')
        expected_message = expected_message % {
            'remove_missing': importer_constants.KEY_UNITS_REMOVE_MISSING}
        self.assertEqual(error_message, expected_message)

    def test_string_false(self):
        config = importer_mocks.get_basic_config(
            **{importer_constants.KEY_UNITS_REMOVE_MISSING: 'false',
               importer_constants.KEY_FEED: 'http://feed.com'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status is True)
        self.assertEqual(error_message, None)

    def test_valid_config(self):
        config = importer_mocks.get_basic_config(
            **{importer_constants.KEY_UNITS_REMOVE_MISSING: True,
               importer_constants.KEY_FEED: 'http://feed.com'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status is True)
        self.assertEqual(error_message, None)


class TestValidateSSLOptions(PulpRPMTests):
    def test_ca_cert_is_non_string(self):
        config = importer_mocks.get_basic_config(**{importer_constants.KEY_SSL_CA_CERT: 7,
                                                    importer_constants.KEY_FEED: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status is False)
        self.assertEqual(error_message,
                         "The configuration parameter <ssl_ca_cert> should be a string, "
                         "but it was <type 'int'>.")

    def test_client_cert_is_non_string(self):
        config = importer_mocks.get_basic_config(**{importer_constants.KEY_SSL_CLIENT_CERT: 8,
                                                    importer_constants.KEY_FEED: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status is False)
        self.assertEqual(error_message,
                         "The configuration parameter <ssl_client_cert> should be a string, "
                         "but it was <type 'int'>.")

    def test_client_key_is_non_string(self):
        params = {importer_constants.KEY_SSL_CLIENT_KEY: 9,
                  importer_constants.KEY_SSL_CLIENT_CERT: 'cert!',
                  importer_constants.KEY_FEED: 'http://test.com'}
        config = importer_mocks.get_basic_config(**params)
        status, error_message = configuration.validate(config)
        self.assertTrue(status is False)
        self.assertEqual(error_message,
                         "The configuration parameter <ssl_client_key> should be a string, "
                         "but it was <type 'int'>.")

    def test_client_key_requires_client_cert(self):
        config = importer_mocks.get_basic_config(
            **{importer_constants.KEY_SSL_CLIENT_KEY: 'Client Key!',
               importer_constants.KEY_FEED: 'http://test.com'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status is False)
        self.assertEqual(error_message, 'The configuration parameter <ssl_client_key> requires the '
                                        '<ssl_client_cert> parameter to also be set.')

    def test_validate(self):
        params = {
            importer_constants.KEY_SSL_CA_CERT: 'CA Certificate!',
            importer_constants.KEY_SSL_CLIENT_CERT: 'Client Certificate!',
            importer_constants.KEY_SSL_CLIENT_KEY: 'Client Key!',
            importer_constants.KEY_FEED: 'http://test.com'}
        config = importer_mocks.get_basic_config(**params)
        status, error_message = configuration.validate(config)
        self.assertTrue(status is True)
        self.assertEqual(error_message, None)


class TestValidateValidateDownloads(PulpRPMTests):
    def test_invalid_config(self):
        config = importer_mocks.get_basic_config(**{importer_constants.KEY_VALIDATE: 1,
                                                    importer_constants.KEY_FEED: 'http://feed.com'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status is False)
        expected_message = ('The configuration parameter <%(validate)s> may only be set to a '
                            'boolean value, but is currently set to <1>.')
        expected_message = expected_message % {'validate': importer_constants.KEY_VALIDATE}
        self.assertEqual(error_message, expected_message)

    def test_string_true(self):
        config = importer_mocks.get_basic_config(**{importer_constants.KEY_VALIDATE: 'true',
                                                    importer_constants.KEY_FEED: 'http://feed.com'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status is True)
        self.assertEqual(error_message, None)

    def test_valid_config(self):
        config = importer_mocks.get_basic_config(**{importer_constants.KEY_VALIDATE: True,
                                                    importer_constants.KEY_FEED: 'http://feed.com'})
        status, error_message = configuration.validate(config)
        self.assertTrue(status is True)
        self.assertEqual(error_message, None)
