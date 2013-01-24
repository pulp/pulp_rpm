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
from pulp_rpm.plugins.importers.iso_importer.importer import ISOImporter
from rpm_support_base import PulpRPMTests


class TestISOImporter(PulpRPMTests):
    """
    Test the ISOImporter object.
    """
    def setUp(self):
        self.iso_importer = ISOImporter()

    def test_import_units(self):
        """
        import_units() doesn't actually do anything, so this test just ensures that we have
        overridden it so that it doesn't raise NotImplemented anymore. Think of this test as a
        placeholder in case we ever need to add functionality to this method, and it will also catch
        it if anyone ever accidentally removes import_units(). This test also has the added benefit
        of getting us one more line of unit test coverage!
        """
        # It actually doesn't matter what we pass to this function, because it just passes anyway.
        # As long as this doesn't raise NotImplemented, we're happy.
        self.iso_importer.import_units(None, None, None, None)
