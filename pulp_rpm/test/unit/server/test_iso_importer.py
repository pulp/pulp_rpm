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
from pulp_rpm.common import ids
from pulp_rpm.plugins.importers.iso_importer.importer import ISOImporter
from rpm_support_base import PulpRPMTests
import importer_mocks

from pulp.plugins.model import Unit

class TestISOImporter(PulpRPMTests):
    """
    Test the ISOImporter object.
    """
    def setUp(self):
        self.iso_importer = ISOImporter()

    def test_import_units__units_none(self):
        """
        Make sure that when units=None, we import all units from the import_conduit.
        """
        # source_repo, dest_repo, and config aren't used by import_units, so we'll just set them to
        # None for simplicity.
        source_units = [Unit(ids.TYPE_ID_ISO, {'name': 'test.iso'}, {}, '/path/test.iso'),
                        Unit(ids.TYPE_ID_ISO, {'name': 'test2.iso'}, {}, '/path/test2.iso'),
                        Unit(ids.TYPE_ID_ISO, {'name': 'test3.iso'}, {}, '/path/test3.iso')]
        import_conduit = importer_mocks.get_import_conduit(source_units=source_units)
        self.iso_importer.import_units(None, None, import_conduit, None, units=None)

        # There should have been two calls to the import_conduit. One to get_source_units(), and one
        # to associate units.
        # get_source_units should have a UnitAssociationCriteria that specified ISOs, so we'll
        # assert that behavior.
        self.assertEqual(len(import_conduit.get_source_units.call_args_list), 1)
        get_source_units_args = tuple(import_conduit.get_source_units.call_args_list[0])[1]
        self.assertEqual(get_source_units_args['criteria']['type_ids'], [ids.TYPE_ID_ISO])

        # There are three Units, so there should be three calls to associate_unit since we didn't
        # pass which units we wanted to import. Let's make sure the three calls were made with the
        # correct Units.
        self.assertEqual(len(import_conduit.associate_unit.call_args_list), 3)
        expected_unit_names = ['test.iso', 'test2.iso', 'test3.iso']
        actual_unit_names = [tuple(call)[0][0].unit_key['name'] \
                             for call in import_conduit.associate_unit.call_args_list]
        self.assertEqual(actual_unit_names, expected_unit_names)
