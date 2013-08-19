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

from copy import deepcopy
import mock
import os
import random
import shutil
import sys
import tempfile
import unittest

from pulp.plugins.model import Consumer, Repository, Unit
from pulp.server.db.model.criteria import Criteria
from pulp.server.managers import factory
from pulp.server.managers.consumer.cud import ConsumerManager

from pulp_rpm.common.ids import TYPE_ID_ERRATA, TYPE_ID_RPM
from pulp_rpm.plugins.profilers.yum import YumProfiler
from pulp_rpm.yum_plugin import comps_util, util, updateinfo
import profiler_mocks
import rpm_support_base


class TestYumProfilerCombined(rpm_support_base.PulpRPMTests):
    """
    The YumProfiler used to be two different profilers - one for RPMs and one for Errata. It was
    combined, and this test suite ensures that the methods that only apply to one of the two types
    are not applied to both.
    """
    def test_update_profile_with_errata(self):
        """
        Test the update_profile() method with a presorted profile. It should not alter it at all.
        """
        profile = ['one_errata', 'two_errata', 'three_errata', 'four_errata']
        profiler = YumProfiler()

        # The update_profile() method doesn't use any of the args except for profile and
        # content_type, so we'll just pass in strings for the others
        # This test just asserts that the profile is returned unaltered
        new_profile = profiler.update_profile('consumer', TYPE_ID_ERRATA, deepcopy(profile),
                                              'config')

        self.assertEqual(new_profile, profile)


