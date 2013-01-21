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
from pulp_rpm.plugins.importers.iso_importer.bumper import ISOBumper
from pulp_rpm.plugins.importers.iso_importer.sync import ISOSyncRun
from rpm_support_base import PulpRPMTests

from mock import MagicMock

class TestISOSyncRun(PulpRPMTests):
    """
    Test the ISOSyncRun object.
    """
    def test_cancel_sync(self):
        """
        Test what happens if cancel_sync is called when there is no Bumper.
        """
        iso_sync_run = ISOSyncRun()
        class FakeBumper(object):
            def __init__(self):
                self._cancel_download_called = False

            def cancel_download(self):
                self._cancel_download_called = True

        FakeBumper = MagicMock(spec_set=ISOBumper)

        iso_sync_run.bumper = FakeBumper()
        iso_sync_run.cancel_sync()
        iso_sync_run.bumper.cancel_download.assert_called_once_with()
