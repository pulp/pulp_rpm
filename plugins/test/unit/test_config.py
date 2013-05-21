# -*- coding: utf-8 -*-
# Copyright (c) 2013 Red Hat, Inc.
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
