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
from pulp_rpm.common import constants
from pulp_rpm.plugins.importers.iso_importer import configuration
from rpm_support_base import PulpRPMTests
import importer_mocks

class TestValidate(PulpRPMTests):
    """
    Test the validate() method.
    """
    def test_validate(self):
        config = importer_mocks.get_basic_config(
            **{constants.CONFIG_FEED_URL: "http://test.com/feed", constants.CONFIG_MAX_SPEED: 56.6})
        status, error_message = configuration.validate(config)
        self.assertTrue(status)
        self.assertEqual(error_message, None)
        
    def test_invalid_config(self):
        config = importer_mocks.get_basic_config(**{constants.CONFIG_FEED_URL: "http://test.com/feed",
                                                    constants.CONFIG_MAX_SPEED: "A Thousand"})
        status, error_message = configuration.validate(config)
        self.assertFalse(status)
        self.assertEqual(error_message, 'The configuration parameter <max_speed> must be set to a positive '
                                        'numerical value, but is currently set to <A Thousand>.')


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