class TestYumProfilerErrata(rpm_support_base.PulpRPMTests):
    """
    Test the YumProfiler with errata content.
    """
    def setUp(self):
        super(TestYumProfilerErrata, self).setUp()
        self.data_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), "../data")
        self.temp_dir = tempfile.mkdtemp()
        self.working_dir = os.path.join(self.temp_dir, "working")
        if not os.path.exists(self.working_dir):
            os.makedirs(self.working_dir)
        self.updateinfo_xml_path = os.path.join(self.data_dir, "test_errata_install",
                                                "updateinfo.xml")
        self.updateinfo_unrelated_xml_path = os.path.join(self.data_dir, "test_errata_install",
                                                          "updateinfo_nonapplicable.xml")
        self.consumer_id = "test_errata_profiler_consumer_id"
        self.profiles = self.get_test_profile()
        self.test_consumer = Consumer(self.consumer_id, self.profiles)
        # i386 version of consumer to test arch issues
        self.consumer_id_i386 = "%s.i386" % (self.consumer_id)
        self.profiles_i386 = self.get_test_profile(arch="i386")
        self.test_consumer_i386 = Consumer(self.consumer_id_i386, self.profiles_i386)
        # consumer has been updated, and has the updated rpms installed
        self.consumer_id_been_updated = "%s.been_updated" % (self.consumer_id)
        self.profiles_been_updated = self.get_test_profile_been_updated()
        self.test_consumer_been_updated = Consumer(self.consumer_id_been_updated,
                                                   self.profiles_been_updated)

    def tearDown(self):
        super(TestYumProfilerErrata, self).tearDown()
        shutil.rmtree(self.temp_dir)

    def create_rpm_dict(self, name, epoch, version, release, arch, checksum, checksumtype):
        unit_key = {"name":name, "epoch":epoch, "version":version, "release":release, 
                "arch":arch, "checksum":checksum, "checksumtype":checksumtype}
        return {"unit-key":unit_key}

    def create_profile_entry(self, name, epoch, version, release, arch, vendor):
        return {"name":name, "epoch": epoch, "version":version, "release":release, 
                "arch":arch, "vendor":vendor}

    def get_test_errata_object(self, eid='RHEA-2010:9999'):
        errata_from_xml = updateinfo.get_errata(self.updateinfo_xml_path)
        self.assertTrue(len(errata_from_xml) > 0)
        errata = {}
        for e in errata_from_xml:
            errata[e['id']] = e
        self.assertTrue(eid in errata)
        return errata[eid]

    def get_test_errata_object_unrelated(self):
        errata_from_xml = updateinfo.get_errata(self.updateinfo_unrelated_xml_path)
        self.assertTrue(len(errata_from_xml) > 0)
        return errata_from_xml[0]

    def get_test_profile(self, arch="x86_64"):
        foo = self.create_profile_entry("emoticons", 0, "0.1", "1", arch, "Test Vendor")
        bar = self.create_profile_entry("patb", 0, "0.1", "1", arch, "Test Vendor")
        return {TYPE_ID_RPM:[foo, bar]}

    def get_test_profile_been_updated(self, arch="x86_64"):
        foo = self.create_profile_entry("emoticons", 0, "0.1", "2", arch, "Test Vendor")
        bar = self.create_profile_entry("patb", 0, "0.1", "2", arch, "Test Vendor")
        return {TYPE_ID_RPM:[foo, bar]}

    def test_get_rpms_from_errata(self):
        errata_obj = self.get_test_errata_object()
        errata_unit = Unit(TYPE_ID_ERRATA, {"id":errata_obj["id"]}, errata_obj, None)
        prof = YumProfiler()
        rpms = prof._get_rpms_from_errata(errata_unit)
        # Expected data:
        # [{'src': 'xen-3.0.3-80.el5_3.3.src.rpm', 'name': 'emoticons', 
        #   'sum': ('md5', '366bb5e73a5905eacb82c96e0578f92b'), 
        #   'filename': 'emoticons-0.1-2.x86_64.rpm', 'epoch': '0', 
        #   'version': '0.1', 'release': '2', 'arch': 'x86_64'}, 
        # {'src': 'xen-3.0.3-80.el5_3.3.src.rpm', 'name': 'patb', 
        #   'sum': ('md5', 'f3c197a29d9b66c5b65c5d62b25db5b4'), 
        #   'filename': 'patb-0.1-2.x86_64.rpm', 'epoch': '0', 
        #   'version': '0.1', 'release': '2', 'arch': 'x86_64'}]
        self.assertEqual(len(rpms), 2)
        self.assertTrue(rpms[0]["name"] in ['emoticons', 'patb'])
        self.assertTrue(rpms[1]["name"] in ['emoticons', 'patb'])
        for r in rpms:
            for key in ["name", "filename", "epoch", "version", "release"]:
                self.assertTrue(r.has_key(key))
                self.assertTrue(r[key])

    def test_rpms_applicable_to_consumer(self):
        errata_rpms = []
        prof = YumProfiler()
        applicable_rpms, old_rpms = prof._rpms_applicable_to_consumer(Consumer("test", {}),
                                                                      errata_rpms)
        self.assertEqual(applicable_rpms, [])
        self.assertEqual(old_rpms, {})

        # Get rpm dictionaries embedded in an errata
        errata_obj = self.get_test_errata_object()
        errata_unit = Unit(TYPE_ID_ERRATA, {"id":errata_obj["id"]}, errata_obj, None)
        errata_rpms = prof._get_rpms_from_errata(errata_unit)
        # Test with 2 newer RPMs in the test errata
        # The consumer has already been configured with a profile containing 'emoticons' and
        # 'patb' rpms
        applicable_rpms, old_rpms = prof._rpms_applicable_to_consumer(self.test_consumer,
                                                                      errata_rpms)
        self.assertTrue(applicable_rpms)
        self.assertTrue(old_rpms)
        self.assertEqual(len(applicable_rpms), 2)
        self.assertTrue(old_rpms.has_key("emoticons x86_64"))
        self.assertEqual("emoticons", old_rpms["emoticons x86_64"]["installed"]["name"])
        self.assertEqual("0.1", old_rpms["emoticons x86_64"]["installed"]["version"])

    def test_unit_applicable_true(self):
        # Errata refers to RPMs which ARE part of our test consumer's profile
        errata_obj = self.get_test_errata_object()
        errata_unit = Unit(TYPE_ID_ERRATA, {"id":errata_obj["id"]}, errata_obj, None)
        errata_unit.id = 'an_errata'
        test_repo = profiler_mocks.get_repo("test_repo_id")

        prof = YumProfiler()
        errata_rpms = prof._get_rpms_from_errata(errata_unit)
        conduit = profiler_mocks.get_profiler_conduit(repo_units=[errata_unit],
                                                      repo_bindings=[test_repo],
                                                      errata_rpms=errata_rpms)
        unit_type_id = TYPE_ID_ERRATA
        unit_profile = self.test_consumer.profiles[TYPE_ID_RPM]
        bound_repo_id = "test_repo_id"
        report_list = prof.calculate_applicable_units(unit_profile, bound_repo_id, None, conduit)
        self.assertEqual(report_list, {TYPE_ID_RPM: [], TYPE_ID_ERRATA: [errata_unit.id]})

    def test_unit_applicable_same_name_diff_arch(self):
        # Errata refers to RPMs that are x86_64, the test consumer is i386
        # the rpms installed share the same name as the errata, but the client arch is different
        # so this errata is marked as unapplicable
        errata_obj = self.get_test_errata_object()
        errata_unit = Unit(TYPE_ID_ERRATA, {"id":errata_obj["id"]}, errata_obj, None)
        test_repo = profiler_mocks.get_repo("test_repo_id")

        prof = YumProfiler()
        errata_rpms = prof._get_rpms_from_errata(errata_unit)
        conduit = profiler_mocks.get_profiler_conduit(repo_units=[errata_unit],
                                                      repo_bindings=[test_repo],
                                                      errata_rpms=errata_rpms)
        unit_type_id = TYPE_ID_ERRATA
        unit_profile = self.test_consumer_i386.profiles[TYPE_ID_RPM]
        bound_repo_id = "test_repo_id"
        report_list = prof.calculate_applicable_units(unit_profile, bound_repo_id, None, conduit)
        self.assertEqual(report_list, {TYPE_ID_RPM: [], TYPE_ID_ERRATA: []})

    def test_unit_applicable_updated_rpm_already_installed(self):
        # Errata refers to RPMs already installed, i.e. the consumer has these exact NEVRA already
        errata_obj = self.get_test_errata_object()
        errata_unit = Unit(TYPE_ID_ERRATA, {"id":errata_obj["id"]}, errata_obj, None)
        test_repo = profiler_mocks.get_repo("test_repo_id")

        prof = YumProfiler()
        errata_rpms = prof._get_rpms_from_errata(errata_unit)
        conduit = profiler_mocks.get_profiler_conduit(repo_units=[errata_unit],
                                                      repo_bindings=[test_repo],
                                                      errata_rpms=errata_rpms)
        unit_type_id = TYPE_ID_ERRATA
        unit_profile = self.test_consumer_been_updated.profiles[TYPE_ID_RPM]
        bound_repo_id = "test_repo_id"
        report_list = prof.calculate_applicable_units(unit_profile, bound_repo_id, None, conduit)
        self.assertEqual(report_list, {TYPE_ID_RPM: [], TYPE_ID_ERRATA: []})

    def test_unit_applicable_false(self):
        # Errata refers to RPMs which are NOT part of our test consumer's profile
        errata_obj = self.get_test_errata_object_unrelated()
        errata_unit = Unit(TYPE_ID_ERRATA, {"id":errata_obj["id"]}, errata_obj, None)
        test_repo = profiler_mocks.get_repo("test_repo_id")

        prof = YumProfiler()
        errata_rpms = prof._get_rpms_from_errata(errata_unit)
        conduit = profiler_mocks.get_profiler_conduit(repo_units=[errata_unit],
                                                      repo_bindings=[test_repo],
                                                      errata_rpms=errata_rpms)
        unit_type_id = TYPE_ID_ERRATA
        unit_profile = self.test_consumer.profiles[TYPE_ID_RPM]
        bound_repo_id = "test_repo_id"
        report_list = prof.calculate_applicable_units(unit_profile, bound_repo_id, None, conduit)
        self.assertEqual(report_list, {TYPE_ID_ERRATA: [], TYPE_ID_RPM: []})

    def test_install_units(self):
        repo_id = "test_repo_id"
        errata_obj = self.get_test_errata_object()
        errata_unit = Unit(TYPE_ID_ERRATA, {"id":errata_obj["id"]}, errata_obj, None)
        existing_units = [errata_unit]
        test_repo = profiler_mocks.get_repo(repo_id)
        conduit = profiler_mocks.get_profiler_conduit(existing_units=existing_units,
                                                      repo_bindings=[test_repo])
        example_errata = {"unit_key":errata_unit.unit_key, "type_id":TYPE_ID_ERRATA}
        prof = YumProfiler()
        translated_units  = prof.install_units(self.test_consumer, [example_errata], None, None,
                                               conduit)
        # check repo_id passed to the conduit get_units()
        self.assertEqual(conduit.get_units.call_args[0][0].id, repo_id)
        # check unit association criteria passed to the conduit get_units()
        self.assertEqual(conduit.get_units.call_args[0][1].type_ids, [TYPE_ID_ERRATA])
        self.assertEqual(conduit.get_units.call_args[0][1].unit_filters, errata_unit.unit_key)
        # validate translated units
        self.assertEqual(len(translated_units), 2)
        expected = []
        for r in prof._get_rpms_from_errata(errata_unit):
            expected_name = "%s-%s:%s-%s.%s" % (r["name"], r["epoch"], r["version"], r["release"],
                                                r["arch"])
            expected.append(expected_name)
        for u in translated_units:
            rpm_name = u["unit_key"]["name"]
            self.assertTrue(rpm_name in expected)


