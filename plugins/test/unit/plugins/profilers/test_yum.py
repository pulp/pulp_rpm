from copy import deepcopy
import os
import shutil
import tempfile

import mock


from pulp.plugins.model import Consumer, Unit
from pulp.plugins.profiler import InvalidUnitsRequested

from pulp_rpm.common.ids import TYPE_ID_ERRATA, TYPE_ID_RPM, TYPE_ID_MODULEMD
from pulp_rpm.devel import rpm_support_base
from pulp_rpm.devel.skip import skip_broken
from pulp_rpm.plugins.profilers.yum import entry_point, YumProfiler
from pulp_rpm.yum_plugin import updateinfo
import profiler_mocks


DATA_DIR = os.path.join(os.path.dirname(__file__), '../../../data/')


class TestYumProfiler(rpm_support_base.PulpRPMTests):
    """
    The YumProfiler used to be two different profilers - one for RPMs and one for Errata. It was
    combined, and this test suite ensures that the methods that only apply to one of the two types
    are not applied to both.
    """

    def test_entry_point(self):
        plugin, config = entry_point()

        self.assertEqual(plugin, YumProfiler)
        self.assertEqual(config, {})

    def test_install_units_with_rpms(self):
        """
        Make sure install_units() can handle being given RPMs.
        """
        rpms = [{'name': 'rpm_1', 'type_id': TYPE_ID_RPM},
                {'name': 'rpm_2', 'type_id': TYPE_ID_RPM}]
        profiler = YumProfiler()

        translated_units = profiler.install_units('consumer', deepcopy(rpms), None, None,
                                                  'conduit')

        # The RPMs should be unaltered
        self.assertEqual(translated_units, rpms)

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
        self.data_dir = DATA_DIR
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
        unit_key = {"name": name, "epoch": epoch, "version": version, "release": release,
                    "arch": arch, "checksum": checksum, "checksumtype": checksumtype}
        return {"unit-key": unit_key}

    def create_profile_entry(self, name, epoch, version, release, arch, vendor):
        return {"name": name, "epoch": epoch, "version": version, "release": release,
                "arch": arch, "vendor": vendor}

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
        return {TYPE_ID_RPM: [foo, bar]}

    def get_test_profile_been_updated(self, arch="x86_64"):
        foo = self.create_profile_entry("emoticons", 0, "0.1", "2", arch, "Test Vendor")
        bar = self.create_profile_entry("patb", 0, "0.1", "2", arch, "Test Vendor")
        return {TYPE_ID_RPM: [foo, bar]}

    @skip_broken
    @mock.patch('pulp_rpm.plugins.db.models.Errata.get_unique_pkglists')
    def test_unit_not_applicable_not_in_repo(self, m_get_unique_pkglists):
        # Errata refers to RPMs which ARE part of our test consumer's profile,
        # but are not in the repo.
        errata_obj = self.get_test_errata_object()
        errata_unit = Unit(TYPE_ID_ERRATA, {"id": errata_obj["id"]}, errata_obj, None)
        errata_unit.id = 'an_errata'
        errata_rpms = errata_obj.pkglist[0]['packages']
        m_get_unique_pkglists.return_value = [[errata_rpms]]
        test_repo = profiler_mocks.get_repo("test_repo_id")

        prof = YumProfiler()
        conduit = profiler_mocks.get_profiler_conduit(repo_units=[errata_unit],
                                                      repo_bindings=[test_repo],
                                                      errata_rpms=errata_rpms)
        unit_profile = self.test_consumer.profiles[TYPE_ID_RPM]
        bound_repo_id = "test_repo_id"
        report_list = prof.calculate_applicable_units(unit_profile, bound_repo_id, None, conduit)
        self.assertEqual(report_list, {TYPE_ID_RPM: [], TYPE_ID_ERRATA: []})

    @skip_broken
    @mock.patch('pulp_rpm.plugins.db.models.Errata.get_unique_pkglists')
    def test_unit_applicable(self, m_get_unique_pkglists):
        # Errata refers to RPMs which ARE part of our test consumer's profile,
        # AND in the repo.
        errata_obj = self.get_test_errata_object()
        errata_unit = Unit(TYPE_ID_ERRATA, {"id": errata_obj["id"]}, errata_obj, None)
        errata_unit.id = 'an_errata'
        errata_rpms = errata_obj.pkglist[0]['packages']
        m_get_unique_pkglists.return_value = [[errata_rpms]]

        rpm_unit_key = self.create_profile_entry("emoticons", 0, "0.1", "2", "x86_64",
                                                 "Test Vendor")
        rpm_unit = Unit(TYPE_ID_RPM, rpm_unit_key, {}, None)
        # Let's give it an id, so we can assert for it later
        rpm_unit.id = 'a_test_id'

        test_repo = profiler_mocks.get_repo("test_repo_id")

        prof = YumProfiler()
        conduit = profiler_mocks.get_profiler_conduit(repo_units=[errata_unit, rpm_unit],
                                                      repo_bindings=[test_repo],
                                                      errata_rpms=errata_rpms)
        unit_profile = self.test_consumer.profiles[TYPE_ID_RPM]
        bound_repo_id = "test_repo_id"
        report_list = prof.calculate_applicable_units(unit_profile, bound_repo_id, None, conduit)
        self.assertEqual(report_list, {TYPE_ID_RPM: ['a_test_id'], TYPE_ID_ERRATA: ['an_errata']})

    @skip_broken
    @mock.patch('pulp_rpm.plugins.db.models.Errata.get_unique_pkglists')
    def test_unit_applicable_same_name_diff_arch(self, m_get_unique_pkglists):
        # Errata refers to RPMs that are x86_64, the test consumer is i386
        # the rpms installed share the same name as the errata, but the client arch is different
        # so this errata is marked as unapplicable
        errata_obj = self.get_test_errata_object()
        errata_unit = Unit(TYPE_ID_ERRATA, {"id": errata_obj["id"]}, errata_obj, None)
        errata_rpms = errata_obj.pkglist[0]['packages']
        m_get_unique_pkglists.return_value = [[errata_rpms]]
        test_repo = profiler_mocks.get_repo("test_repo_id")

        prof = YumProfiler()
        conduit = profiler_mocks.get_profiler_conduit(repo_units=[errata_unit],
                                                      repo_bindings=[test_repo],
                                                      errata_rpms=errata_rpms)
        unit_profile = self.test_consumer_i386.profiles[TYPE_ID_RPM]
        bound_repo_id = "test_repo_id"
        report_list = prof.calculate_applicable_units(unit_profile, bound_repo_id, None, conduit)
        self.assertEqual(report_list, {TYPE_ID_RPM: [], TYPE_ID_ERRATA: []})

    @skip_broken
    @mock.patch('pulp_rpm.plugins.db.models.Errata.get_unique_pkglists')
    def test_unit_applicable_updated_rpm_already_installed(self, m_get_unique_pkglists):
        # Errata refers to RPMs already installed, i.e. the consumer has these exact NEVRA already
        errata_obj = self.get_test_errata_object()
        errata_unit = Unit(TYPE_ID_ERRATA, {"id": errata_obj["id"]}, errata_obj, None)
        errata_rpms = errata_obj.pkglist[0]['packages']
        m_get_unique_pkglists.return_value = [[errata_rpms]]
        test_repo = profiler_mocks.get_repo("test_repo_id")

        prof = YumProfiler()
        conduit = profiler_mocks.get_profiler_conduit(repo_units=[errata_unit],
                                                      repo_bindings=[test_repo],
                                                      errata_rpms=errata_rpms)
        unit_profile = self.test_consumer_been_updated.profiles[TYPE_ID_RPM]
        bound_repo_id = "test_repo_id"
        report_list = prof.calculate_applicable_units(unit_profile, bound_repo_id, None, conduit)
        self.assertEqual(report_list, {TYPE_ID_RPM: [], TYPE_ID_ERRATA: []})

    @skip_broken
    @mock.patch('pulp_rpm.plugins.db.models.Errata.get_unique_pkglists')
    def test_unit_applicable_false(self, m_get_unique_pkglists):
        # Errata refers to RPMs which are NOT part of our test consumer's profile
        errata_obj = self.get_test_errata_object_unrelated()
        errata_unit = Unit(TYPE_ID_ERRATA, {"id": errata_obj["id"]}, errata_obj, None)
        errata_rpms = errata_obj.pkglist[0]['packages']
        m_get_unique_pkglists.return_value = [[errata_rpms]]
        test_repo = profiler_mocks.get_repo("test_repo_id")

        prof = YumProfiler()
        conduit = profiler_mocks.get_profiler_conduit(repo_units=[errata_unit],
                                                      repo_bindings=[test_repo],
                                                      errata_rpms=errata_rpms)
        unit_profile = self.test_consumer.profiles[TYPE_ID_RPM]
        bound_repo_id = "test_repo_id"
        report_list = prof.calculate_applicable_units(unit_profile, bound_repo_id, None, conduit)
        self.assertEqual(report_list, {TYPE_ID_ERRATA: [], TYPE_ID_RPM: []})

    def test_install_units_no_profile(self):
        """
        Test the InvalidUnitsRequested is raised when the consumer has no RPM profile.
        """
        config = {}
        options = {}
        conduit = mock.Mock()
        consumer = mock.Mock(profiles={'OTHER': {}})
        units = [{'type_id': TYPE_ID_ERRATA}]
        self.assertRaises(
            InvalidUnitsRequested,
            YumProfiler.install_units,
            consumer,
            units,
            options,
            config,
            conduit)

    def test_create_nevra(self):
        rpm = {'name': "foo",
               'epoch': 0,
               'version': '1',
               'release': '5',
               'arch': '8088',
               'extra_field': 'extra'}

        result = YumProfiler._create_nevra(rpm)
        self.assertEquals(result, ('foo', '0', '1', '5', '8088'))


