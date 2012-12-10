# -*- coding: utf-8 -*-
#
# Copyright © 2012 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

import os
import sys
import mock
import unittest
import shutil

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)) + "/../../../src/")
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)) + "/../../../plugins/importers/")
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)) + "/../../common")
import importer_mocks
import tempfile

from yum_importer import errata
from yum_importer import importer_rpm
from yum_importer.importer import YumImporter

from pulp.plugins.model import Repository, Unit
from pulp.server.db.model.repository import RepoContentUnit
from pulp_rpm.common.ids import TYPE_ID_RPM, TYPE_ID_IMPORTER_YUM, TYPE_ID_ERRATA
import rpm_support_base


class TestErrata(rpm_support_base.PulpRPMTests):

    def setUp(self):
        super(TestErrata, self).setUp()
        self.temp_dir = tempfile.mkdtemp()

        self.working_dir = os.path.join(self.temp_dir, "working")
        os.makedirs(self.working_dir)
        self.repo_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), "../data",
                                     "test_repo")
        self.data_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), "../data")

        self.pkg_dir = os.path.join(self.temp_dir, "packages")

    def tearDown(self):
        super(TestErrata, self).tearDown()
        self.clean()

    def clean(self):
        shutil.rmtree(self.temp_dir)

    def test_metadata(self):
        metadata = YumImporter.metadata()
        self.assertEquals(metadata["id"], TYPE_ID_IMPORTER_YUM)
        self.assertTrue(TYPE_ID_ERRATA in metadata["types"])

    def test_errata_sync(self):
        feed_url = "http://example.com/test_repo/"
        importer = YumImporter()
        repo = mock.Mock(spec=Repository)
        repo.working_dir = self.working_dir
        repo.id = "test_repo"
        sync_conduit = importer_mocks.get_sync_conduit()
        config = importer_mocks.get_basic_config(feed_url=feed_url)
        self.simulate_sync(repo, self.repo_dir)
        importer_errata = errata.ImporterErrata()
        status, summary, details = importer_errata.sync(repo, sync_conduit, config)
        self.assertTrue(status)
        self.assertTrue(summary is not None)
        self.assertTrue(details is not None)

        self.assertEquals(summary["num_new_errata"], 52)
        self.assertEquals(summary["num_existing_errata"], 0)
        self.assertEquals(summary["num_orphaned_errata"], 0)

        self.assertEquals(details["num_bugfix_errata"], 36)
        self.assertEquals(details["num_security_errata"], 7)
        self.assertEquals(details["num_enhancement_errata"], 9)

    def test_errata_sync_with_repos_that_share_upstream_url(self):
        # This test is for https://bugzilla.redhat.com/show_bug.cgi?id=870495
        feed_url = "http://example.com/test_repo/"

        # Set up repo_1 and sync it
        importer_1 = YumImporter()
        repo_1 = mock.Mock(spec=Repository)
        repo_1.working_dir = self.working_dir
        repo_1.id = "test_repo_1"
        sync_conduit_1 = importer_mocks.get_sync_conduit()
        config_1 = importer_mocks.get_basic_config(feed_url=feed_url)
        self.simulate_sync(repo_1, self.repo_dir)
        importer_errata_1 = errata.ImporterErrata()
        status_1, summary_1, details_1 = importer_errata_1.sync(repo_1, sync_conduit_1, config_1)
        self.assertTrue(status_1)
        self.assertTrue(summary_1 is not None)
        self.assertTrue(details_1 is not None)
        self.assertEquals(summary_1["num_new_errata"], 52)
        self.assertEquals(summary_1["num_existing_errata"], 0)
        self.assertEquals(summary_1["num_orphaned_errata"], 0)
        self.assertEquals(details_1["num_bugfix_errata"], 36)
        self.assertEquals(details_1["num_security_errata"], 7)
        self.assertEquals(details_1["num_enhancement_errata"], 9)
        # We should have called save_unit() once for each errata, in sync().
        self.assertEqual(len(sync_conduit_1.save_unit.mock_calls), 52)

        # Now let's set up another repo with the same URL, and then sync. We should get the same
        # errata.
        importer_2 = YumImporter()
        repo_2 = mock.Mock(spec=Repository)
        working_dir_2 = os.path.join(self.temp_dir, "working_2")
        os.makedirs(working_dir_2)
        repo_2.working_dir = working_dir_2
        repo_2.id = "test_repo_2"
        unit_key = {'id': "RHBA-2007:0112"}
        metadata = {'updated' : "2007-03-14 00:00:00",
                    'pkglist': [{'name': 'RHEL Virtualization (v. 5 for 32-bit x86)'}]}
        existing_units = [Unit(TYPE_ID_ERRATA, unit_key, metadata, '')]
        existing_units[0].updated = metadata['updated']
        sync_conduit_2 = importer_mocks.get_sync_conduit(existing_units=existing_units)
        config_2 = importer_mocks.get_basic_config(feed_url=feed_url)
        self.simulate_sync(repo_2, self.repo_dir)
        importer_errata_2 = errata.ImporterErrata()
        status_2, summary_2, details_2 = importer_errata_2.sync(repo_2, sync_conduit_2, config_2)
        self.assertTrue(status_2)
        self.assertTrue(summary_2 is not None)
        self.assertTrue(details_2 is not None)
        self.assertEquals(summary_2["num_new_errata"], 51)
        self.assertEquals(summary_2["num_existing_errata"], 1)
        self.assertEquals(summary_2["num_orphaned_errata"], 0)
        self.assertEquals(details_2["num_bugfix_errata"], 35)
        self.assertEquals(details_2["num_security_errata"], 7)
        self.assertEquals(details_2["num_enhancement_errata"], 9)

        # There should be the same number of calls to save_unit() as there are errata,
        # because sync() calls it once for each of the 51 new erratum, and get_new_errata_units()
        # also calls it once for the one errata that already existed
        self.assertEqual(len(sync_conduit_2.save_unit.mock_calls), 52)

    def test_get_available_errata(self):
        errata_items_found = errata.get_available_errata(self.repo_dir)
        self.assertEqual(52, len(errata_items_found))

    def test_get_existing_errata(self):
        unit_key = dict()
        unit_key['id'] = "RHBA-2007:0112"
        metadata = {'updated' : "2007-03-13 00:00:00"}
        existing_units = [Unit(TYPE_ID_ERRATA, unit_key, metadata, '')]
        sync_conduit = importer_mocks.get_sync_conduit(existing_units=existing_units)
        created_existing_units = errata.get_existing_errata(sync_conduit)
        self.assertEquals(len(created_existing_units), 1)
        self.assertEquals(len(existing_units), len(created_existing_units))

    def test_new_errata_units(self):
        # existing errata is newer or same as available errata; should skip sync for 1 errata
        available_errata = errata.get_available_errata(self.repo_dir)
        self.assertEqual(52, len(available_errata))
        unit_key = dict()
        unit_key['id'] = "RHBA-2007:0112"
        metadata = {'updated' : "2006-03-13 00:00:00"}
        existing_units = [Unit(TYPE_ID_ERRATA, unit_key, metadata, '')]
        existing_units[0].updated = "2006-03-13 00:00:00"
        sync_conduit = importer_mocks.get_sync_conduit(existing_units=existing_units)
        created_existing_units = errata.get_existing_errata(sync_conduit)
        self.assertEquals(len(created_existing_units), 1)
        self.assertEquals(len(existing_units), len(created_existing_units))
        new_errata, new_units, sync_conduit = errata.get_new_errata_units(available_errata,
                                                                          sync_conduit)
        self.assertEquals(len(available_errata), len(new_errata))

    def test_get_new_errata_units_saves_existing_units(self):
        # This test is for https://bugzilla.redhat.com/show_bug.cgi?id=870495
        available_errata = errata.get_available_errata(self.repo_dir)
        self.assertEqual(52, len(available_errata))
        unit_key = {'id': "RHBA-2007:0112"}
        metadata = {'updated' : "2007-03-14 00:00:00",
                    'pkglist': [{'name': 'RHEL Virtualization (v. 5 for 32-bit x86)'}]}
        existing_units = [Unit(TYPE_ID_ERRATA, unit_key, metadata, '')]
        existing_units[0].updated = metadata['updated']
        sync_conduit = importer_mocks.get_sync_conduit(existing_units=existing_units)
        created_existing_units = errata.get_existing_errata(sync_conduit)
        self.assertEquals(len(created_existing_units), 1)
        self.assertEquals(len(existing_units), len(created_existing_units))
        new_errata, new_units, sync_conduit = errata.get_new_errata_units(available_errata,
                                                                          sync_conduit)
        # The one pre-existing errata makes the number of new errata one less
        self.assertEquals(len(new_errata), len(available_errata) - 1)
        # The one existing unit that we passed in as an existing unit should cause save_unit() to be
        # called one time
        self.assertEqual(len(sync_conduit.save_unit.mock_calls), 1)
        # Assert that save_unit was called with the pre-existing errata
        self.assertEqual(sync_conduit.save_unit.mock_calls[0][1][0], existing_units[0])

    def test_update_errata_units(self):
        # existing errata is older than available; should purge and resync
        available_errata = errata.get_available_errata(self.repo_dir)
        self.assertEqual(52, len(available_errata))
        unit_key = dict()
        unit_key['id'] = "RHBA-2007:0112"
        metadata = {'updated' : "2007-03-13 00:00:00"}
        existing_units = [Unit(TYPE_ID_ERRATA, unit_key, metadata, '')]
        existing_units[0].updated = "2007-03-13 00:00:00"
        sync_conduit = importer_mocks.get_sync_conduit(existing_units=existing_units)
        created_existing_units = errata.get_existing_errata(sync_conduit)
        self.assertEquals(len(created_existing_units), 1)
        new_errata, new_units, sync_conduit = errata.get_new_errata_units(available_errata, sync_conduit)
        self.assertEquals(len(available_errata), len(new_errata))

    def test_link_errata_rpm_units(self):
        feed_url = "file://%s/test_errata_local_sync/" % self.data_dir
        repo = mock.Mock(spec=Repository)
        repo.working_dir = self.working_dir
        repo.id = "test_errata_local_sync"
        repo.checksumtype = 'sha'
        sync_conduit = importer_mocks.get_sync_conduit(type_id=TYPE_ID_RPM, existing_units=[], pkg_dir=self.pkg_dir)
        config = importer_mocks.get_basic_config(feed_url=feed_url)
        importerRPM = importer_rpm.ImporterRPM()
        status, summary, details = importerRPM.sync(repo, sync_conduit, config)
        metadata = {'updated' : "2007-03-13 00:00:00"}
        unit_key_a = {'id' : '','name' :'patb', 'version' :'0.1', 'release' : '2', 'epoch':'0', 'arch' : 'noarch', 'checksumtype' : 'sha',
                      'checksum': '017c12050a97cf6095892498750c2a39d2bf535e'}
        unit_key_b = {'id' : '', 'name' :'emoticons', 'version' :'0.1', 'release' :'2', 'epoch':'0','arch' : 'noarch', 'checksumtype' :'sha',
                      'checksum' : '663c89b0d29bfd5479d8736b716d50eed9495dbb'}

        existing_units = []
        for unit in [unit_key_a, unit_key_b]:
            existing_units.append(Unit(TYPE_ID_RPM, unit, metadata, ''))
        sync_conduit = importer_mocks.get_sync_conduit(type_id=TYPE_ID_RPM, existing_units=existing_units, pkg_dir=self.pkg_dir)
        importerErrata = errata.ImporterErrata()
        status, summary, details = importerErrata.sync(repo, sync_conduit, config)
        self.assertEquals(len(details['link_report']['linked_units']), 2)

    def test_link_errata_rpm_units_with_bad_data(self):
        # Tests against EPEL Fedora 6 errata info which lacks checksum info for package list entries
        repo_src_dir = os.path.join(self.data_dir, "test_epel_errata_info")
        feed_url = "file://%s/" % repo_src_dir
        repo = mock.Mock(spec=Repository)
        repo.working_dir = self.working_dir
        repo.id = "test_link_errata_rpm_units_with_bad_data"
        repo.checksumtype = 'sha'
        self.simulate_sync(repo, repo_src_dir)
        sync_conduit = importer_mocks.get_sync_conduit(type_id=TYPE_ID_RPM, existing_units=[], pkg_dir=self.pkg_dir)
        config = importer_mocks.get_basic_config(feed_url=feed_url)
        caught_exception = False
        try:
            importerErrata = errata.ImporterErrata()
            status, summary, details = importerErrata.sync(repo, sync_conduit, config)
        except Exception, e:
            caught_exception = True
        self.assertFalse(caught_exception)