class TestYumProfilerRPM(rpm_support_base.PulpRPMTests):
    """
    Test the YumProfiler class with RPM content.
    """

    def setUp(self):
        super(TestYumProfilerRPM, self).setUp()
        self.data_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), "../data")
        self.temp_dir = tempfile.mkdtemp()
        self.working_dir = os.path.join(self.temp_dir, "working")
        if not os.path.exists(self.working_dir):
            os.makedirs(self.working_dir)
        self.consumer_id = "test_errata_profiler_consumer_id"
        self.profiles = self.get_test_profile()
        self.test_consumer = Consumer(self.consumer_id, self.profiles)
        self.test_consumer_lookup = YumProfiler._form_lookup_table(self.profiles[TYPE_ID_RPM])
        # i386 version of consumer to test arch issues
        self.consumer_id_i386 = "%s.i386" % (self.consumer_id)
        self.profiles_i386 = self.get_test_profile(arch="i386")
        self.test_consumer_i386 = Consumer(self.consumer_id_i386, self.profiles_i386)
        # consumer has been updated, and has the updated rpms installed
        self.consumer_id_been_updated = "%s.been_updated" % (self.consumer_id)
        self.profiles_been_updated = self.get_test_profile_been_updated()
        self.test_consumer_been_updated = Consumer(self.consumer_id_been_updated,
                                                   self.profiles_been_updated)

    def tearDown(self):
        super(TestYumProfilerRPM, self).tearDown()
        shutil.rmtree(self.temp_dir)

    def create_rpm_dict(self, name, epoch, version, release, arch, checksum, checksumtype):
        unit_key = {"name":name, "epoch":epoch, "version":version, "release":release,
                "arch":arch, "checksum":checksum, "checksumtype":checksumtype}
        return {"unit-key":unit_key}

    def create_profile_entry(self, name, epoch, version, release, arch, vendor):
        return {"name":name, "epoch": epoch, "version":version, "release":release, 
                "arch":arch, "vendor":vendor}

    def get_test_profile(self, arch="x86_64"):
        foo = self.create_profile_entry("emoticons", 0, "0.0.1", "1", arch, "Test Vendor")
        bar = self.create_profile_entry("patb", 0, "0.0.1", "1", arch, "Test Vendor")
        return {TYPE_ID_RPM:[foo, bar]}

    def get_test_profile_been_updated(self, arch="x86_64"):
        foo = self.create_profile_entry("emoticons", 0, "0.1", "2", arch, "Test Vendor")
        bar = self.create_profile_entry("patb", 0, "0.1", "2", arch, "Test Vendor")
        return {TYPE_ID_RPM:[foo, bar]}

    def test_metadata(self):
        """
        Test the metadata() method.
        """
        data = YumProfiler.metadata()
        self.assertTrue(data.has_key("id"))
        self.assertEquals(data['id'], YumProfiler.TYPE_ID)
        self.assertTrue(data.has_key("display_name"))
        # Make sure the advertised types are RPM and Errata
        self.assertTrue(data.has_key("types"))
        self.assertEqual(len(data['types']), 2)
        self.assertTrue(TYPE_ID_RPM in data["types"])
        self.assertTrue(TYPE_ID_ERRATA in data["types"])

    def test_rpm_applicable_to_consumer(self):
        rpm = {}
        prof = YumProfiler()
        applicable = prof._is_rpm_applicable(rpm, {})
        self.assertEqual(applicable, False)

        # Test with newer RPM
        # The consumer has already been configured with a profile containing 'emoticons'
        rpm = self.create_profile_entry("emoticons", 0, "0.1", "2", "x86_64", "Test Vendor")
        applicable = prof._is_rpm_applicable(rpm, self.test_consumer_lookup)
        self.assertTrue(applicable)

    def test_unit_applicable_true(self):
        rpm_unit_key = self.create_profile_entry("emoticons", 0, "0.1", "2", "x86_64",
                                                 "Test Vendor")
        rpm_unit = Unit(TYPE_ID_RPM, rpm_unit_key, {}, None)
        # Let's give it an id, so we can assert for it later
        rpm_unit.id = 'a_test_id'
        test_repo = profiler_mocks.get_repo("test_repo_id")
        conduit = profiler_mocks.get_profiler_conduit(repo_units=[rpm_unit],
                                                      repo_bindings=[test_repo])

        prof = YumProfiler()
        unit_type_id = TYPE_ID_RPM
        unit_profile = self.test_consumer.profiles[TYPE_ID_RPM]
        bound_repo_id = "test_repo_id"
        report_list = prof.calculate_applicable_units(unit_profile, bound_repo_id, None, conduit)
        self.assertEqual(report_list, {TYPE_ID_RPM: [rpm_unit.id], TYPE_ID_ERRATA: []})

    def test_unit_applicable_same_name_diff_arch(self):
        rpm_unit_key = self.create_profile_entry("emoticons", 0, "0.1", "2", "x86_64",
                                                 "Test Vendor")
        rpm_unit = Unit(TYPE_ID_RPM, rpm_unit_key, {}, None)
        test_repo = profiler_mocks.get_repo("test_repo_id")
        conduit = profiler_mocks.get_profiler_conduit(repo_units=[rpm_unit],
                                                      repo_bindings=[test_repo])

        prof = YumProfiler()
        unit_type_id = TYPE_ID_RPM
        unit_profile = self.test_consumer_i386.profiles[TYPE_ID_RPM]
        bound_repo_id = "test_repo_id"
        report_list = prof.calculate_applicable_units(unit_profile, bound_repo_id, None, conduit)
        self.assertEqual(report_list, {TYPE_ID_RPM: [], TYPE_ID_ERRATA: []})

    def test_unit_applicable_updated_rpm_already_installed(self):
        rpm_unit_key = self.create_profile_entry("emoticons", 0, "0.1", "2", "x86_64",
                                                 "Test Vendor")
        rpm_unit = Unit(TYPE_ID_RPM, rpm_unit_key, {}, None)
        test_repo = profiler_mocks.get_repo("test_repo_id")
        conduit = profiler_mocks.get_profiler_conduit(repo_units=[rpm_unit],
                                                      repo_bindings=[test_repo])

        prof = YumProfiler()
        unit_type_id = TYPE_ID_RPM
        unit_profile = self.test_consumer_been_updated.profiles[TYPE_ID_RPM]
        bound_repo_id = "test_repo_id"
        report_list = prof.calculate_applicable_units(unit_profile, bound_repo_id, None, conduit)
        self.assertEqual(report_list, {TYPE_ID_RPM: [], TYPE_ID_ERRATA: []})

    def test_unit_applicable_false(self):
        rpm_unit_key = self.create_profile_entry("bla-bla", 0, "0.1", "2", "x86_64", "Test Vendor")
        rpm_unit = Unit(TYPE_ID_RPM, rpm_unit_key, {}, None)
        test_repo = profiler_mocks.get_repo("test_repo_id")
        conduit = profiler_mocks.get_profiler_conduit(repo_units=[rpm_unit],
                                                      repo_bindings=[test_repo])

        prof = YumProfiler()
        unit_type_id = TYPE_ID_RPM
        unit_profile = self.test_consumer.profiles[TYPE_ID_RPM]
        bound_repo_id = "test_repo_id"
        report_list = prof.calculate_applicable_units(unit_profile, bound_repo_id, None, conduit)
        self.assertEqual(report_list, {TYPE_ID_RPM: [], TYPE_ID_ERRATA: []})

    def test_update_profile_presorted_profile(self):
        """
        Test the update_profile() method with a presorted profile. It should not alter it at all.
        """
        profile = [
            {'name': 'Package A', 'epoch': 0, 'version': '1.0.1', 'release': '2.el6',
             'arch': 'x86_64', 'vendor': 'Red Hat, Inc.'},
            {'name': 'Package A', 'epoch': 0, 'version': '1.1.0', 'release': '1.el6',
             'arch': 'x86_64', 'vendor': 'Red Hat, Inc.'},
            {'name': 'Package B', 'epoch': 0, 'version': '2.3.9', 'release': '1.el6',
             'arch': 'x86_64', 'vendor': 'Red Hat, Inc.'},
            {'name': 'Package B', 'epoch': 1, 'version': '1.2.1', 'release': '8.el6',
             'arch': 'x86_64', 'vendor': 'Red Hat, Inc.'},
            {'name': 'Package C', 'epoch': 0, 'version': '1.0.0', 'release': '1.el6',
             'arch': 'x86_64', 'vendor': 'Red Hat, Inc.'},
            {'name': 'Package C', 'epoch': 0, 'version': '1.0.0', 'release': '2.el6',
             'arch': 'x86_64', 'vendor': 'Red Hat, Inc.'},
        ]
        profiler = YumProfiler()

        # The update_profile() method doesn't use any of the args except for profile and
        # content_type, so we'll just pass in strings for the others
        new_profile = profiler.update_profile('consumer', TYPE_ID_RPM, deepcopy(profile), 'config')

        self.assertEqual(new_profile, profile)

    def test_update_profile_sorts_profile(self):
        """
        Test that the update_profile() method sorts the profile.
        """
        profile = [
            {'name': 'Package A', 'epoch': 0, 'version': '1.0.1', 'release': '2.el6',
             'arch': 'x86_64', 'vendor': 'Red Hat, Inc.'},
            {'name': 'Package C', 'epoch': 0, 'version': '1.0.0', 'release': '1.el6',
             'arch': 'x86_64', 'vendor': 'Red Hat, Inc.'},
            {'name': 'Package C', 'epoch': 0, 'version': '1.0.0', 'release': '2.el6',
             'arch': 'x86_64', 'vendor': 'Red Hat, Inc.'},
            {'name': 'Package A', 'epoch': 0, 'version': '1.1.0', 'release': '1.el6',
             'arch': 'x86_64', 'vendor': 'Red Hat, Inc.'},
            {'name': 'Package B', 'epoch': 1, 'version': '1.2.1', 'release': '8.el6',
             'arch': 'x86_64', 'vendor': 'Red Hat, Inc.'},
            {'name': 'Package B', 'epoch': 0, 'version': '2.3.9', 'release': '1.el6',
             'arch': 'x86_64', 'vendor': 'Red Hat, Inc.'},
        ]
        profiler = YumProfiler()

        # The update_profile() method doesn't use any of the args except for profile and
        # content_type, so we'll just pass in strings for the others
        new_profile = profiler.update_profile('consumer', TYPE_ID_RPM, deepcopy(profile), 'config')

        expected_profile = [
            {'name': 'Package A', 'epoch': 0, 'version': '1.0.1', 'release': '2.el6',
             'arch': 'x86_64', 'vendor': 'Red Hat, Inc.'},
            {'name': 'Package A', 'epoch': 0, 'version': '1.1.0', 'release': '1.el6',
             'arch': 'x86_64', 'vendor': 'Red Hat, Inc.'},
            {'name': 'Package B', 'epoch': 0, 'version': '2.3.9', 'release': '1.el6',
             'arch': 'x86_64', 'vendor': 'Red Hat, Inc.'},
            {'name': 'Package B', 'epoch': 1, 'version': '1.2.1', 'release': '8.el6',
             'arch': 'x86_64', 'vendor': 'Red Hat, Inc.'},
            {'name': 'Package C', 'epoch': 0, 'version': '1.0.0', 'release': '1.el6',
             'arch': 'x86_64', 'vendor': 'Red Hat, Inc.'},
            {'name': 'Package C', 'epoch': 0, 'version': '1.0.0', 'release': '2.el6',
             'arch': 'x86_64', 'vendor': 'Red Hat, Inc.'},
        ]
        self.assertEqual(new_profile, expected_profile)
