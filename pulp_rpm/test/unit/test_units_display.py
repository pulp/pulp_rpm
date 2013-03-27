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

import okaara.prompt
from pulp.client.extensions.core import PulpPrompt

from pulp_rpm.common.ids import (TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM, TYPE_ID_ERRATA, TYPE_ID_DISTRO,
                                 TYPE_ID_PKG_GROUP, TYPE_ID_PKG_CATEGORY)
from pulp_rpm.extension.admin import units_display

class UnitsDisplayTests(unittest.TestCase):

    def setUp(self):
        super(UnitsDisplayTests, self).setUp()

        # Disabling color makes it easier to grep results since the character codes aren't there
        self.recorder = okaara.prompt.Recorder()
        self.prompt = PulpPrompt(enable_color=False, output=self.recorder, record_tags=True)

    def test_display_units_zero_count(self):
        # Test
        units_display.display_units(self.prompt, [], 10)

        # Verify
        self.assertEqual(['too-few'], self.prompt.get_write_tags())

    def test_display_units_over_threshold(self):
        # Test
        copied_modules = self._generate_errata(7)
        units_display.display_units(self.prompt, copied_modules, 2)

        # Verify
        expected_tags = ['summary', 'count-entry']
        self.assertEqual(expected_tags, self.prompt.get_write_tags())
        self.assertTrue('7' in self.recorder.lines[1])

    def test_display_units_mixed(self):
        # Setup
        units = self._generate_packages(1, TYPE_ID_RPM) + \
                self._generate_packages(1, TYPE_ID_SRPM) + \
                self._generate_errata(1) + \
                self._generate_distribution(1) + \
                self._generate_drpms(1) + \
                self._generate_package_category(1) + \
                self._generate_package_groups(1)

        # Test
        units_display.display_units(self.prompt, units, 100)

        # Verify
        expected_tags = ['header']
        for i in sorted([TYPE_ID_DISTRO, TYPE_ID_DRPM, TYPE_ID_ERRATA, TYPE_ID_PKG_CATEGORY,
                         TYPE_ID_PKG_GROUP, TYPE_ID_RPM, TYPE_ID_SRPM]):
            expected_tags.append('type-header-%s' % i)
            expected_tags.append('unit-entry-%s' % i)

        self.assertEqual(expected_tags, self.prompt.get_write_tags())

    def test_display_units_sort_units(self):
        # Setup
        units = self._generate_packages(10, TYPE_ID_RPM)  # will be in descending order

        # Test
        units_display.display_units(self.prompt, units, 100)

        # Verify they were written out in ascending order
        for i in range(1, 10):
            self.assertTrue(str(i) in self.recorder.lines[i + 1])

    # -- utilities ------------------------------------------------------------------------------------------

    def _generate_packages(self, count, type_id):
        packages = []
        for i in range(count, 0, -1):
            unit_key = {
                'name' : 'name-%s' % i,
                'epoch' : 'epoch-%s' % i,
                'version' : 'version-%s' % i,
                'release' : 'release-%s' % i,
                'arch' : 'arch-%s' % i,
            }
            packages.append({'type_id' : type_id, 'unit_key' : unit_key})

        return packages

    def _generate_drpms(self, count):
        drpms = []
        for i in range(count, 0, -1):
            unit_key = {
                'epoch' : 'epoch-%s' % i,
                'version' : 'version-%s' % i,
                'release' : 'release-%s' % i,
                'filename' : 'filename-%s' % i,
            }
            drpms.append({'type_id' : TYPE_ID_DRPM, 'unit_key' : unit_key})

        return drpms

    def _generate_distribution(self, count):
        distros = []
        for i in range(count, 0, -1):
            unit_key = {
                'id' : 'id-%s' % i,
                'version' : 'version-%s' % i,
                'arch' : 'arch-%s' % i,
            }
            distros.append({'type_id' : TYPE_ID_DISTRO, 'unit_key' : unit_key})

        return distros

    def _generate_errata(self, count):
        errata = []
        for i in range(count, 0, -1):
            unit_key = {'id' : 'id-%s' % i}
            errata.append({'type_id' : TYPE_ID_ERRATA, 'unit_key' : unit_key})

        return errata

    def _generate_package_groups(self, count):
        groups = []
        for i in range(count, 0, -1):
            unit_key = {'id' : 'id-%s' % i}
            groups.append({'type_id' : TYPE_ID_PKG_GROUP, 'unit_key' : unit_key})

        return groups

    def _generate_package_category(self, count):
        categories = []
        for i in range(count, 0, -1):
            unit_key = {'id' : 'id-%s' % i}
            categories.append({'type_id' : TYPE_ID_PKG_CATEGORY, 'unit_key' : unit_key})

        return categories
