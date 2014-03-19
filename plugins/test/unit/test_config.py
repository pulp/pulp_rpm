# -*- coding: utf-8 -*-

import unittest

from pulp.common.plugins import importer_constants
from pulp.plugins.config import PluginCallConfiguration

from pulp_rpm.plugins.importers.yum import config_validate


class ValidateTests(unittest.TestCase):
    """
    The bulk of the actual functionality is in the platform utility. These tests verify
    the behavior of how the yum importer interacts with the returned results from those APIs.
    """

    def test_valid(self):
        # Setup
        config = PluginCallConfiguration({}, {}) # an empty configuration is valid

        # Test
        result, error = config_validate.validate(config)

        # Verify
        self.assertEqual(result, True)
        self.assertEqual(error, None)

    def test_invalid(self):
        # Setup
        config = PluginCallConfiguration({}, {importer_constants.KEY_PROXY_PORT : 'foo'}) # should always be wrong

        # Test
        result, error = config_validate.validate(config)

        # Verify
        self.assertEqual(False, result)
        self.assertTrue('Configuration errors' in error)
        self.assertTrue(not error.endswith('\n')) # make sure trailing \n is stripped off