class TestYumProfilerRPM(rpm_support_base.PulpRPMTests):
    """
    Test the YumProfiler class with RPM content.
    """

    def setUp(self):
        super(TestYumProfilerRPM, self).setUp()
        self.data_dir = DATA_DIR
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
        unit_key = {"name": name, "epoch": epoch, "version": version, "release": release,
                    "arch": arch, "checksum": checksum, "checksumtype": checksumtype}
        return {"unit-key": unit_key}

    def create_profile_entry(self, name, epoch, version, release, arch, vendor):
        return {"name": name, "epoch": epoch, "version": version, "release": release,
                "arch": arch, "vendor": vendor}

    def get_test_profile(self, arch="x86_64"):
        foo = self.create_profile_entry("emoticons", 0, "0.0.1", "1", arch, "Test Vendor")
        bar = self.create_profile_entry("patb", 0, "0.0.1", "1", arch, "Test Vendor")
        return {TYPE_ID_RPM: [foo, bar]}

    def get_test_profile_been_updated(self, arch="x86_64"):
        foo = self.create_profile_entry("emoticons", 0, "0.1", "2", arch, "Test Vendor")
        bar = self.create_profile_entry("patb", 0, "0.1", "2", arch, "Test Vendor")
        return {TYPE_ID_RPM: [foo, bar]}

    def get_test_profile_with_duplicate_packages(self, arch="x86_64"):
        foo = self.create_profile_entry("emoticons", 0, "0.0.1", "1", arch, "Test Vendor")
        bar = self.create_profile_entry("patb", 0, "0.0.1", "1", arch, "Test Vendor")
        newer_bar = self.create_profile_entry("patb", 0, "0.0.2", "1", arch, "Test Vendor")
        return {TYPE_ID_RPM: [foo, newer_bar, bar]}

    def test_metadata(self):
        """
        Test the metadata() method.
        """
        data = YumProfiler.metadata()
        self.assertTrue("id" in data)
        self.assertEquals(data['id'], YumProfiler.TYPE_ID)
        self.assertTrue("display_name" in data)
        # Make sure the advertised types are RPM, Modulemd and Errata
        self.assertTrue('types' in data)
        self.assertEqual(len(data['types']), 3)
        self.assertTrue(TYPE_ID_RPM in data["types"])
        self.assertTrue(TYPE_ID_ERRATA in data["types"])
        self.assertTrue(TYPE_ID_MODULEMD in data["types"])

    @skip_broken
    def test_form_lookup_table(self):
        """
        Test that form_lookup_table creates a table with the latest rpm in the profile as a value
        corresponding to the rpm name and arch.
        """
        test_profile = self.get_test_profile_with_duplicate_packages()
        consumer_lookup = YumProfiler._form_lookup_table(test_profile[TYPE_ID_RPM])
        self.assertEqual(len(consumer_lookup), 2)
        self.assertEqual(consumer_lookup['patb x86_64'],
                         self.create_profile_entry("patb", 0, "0.0.2", "1", "x86_64",
                                                   "Test Vendor"))

    @skip_broken
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

    @skip_broken
    def test_rpm_applicable_with_profile_containing_duplicate_packages(self):
        """
        If a consumer profile contains multiple rpms with same name and arch (eg. in case of
        kernel rpms), make sure that the applicability calculations take into consideration
        the newest rpm installed.
        """
        consumer_profile = self.get_test_profile_with_duplicate_packages()
        test_consumer_lookup = YumProfiler._form_lookup_table(consumer_profile[TYPE_ID_RPM])
        rpm = self.create_profile_entry("patb", 0, "0.0.2", "1", "x86_64", "Test Vendor")
        yum_profiler = YumProfiler()
        applicable = yum_profiler._is_rpm_applicable(rpm, test_consumer_lookup)
        self.assertFalse(applicable)
        newer_rpm = self.create_profile_entry("patb", 0, "0.0.3", "1", "x86_64", "Test Vendor")
        applicable = yum_profiler._is_rpm_applicable(newer_rpm, test_consumer_lookup)
        self.assertTrue(applicable)

    @skip_broken
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
        unit_profile = self.test_consumer.profiles[TYPE_ID_RPM]
        bound_repo_id = "test_repo_id"
        report_list = prof.calculate_applicable_units(unit_profile, bound_repo_id, None, conduit)
        self.assertEqual(report_list, {TYPE_ID_RPM: [rpm_unit.id], TYPE_ID_ERRATA: []})

    @skip_broken
    def test_unit_applicable_same_name_diff_arch(self):
        rpm_unit_key = self.create_profile_entry("emoticons", 0, "0.1", "2", "x86_64",
                                                 "Test Vendor")
        rpm_unit = Unit(TYPE_ID_RPM, rpm_unit_key, {}, None)
        test_repo = profiler_mocks.get_repo("test_repo_id")
        conduit = profiler_mocks.get_profiler_conduit(repo_units=[rpm_unit],
                                                      repo_bindings=[test_repo])

        prof = YumProfiler()
        unit_profile = self.test_consumer_i386.profiles[TYPE_ID_RPM]
        bound_repo_id = "test_repo_id"
        report_list = prof.calculate_applicable_units(unit_profile, bound_repo_id, None, conduit)
        self.assertEqual(report_list, {TYPE_ID_RPM: [], TYPE_ID_ERRATA: []})

    @skip_broken
    def test_unit_applicable_updated_rpm_already_installed(self):
        rpm_unit_key = self.create_profile_entry("emoticons", 0, "0.1", "2", "x86_64",
                                                 "Test Vendor")
        rpm_unit = Unit(TYPE_ID_RPM, rpm_unit_key, {}, None)
        test_repo = profiler_mocks.get_repo("test_repo_id")
        conduit = profiler_mocks.get_profiler_conduit(repo_units=[rpm_unit],
                                                      repo_bindings=[test_repo])

        prof = YumProfiler()
        unit_profile = self.test_consumer_been_updated.profiles[TYPE_ID_RPM]
        bound_repo_id = "test_repo_id"
        report_list = prof.calculate_applicable_units(unit_profile, bound_repo_id, None, conduit)
        self.assertEqual(report_list, {TYPE_ID_RPM: [], TYPE_ID_ERRATA: []})

    @skip_broken
    def test_unit_applicable_false(self):
        rpm_unit_key = self.create_profile_entry("bla-bla", 0, "0.1", "2", "x86_64", "Test Vendor")
        rpm_unit = Unit(TYPE_ID_RPM, rpm_unit_key, {}, None)
        test_repo = profiler_mocks.get_repo("test_repo_id")
        conduit = profiler_mocks.get_profiler_conduit(repo_units=[rpm_unit],
                                                      repo_bindings=[test_repo])

        prof = YumProfiler()
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
