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

"""
The tests in this module test the pulp_rpm.common.progress module.
"""

from datetime import datetime
import unittest

from pulp_rpm.common import progress
import importer_mocks


class TestISOProgressReport(unittest.TestCase):
    """
    Test the ISOProgressReport class.
    """
    def setUp(self):
        self.conduit = importer_mocks.get_import_conduit()

    def test___init___with_defaults(self):
        """
        Test the __init__ method with all default parameters.
        """
        report = progress.ISOProgressReport(self.conduit)

        # Make sure all the appropriate attributes were set
        self.assertEqual(report.conduit, self.conduit)
        self.assertEqual(report._state, progress.ISOProgressReport.STATE_NOT_STARTED)

        # The state_times attribute should be a dictionary with only the time the not started state was
        # entered
        self.assertTrue(isinstance(report.state_times, dict))
        self.assertEqual(len(report.state_times), 1)
        self.assertTrue(isinstance(report.state_times[progress.ISOProgressReport.STATE_NOT_STARTED],
                                   datetime))

        self.assertEqual(report.num_isos, None)
        self.assertEqual(report.num_isos_finished, 0)
        self.assertEqual(report.iso_error_messages, {})
        self.assertEqual(report.error_message, None)
        self.assertEqual(report.traceback, None)