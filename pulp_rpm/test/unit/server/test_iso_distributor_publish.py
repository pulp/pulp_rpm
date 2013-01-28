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
from rpm_support_base import PulpRPMTests
import importer_mocks
import distributor_mocks

from mock import call, MagicMock, patch
from pulp.plugins.model import Repository, Unit

class TestPublish(PulpRPMTests):
    """
    Test the publish module.
    """
    def setUp(self):
        existing_units = [Unit(ids.TYPE_ID_ISO, {'name': 'test.iso'}, {}, '/path/test.iso'),
                          Unit(ids.TYPE_ID_ISO, {'name': 'test2.iso'}, {}, '/path/test2.iso'),
                          Unit(ids.TYPE_ID_ISO, {'name': 'test3.iso'}, {}, '/path/test3.iso')]
        self.publish_conduit = distributor_mocks.get_publish_conduit(existing_units=existing_units)

    def tearDown(self):
        pass

    def test__build_metadata(self):
        """
        The _build_metadata() method should put the metadata in the build directory.
        """
        repo = MagicMock(spec=Repository)
