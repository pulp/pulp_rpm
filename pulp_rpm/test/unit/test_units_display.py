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

from mock import Mock, patch
import okaara.prompt
from pulp.client.extensions.core import PulpPrompt

from pulp_rpm.common.ids import (TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM, TYPE_ID_ERRATA,
                                 TYPE_ID_DISTRO, TYPE_ID_PKG_GROUP, TYPE_ID_PKG_CATEGORY)
from pulp_rpm.extension.admin import units_display


class UnitsDisplayTests(unittest.TestCase):

    def setUp(self):
        super(UnitsDisplayTests, self).setUp()

        # Disabling color makes it easier to grep results since the character codes aren't there
        self.recorder = okaara.prompt.Recorder()
        self.prompt = PulpPrompt(enable_color=False, output=self.recorder, record_tags=True)

    def test_details_package(self):
        unit = {'name': 'foo',
                'version': 'bar',
                'release': 'baz',
                'arch': 'qux'}
        self.assertEquals(units_display._details_package(unit), 'foo-bar-baz-qux')

    def test_details_drpm(self):
        self.assertEquals(units_display._details_drpm({'filename': 'foo'}), 'foo')

    def test_details_id_only(self):
        self.assertEquals(units_display._details_id_only({'id': 'foo'}), 'foo')

    @patch('pulp_rpm.extension.admin.units_display._details_id_only')
    @patch('pulp_rpm.extension.admin.units_display._details_package')
    @patch('pulp_rpm.extension.admin.units_display._details_drpm')
    def test_get_formatter_for_type(self, mock_drpm, mock_package, mock_id_only):
        self.assertTrue(mock_package is units_display.get_formatter_for_type(TYPE_ID_RPM))
        self.assertTrue(mock_package is units_display.get_formatter_for_type(TYPE_ID_SRPM))
        self.assertTrue(mock_drpm is units_display.get_formatter_for_type(TYPE_ID_DRPM))
        self.assertTrue(mock_id_only is units_display.get_formatter_for_type(TYPE_ID_ERRATA))
        self.assertTrue(mock_id_only is units_display.get_formatter_for_type(TYPE_ID_DISTRO))
        self.assertTrue(mock_id_only is units_display.get_formatter_for_type(TYPE_ID_PKG_GROUP))
        self.assertTrue(mock_id_only is units_display.get_formatter_for_type(TYPE_ID_PKG_CATEGORY))
