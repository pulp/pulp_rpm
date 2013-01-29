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
import shutil
import tempfile

from pulp_rpm.common import constants, ids
from pulp_rpm.plugins.distributors.iso_distributor import publish
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
        self.existing_units = [Unit(ids.TYPE_ID_ISO, {'name': 'test.iso'}, {}, '/path/test.iso'),
                               Unit(ids.TYPE_ID_ISO, {'name': 'test2.iso'}, {}, '/path/test2.iso'),
                               Unit(ids.TYPE_ID_ISO, {'name': 'test3.iso'}, {}, '/path/test3.iso')]
        self.publish_conduit = distributor_mocks.get_publish_conduit(
            existing_units=self.existing_units)
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        # shutil.rmtree(self.temp_dir)
        pass

    def test__build_metadata(self):
        """
        The _build_metadata() method should put the metadata in the build directory.
        """
        repo = MagicMock(spec=Repository)
        repo.working_dir = self.temp_dir
        publish._build_metadata(repo, self.existing_units)

        # Now let's have a look at the PULP_MANIFEST file to make sure it was generated correctly.
        manifest_filename = os.path.join(self.temp_dir, publish.BUILD_DIRNAME,
                                constants.ISO_MANIFEST_FILENAME)
        with open(manifest_filename) as manifest_file:
            manifest = csv.reader(manifest_file)
        for row in manifest:
            print row
