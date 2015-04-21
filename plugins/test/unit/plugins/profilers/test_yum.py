from copy import deepcopy
import os
import shutil
import tempfile

import mock

from pulp.plugins.model import Consumer, Unit
from pulp.plugins.profiler import InvalidUnitsRequested

from pulp_rpm.common.ids import TYPE_ID_ERRATA, TYPE_ID_RPM
from pulp_rpm.devel import rpm_support_base
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
    @mock.patch('pulp_rpm.plugins.profilers.yum.YumProfiler._rpms_applicable_to_consumer')
    def test__translate_erratum_returns_unit_keys(self, _rpms_applicable_to_consumer):
        """
        The agent handler is expecting to be given a unit key, and we had a bug[0] wherein it was
        being given only 'name' in the unit key, with all of the other "EVRA" fields being written
        into it. This test asserts that the first element of the return value of the
        _translate_erratum() method has full unit keys.

        [0] https://bugzilla.redhat.com/show_bug.cgi?id=1097434
        """
        unit = mock.MagicMock()
        repo_ids = ['repo_1', 'repo_2']
        consumer = mock.MagicMock()
        conduit = mock.MagicMock()
        # Mock there being an applicable RPM
        applicable_unit_key = {'name': 'a_name', 'epoch': '0', 'version': '2.0.1', 'release': '2',
                               'arch': 'x86_64'}
        _rpms_applicable_to_consumer.return_value = ([applicable_unit_key], mock.MagicMock())

        rpms, details = YumProfiler._translate_erratum(unit, repo_ids, consumer, conduit)

        expected_rpms = [{'unit_key': applicable_unit_key, 'type_id': TYPE_ID_RPM}]
        self.assertEqual(rpms, expected_rpms)

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

        translated_units  = profiler.install_units('consumer', deepcopy(rpms), None, None,
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

    def test_get_rpms_from_errata_no_epoch(self):
        """
        Test that we default to '0' for the epoch if one doesn't exist.
        """
        errata_obj = self.get_test_errata_object(eid='RHEA-2010:8888')
        errata_unit = Unit(TYPE_ID_ERRATA, {"id": errata_obj["id"]}, errata_obj, None)
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
            self.assertTrue('epoch' in r)
            self.assertTrue(r['epoch'] == '0')

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

    def test_unit_not_applicable_not_in_repo(self):
        # Errata refers to RPMs which ARE part of our test consumer's profile,
        # but are not in the repo.
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
        self.assertEqual(report_list, {TYPE_ID_RPM: [], TYPE_ID_ERRATA: []})

    def test_unit_applicable(self):
        # Errata refers to RPMs which ARE part of our test consumer's profile,
        # AND in the repo.
        errata_obj = self.get_test_errata_object()
        errata_unit = Unit(TYPE_ID_ERRATA, {"id":errata_obj["id"]}, errata_obj, None)
        errata_unit.id = 'an_errata'

        rpm_unit_key = self.create_profile_entry("emoticons", 0, "0.1", "2", "x86_64",
                                                 "Test Vendor")
        rpm_unit = Unit(TYPE_ID_RPM, rpm_unit_key, {}, None)
        # Let's give it an id, so we can assert for it later
        rpm_unit.id = 'a_test_id'

        test_repo = profiler_mocks.get_repo("test_repo_id")

        prof = YumProfiler()
        errata_rpms = prof._get_rpms_from_errata(errata_unit)
        conduit = profiler_mocks.get_profiler_conduit(repo_units=[errata_unit, rpm_unit],
                                                      repo_bindings=[test_repo],
                                                      errata_rpms=errata_rpms)
        unit_type_id = TYPE_ID_ERRATA
        unit_profile = self.test_consumer.profiles[TYPE_ID_RPM]
        bound_repo_id = "test_repo_id"
        report_list = prof.calculate_applicable_units(unit_profile, bound_repo_id, None, conduit)
        self.assertEqual(report_list, {TYPE_ID_RPM: ['a_test_id'], TYPE_ID_ERRATA: ['an_errata']})

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
        """
        Verify that all available packages in the erratum are installed

        In this test, there are two packages in the erratum, and both are
        available to the consumer. Thus, both should be installed.
        """
        repo_id = "test_repo_id"
        errata_obj = self.get_test_errata_object()
        errata_unit = Unit(TYPE_ID_ERRATA, {"id":errata_obj["id"]}, errata_obj, None)
        existing_units = [errata_unit]
        test_repo = profiler_mocks.get_repo(repo_id)

        # create two RPM units that match what is in the erratum
        rpm_units = []
        rpm_unit_key_1 = self.create_profile_entry("emoticons", 0, "0.1", "2", "x86_64",
                                                   "Test Vendor")
        rpm_units.append(Unit(TYPE_ID_RPM, rpm_unit_key_1, {}, None))

        rpm_unit_key_2 = self.create_profile_entry("patb", 0, "0.1", "2", "x86_64", "Test Vendor")
        rpm_units.append(Unit(TYPE_ID_RPM, rpm_unit_key_2, {}, None))

        existing_units += rpm_units

        conduit = profiler_mocks.get_profiler_conduit(existing_units=existing_units,
                                                      repo_bindings=[test_repo],
                                                      repo_units=rpm_units)


        example_errata = {"unit_key":errata_unit.unit_key, "type_id":TYPE_ID_ERRATA}
        prof = YumProfiler()
        translated_units  = prof.install_units(self.test_consumer, [example_errata], None, None,
                                               conduit)
        # check repo_id passed to the conduit get_units()
        self.assertEqual(conduit.get_units.call_args[0][0].id, repo_id)
        # check unit association criteria passed to the conduit get_units()
        self.assertEqual(conduit.get_units.call_args_list[0][0][1].type_ids, [TYPE_ID_ERRATA])
        self.assertEqual(conduit.get_units.call_args_list[0][0][1].unit_filters,
                        errata_unit.unit_key)
        # validate translated units
        self.assertEqual(len(translated_units), 2)
        expected = prof._get_rpms_from_errata(errata_unit)
        for u in translated_units:
            rpm_unit_key = u["unit_key"]
            self.assertTrue(rpm_unit_key in expected)

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

    def test_install_units_unit_not_in_repo(self):
        """
        This tests that if an erratum unit is requested to be installed, we do
        not attempt to install any RPM units that are not available in repos.

        For example, if an erratum contains packages for RHEL6 and RHEL7, we do
        not want to ask a RHEL6 consumer to install RHEL7 packages that are
        unavailable on that host.

        This is a related issue to errata applicability but is slightly
        different since the API caller wants to install a particular erratum, and is
        not trying to determine which errata are applicable.

        Note also that RHEA-2014:9999 has emoticons-0.1 and patb-0.1 in
        different package collections; this is atypical and would likely not be
        seen in the wild. I set it up like this to ensure the package list from
        the erratum was being flattened during comparisons.

        More detail is available in https://pulp.plan.io/issues/770
        """
        repo_id = "test_repo_id"

        # this erratum has four RPMs but only two are available
        errata_obj = self.get_test_errata_object(eid='RHEA-2014:9999')
        errata_unit = Unit(TYPE_ID_ERRATA, {"id":errata_obj["id"]}, errata_obj, None)
        existing_units = [errata_unit]
        test_repo = profiler_mocks.get_repo(repo_id)

        # create two RPM units that match what is in the erratum. There are
        # higher versioned RPMs in the erratum that are not available; these
        # should not be installed.

        rpm_units = []
        rpm_unit_key_1 = self.create_profile_entry("emoticons", 0, "0.1", "2", "x86_64",
                                                   "Test Vendor")
        rpm_units.append(Unit(TYPE_ID_RPM, rpm_unit_key_1, {}, None))

        rpm_unit_key_2 = self.create_profile_entry("patb", 0, "0.1", "2", "x86_64", "Test Vendor")
        rpm_units.append(Unit(TYPE_ID_RPM, rpm_unit_key_2, {}, None))

        existing_units += rpm_units

        conduit = profiler_mocks.get_profiler_conduit(existing_units=existing_units,
                                                      repo_bindings=[test_repo],
                                                      repo_units=rpm_units)

        def mocked_get_units(repo_id, criteria=None):
            """
            Override the default get_units in profiler_mocks.

            This method is specific to this particular unit test. The default
            get_units() in profiler_mocks only checks the criteria's type_id and not any
            other fields.

            :param repo_id: repo ID (unused)
            :type  repo_id: not used
            :param criteria: unit association criteria
            :type  criteria: pulp.server.db.model.criteria.UnitAssociationCriteria

            """
            if TYPE_ID_ERRATA in criteria.type_ids:
                return [errata_unit]
            elif criteria['unit_filters']['name'] == 'emoticons' and \
                 criteria['unit_filters']['version'] == '0.1':
                    return [rpm_units[0]]
            elif criteria['unit_filters']['name'] == 'patb' and \
                 criteria['unit_filters']['version'] == '0.1':
                    return [rpm_units[1]]
            else:
                return []

        conduit.get_units.side_effect = mocked_get_units

        example_errata = {"unit_key":errata_unit.unit_key, "type_id":TYPE_ID_ERRATA}
        prof = YumProfiler()
        translated_units  = prof.install_units(self.test_consumer, [example_errata], None, None,
                                               conduit)
        # check repo_id passed to the conduit get_units()
        self.assertEqual(conduit.get_units.call_args_list[0][0][0].id, repo_id)
        # validate translated units
        self.assertEqual(len(translated_units), 2)
        self.assertEqual(translated_units[0]['unit_key']['filename'], 'patb-0.1-2.x86_64.rpm')
        self.assertEqual(translated_units[1]['unit_key']['filename'], 'emoticons-0.1-2.x86_64.rpm')
        expected = prof._get_rpms_from_errata(errata_unit)
        for u in translated_units:
            rpm_unit_key = u["unit_key"]
            self.assertTrue(rpm_unit_key in expected)

    def test_create_nevra(self):
        rpm = {'name': "foo",
               'epoch': 0,
               'version': '1',
               'release': '5',
               'arch': '8088',
               'extra_field': 'extra'}

        result = YumProfiler._create_nevra(rpm)
        self.assertEquals(result, {'name': 'foo', 'epoch': '0', 'version': '1',
                                   'release': '5', 'arch': '8088'})


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
        self.assertTrue(data.has_key("id"))
        self.assertEquals(data['id'], YumProfiler.TYPE_ID)
        self.assertTrue(data.has_key("display_name"))
        # Make sure the advertised types are RPM and Errata
        self.assertTrue(data.has_key("types"))
        self.assertEqual(len(data['types']), 2)
        self.assertTrue(TYPE_ID_RPM in data["types"])
        self.assertTrue(TYPE_ID_ERRATA in data["types"])

    def test_form_lookup_table(self):
        """
        Test that form_lookup_table creates a table with the latest rpm in the profile as a value
        corresponding to the rpm name and arch.
        """
        test_profile = self.get_test_profile_with_duplicate_packages()
        consumer_lookup = YumProfiler._form_lookup_table(test_profile[TYPE_ID_RPM])
        self.assertEqual(len(consumer_lookup), 2)
        self.assertEqual(consumer_lookup['patb x86_64'],
                         self.create_profile_entry("patb", 0, "0.0.2", "1", "x86_64", "Test Vendor"))

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
