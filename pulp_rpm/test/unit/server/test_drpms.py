# -*- coding: utf-8 -*-
#
# Copyright © 2011 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

import mock
import os
import shutil
import sys
import tempfile

from pulp.plugins.model import Repository

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)) + "/../../../src/")
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)) + "/../../../plugins/importers/")
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)) + "/../../common")

from pulp_rpm.common.ids import UNIT_KEY_DRPM, TYPE_ID_IMPORTER_YUM, TYPE_ID_DRPM
from rpm_support_base import PulpRPMTests
from yum_importer import drpm, importer_rpm
from yum_importer.importer import YumImporter
import importer_mocks


class TestDRPMS(PulpRPMTests):

    def setUp(self):
        super(TestDRPMS, self).setUp()
        self.temp_dir = tempfile.mkdtemp()
        self.working_dir = os.path.join(self.temp_dir, "working")
        self.pkg_dir = os.path.join(self.temp_dir, "packages")
        self.data_dir = os.path.abspath(os.path.join(os.path.abspath(os.path.dirname(__file__)), "../data"))

    def tearDown(self):
        super(TestDRPMS, self).tearDown()
        self.clean()

    def clean(self):
        shutil.rmtree(self.temp_dir)

    def test_metadata(self):
        metadata = YumImporter.metadata()
        self.assertEquals(metadata["id"], TYPE_ID_IMPORTER_YUM)
        self.assertTrue(TYPE_ID_DRPM in metadata["types"])

    def test_get_available_drpms(self):
        deltarpm = {}
        for k in UNIT_KEY_DRPM:
            deltarpm[k] = "test_drpm"
        available_drpms = drpm.get_available_drpms([deltarpm])
        lookup_key = drpm.form_lookup_drpm_key(deltarpm)
        self.assertEqual(available_drpms[lookup_key], deltarpm)
