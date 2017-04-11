from cStringIO import StringIO
from urlparse import urljoin
import copy
import hashlib
import math
import os
import shutil
import tempfile
from xml.etree import ElementTree as ET

import mock
from pulp.common.compat import unittest
import pulp.common.error_codes as platform_error_codes
from pulp.server.exceptions import PulpCodedException

from pulp_rpm.common import ids, constants
from pulp_rpm.devel.skip import skip_broken
from pulp_rpm.plugins import error_codes
from pulp_rpm.plugins.db import models


class TestNonMetadataModel(unittest.TestCase):
    def test_init_no_checksum(self):
        """
        Make sure the class can be instantiated with a checksum and checksumtype set to None. It may
        not be possible to save it this way, but it should be usable as an instance.

        https://pulp.plan.io/issues/1792
        """
        models.NonMetadataPackage(version='1.0.0', release='2', checksumtype=None, checksum=None)


class TestNEVRATuple(unittest.TestCase):
    """Test that the NEVRA namedtuple properly converts to and from dictionaries"""
    pkg_dict_noepoch = {
        'name': 'package',
        'version': '0.0',
        'release': '0',
        'arch': 'pulp',
    }

    # a tuple with correct values in the expected order
    expected = (
        pkg_dict_noepoch['name'],
        '0',
        pkg_dict_noepoch['version'],
        pkg_dict_noepoch['release'],
        pkg_dict_noepoch['arch'],
    )

    def _pkg_dict(self, epoch):
        # package dict builder, DRYs inserting different values for the epoch field
        pkg_dict = self.pkg_dict_noepoch.copy()
        pkg_dict['epoch'] = epoch
        return pkg_dict

    def test_dict_conversion(self):
        """ensure the correct field names are mapped to the correct values"""
        pkg_dict = self._pkg_dict(epoch='0')
        pkg_nevra = models.NEVRA._fromdict(pkg_dict)
        self.assertEqual(pkg_nevra, self.expected)
        self.assertEqual(pkg_nevra._asdict(), pkg_dict)

    def test_dict_conversion_falsey_epoch(self):
        """ensure the special handling for a "falsey" epoch (usually None) functions properly"""
        # epoch should become string '0' in this case
        for falsey in (0, None, False, ''):
            pkg_dict = self._pkg_dict(epoch=falsey)
            pkg_nevra = models.NEVRA._fromdict(pkg_dict)
            self.assertEqual(pkg_nevra, self.expected)


class TestNonMetadataGetOrCalculateChecksum(unittest.TestCase):
    def setUp(self):
        super(TestNonMetadataGetOrCalculateChecksum, self).setUp()
        self.model = models.RPM(name='foo', epoch='0', version='1.0.0', release='2', arch='noarch',
                                checksumtype='sha1', checksum='abc123')
        self.model.checksums = {'sha256': 'asum'}

    def test_invalid_type(self):
        self.assertRaises(ValueError, self.model.get_or_calculate_and_save_checksum, 'sha1.5')

    def test_value_already_in_checksums(self):
        ret = self.model.get_or_calculate_and_save_checksum('sha256')

        self.assertEqual(ret, 'asum')

    def test_value_in_unit_key(self):
        with mock.patch.object(self.model, 'save') as mock_save:
            ret = self.model.get_or_calculate_and_save_checksum('sha1')

        self.assertEqual(ret, self.model.checksum)
        # make sure the checksum was added to the dict and the model was saved
        self.assertTrue('sha1' in self.model.checksums)
        mock_save.assert_called_once_with()

    @mock.patch('__builtin__.open')
    @mock.patch('pulp.server.util.calculate_checksums')
    def test_calculate_value(self, mock_calculate_checksums, mock_open):
        mock_calculate_checksums.return_value = {'md5': 'md5 sum'}

        with mock.patch.object(self.model, 'save') as mock_save:
            ret = self.model.get_or_calculate_and_save_checksum('md5')

        self.assertEqual(ret, 'md5 sum')
        mock_save.assert_called_once_with()

    def test_not_downloaded(self):
        self.model.downloaded = False

        with self.assertRaises(PulpCodedException) as assertion:
            self.model.get_or_calculate_and_save_checksum('md5')

        self.assertEqual(assertion.exception.error_code, error_codes.RPM1008)

    def test_cannot_open_file_missing(self):
        """
        When the file is missing but expected, raise a PulpCodedException.
        """
        self.model._storage_path = '/tmp/a/b/c/d/e'

        with self.assertRaises(PulpCodedException) as assertion:
            self.model.get_or_calculate_and_save_checksum('md5')

        self.assertEqual(assertion.exception.error_code, platform_error_codes.PLP0048)

    @mock.patch('__builtin__.open')
    def test_cannot_open_other_reason(self, mock_open):
        """
        Make sure if there is some other reason that opening the file failed, that bubbles up.
        """
        class MyException(Exception):
            pass

        mock_open.side_effect = MyException
        self.model._storage_path = '/tmp/a/b/c/d/e'

        self.assertRaises(MyException, self.model.get_or_calculate_and_save_checksum, 'md5')


class TestRpmBaseModifyXML(unittest.TestCase):
    # a snippet from repodata primary xml for a package
    # this snippet has been truncated to only provide the tags needed to test
    PRIMARY_EXCERPT = '''
<package type="rpm">
  <name>shark</name>
  <arch>noarch</arch>
  <version epoch="0" rel="1" ver="0.1" />
  <checksum pkgid="YES"
  type="sha256">951e0eacf3e6e6102b10acb2e689243b5866ec2c7720e783749dbd32f4a69ab3</checksum>
  <summary>A dummy package of shark</summary>
  <description>A dummy package of shark</description>
  <packager />
  <url>http://tstrachota.fedorapeople.org</url>
  <time build="1331831369" file="1331832459" />
  <size archive="296" installed="42" package="2441" />
  <location href="fixme/shark-0.1-1.noarch.rpm" />
  <format>
    <rpm:license>GPLv2</rpm:license>
    <rpm:vendor />
    <rpm:group>Internet/Applications</rpm:group>
    <rpm:buildhost>smqe-ws15</rpm:buildhost>
    <rpm:sourcerpm>shark-0.1-1.src.rpm</rpm:sourcerpm>
    <rpm:header-range end="2289" start="872" />
    <rpm:provides>
      <rpm:entry epoch="0" flags="EQ" name="shark" rel="1" ver="0.1" />
    </rpm:provides>
    <rpm:requires>
      <rpm:entry name="shark" flags="EQ" epoch="0" ver="0.1" rel="1"/>
      <rpm:entry name="walrus" flags="EQ" epoch="0" ver="5.21" rel="1"/>
    </rpm:requires>
  </format>
</package>
    '''
    OTHER_EXCERPT = '''
<package arch="noarch" name="shark"
    pkgid="951e0eacf3e6e6102b10acb2e689243b5866ec2c7720e783749dbd32f4a69ab3">
    <version epoch="0" rel="1" ver="0.1" />
</package>'''
    FILELISTS_EXCERPT = '''
<package arch="noarch" name="shark"
    pkgid="951e0eacf3e6e6102b10acb2e689243b5866ec2c7720e783749dbd32f4a69ab3">
    <version epoch="0" rel="1" ver="0.1" />
    <file>/tmp/shark.txt</file>
</package>'''

    def setUp(self):
        self.unit = models.RPM()
        self.unit.filename = 'fixed-filename.rpm'
        self.checksum = '951e0eacf3e6e6102b10acb2e689243b5866ec2c7720e783749dbd32f4a69ab3'
        self.repodata = {'primary': self.PRIMARY_EXCERPT,
                         'filelists': self.FILELISTS_EXCERPT,
                         'other': self.OTHER_EXCERPT}

    def assertParsable(self, text):
        try:
            ET.fromstring(text)
        except ET.ParseError:
            self.fail('could not parse XML')

    def test_update_location(self):
        self.unit.modify_xml(self.repodata)
        primary_xml = self.unit.get_repodata('primary')
        self.assertTrue('fixme' not in primary_xml)
        self.assertTrue('<location href="%s/f/fixed-filename.rpm"' % (constants.PULP_PACKAGES_DIR)
                        in primary_xml)

    def test_checksum_template(self):
        self.unit.modify_xml(self.repodata)
        primary_xml = self.unit.get_repodata('primary')
        self.assertTrue('{{ checksum }}' in primary_xml)
        self.assertTrue('{{ checksumtype }}' in primary_xml)
        self.assertTrue(self.checksum not in primary_xml)

    def test_checksum_other_pkgid(self):
        self.unit.modify_xml(self.repodata)
        other_xml = self.unit.get_repodata('other')
        self.assertTrue('{{ pkgid }}' in other_xml)
        self.assertTrue(self.checksum not in other_xml)
        self.assertParsable(other_xml)

    def test_checksum_filelists_pkgid(self):
        self.unit.modify_xml(self.repodata)
        filelists_xml = self.unit.get_repodata('filelists')
        self.assertTrue('{{ pkgid }}' in filelists_xml)
        self.assertTrue(self.checksum not in filelists_xml)
        self.assertParsable(filelists_xml)


class TestDistribution(unittest.TestCase):
    """
    This class contains tests for the Distribution class.
    """

    @skip_broken
    def test_process_download_reports_sanitizes_checksum_type(self):
        """
        Ensure that the process_download_reports() method calls sanitize_checksum_type correctly.
        """
        d = models.Distribution('family', 'variant', 'version', 'arch', {})
        mock_report = mock.MagicMock()
        # This should get altered to sha1
        mock_report.data = {'checksumtype': 'sha', 'checksum': 'somesum',
                            'relativepath': 'some/path'}
        reports = [mock_report]

        d.process_download_reports(reports)

        self.assertEqual(d.metadata['files'][0]['checksumtype'], 'sha1')

    def test_str(self):
        """
        Assert __str__ works with distributions.
        """
        d = models.Distribution(family='family', variant='variant', version='version', arch='arch')
        self.assertEqual('distribution: ks-family-variant-version-arch-family-'
                         'variant-version-arch', str(d))

    def test_str_no_variant(self):
        """
        Assert __str__ works with distributions that don't have a Variant.
        """
        d = models.Distribution(family='family', variant=None, version='version', arch='arch')
        self.assertEqual('distribution: ks-family--version-arch-family-None-version-arch',
                         str(d))


class TestDRPM(unittest.TestCase):
    """
    This class contains tests for the DRPM class.
    """

    def test___init___sanitizes_checksum_type(self):
        """
        Ensure that __init__() calls sanitize_checksum_type correctly.
        """
        unit_metadata = {'epoch': 'epoch',
                         'version': 'version',
                         'release': 'release',
                         'filename': 'filename',
                         'checksumtype': 'sha',
                         'checksum': 'checksum'}

        # The sha should get changed to sha1
        drpm = models.DRPM(**unit_metadata)

        self.assertEqual(drpm.checksumtype, 'sha1')


class TestErrata(unittest.TestCase):
    """
    This class contains tests for the Errata class.
    """
    def setUp(self):
        self.existing_packages = [
            {'src': 'pulp-test-package-0.3.1-1.fc22.src.rpm',
             'name': 'pulp-test-package',
             'arch': 'x86_64',
             'sums': 'sums',
             'filename': 'pulp-test-package-0.3.1-1.fc22.x86_64.rpm',
             'epoch': '0',
             'version': '0.3.1',
             'release': '1.fc22',
             'type': 'sha256'}]
        self.collection_wo_pulp_repo_id = {
            'packages': self.existing_packages,
            'name': 'test-name',
            'short': ''}
        self.collection_pulp_repo_id = {
            'packages': self.existing_packages,
            'name': 'test-name',
            'short': '',
            '_pulp_repo_id': 'test-repo'}

    def test_rpm_search_dicts_sanitizes_checksum_type_sum(self):
        """
        Assert that the rpm_search_dicts() method properly sanitizes checksum types with the sum
        is specified with the 'sum' attribute.
        """
        errata = models.Errata()
        errata.pkglist = [
            {'packages': [
                {'name': 'name', 'epoch': '0', 'version': '0.0', 'sum': ['sha', 'sum'],
                 'release': 'release', 'arch': 'arch'}]}]

        ret = errata.rpm_search_dicts

        self.assertEqual(len(ret), 1)
        self.assertEqual(ret[0]['checksumtype'], 'sha1')

    def test_rpm_search_dicts_sanitizes_checksum_type_sums(self):
        """
        Assert that the rpm_search_dicts() method properly sanitizes checksum types with the sum
        is specified with the 'type' attribute.
        """
        errata = models.Errata()
        errata.pkglist = [
            {'packages': [
                {'name': 'name', 'epoch': '0', 'version': '0.0', 'sums': ['sum1', 'sum2'],
                 'release': 'release', 'arch': 'arch', 'type': 'sha'}]}]

        ret = errata.rpm_search_dicts

        self.assertEqual(len(ret), 1)
        self.assertEqual(ret[0]['checksumtype'], 'sha1')

    def test_rpm_search_dicts_no_checksum(self):
        """
        Assert that the rpm_search_dicts() method tolerates a missing checksumtype, as is found
        when using this demo repo: https://repos.fedorapeople.org/repos/pulp/pulp/demo_repos/zoo/
        """
        errata = models.Errata()
        errata.pkglist = [
            {'packages': [
                {'name': 'foo', 'epoch': '0', 'version': '0.0', 'sum': None,
                 'release': 'release', 'arch': 'arch'}]}]

        ret = errata.rpm_search_dicts

        # sanity-check that there is one result with the correct name
        self.assertEqual(len(ret), 1)
        self.assertEqual(ret[0]['name'], 'foo')
        # make sure this field is still not present
        self.assertTrue('checksumtype' not in ret[0])

    def test_check_packages_equal(self):
        """Assert that equal lists of packages are compared properly."""
        erratum = models.Errata()
        other_packages = copy.deepcopy(self.existing_packages)

        ret = erratum._check_packages(self.existing_packages, other_packages)
        self.assertTrue(ret)

    def test_check_packages_not_equal(self):
        """Assert that not equal lists of packages are compared properly."""
        erratum = models.Errata()
        other_packages = copy.deepcopy(self.existing_packages)
        other_packages[0]["version"] = "0.3.2"

        ret = erratum._check_packages(self.existing_packages, other_packages)
        self.assertFalse(ret)

    def test_check_packages_different_length(self):
        """Assert that not equal lists of packages are compared properly."""
        erratum = models.Errata()
        other_packages = []

        ret = erratum._check_packages(self.existing_packages, other_packages)
        self.assertFalse(ret)

    def test_update_needed_newer_erratum(self):
        """
        Assert that if the newer erratum is uploaded, then the update is needed.
        """
        existing_erratum, uploaded_erratum = models.Errata(), models.Errata()
        existing_erratum.updated = '2016-01-01 00:00:00 UTC'
        uploaded_erratum.updated = '2016-04-01 00:00:00 UTC'
        ret = existing_erratum.update_needed(uploaded_erratum)
        self.assertTrue(ret)

    def test_update_needed_older_erratum(self):
        """
        Assert that if the older erratum is uploaded, then the update is not needed.
        """
        existing_erratum, uploaded_erratum = models.Errata(), models.Errata()
        existing_erratum.updated = '2016-01-01 00:00:00 UTC'
        uploaded_erratum.updated = '2015-01-01 00:00:00 UTC'
        ret = existing_erratum.update_needed(uploaded_erratum)
        self.assertFalse(ret)

    def test_update_needed_different_supported_date_formats(self):
        """
        Assert that the supported datetime format are handled correctly and without any warning
        """
        existing_erratum, uploaded_erratum = models.Errata(), models.Errata()
        existing_erratum.updated = '2015-01-01'
        uploaded_erratum.updated = '2016-01-01 00:00:00'
        ret = existing_erratum.update_needed(uploaded_erratum)
        self.assertTrue(ret)

    def test_update_needed_bad_date_existing(self):
        """
        Assert that if the `updated` date of the existing erratum is in the unknown format, then
        a ValueError is raised.
        """
        existing_erratum, uploaded_erratum = models.Errata(), models.Errata()
        existing_erratum.updated = 'Fri Jan  1 00:00:00 UTC 2016'
        uploaded_erratum.updated = '2016-04-01 00:00:00 UTC'
        self.assertRaises(ValueError, existing_erratum.update_needed, uploaded_erratum)

    def test_update_needed_bad_date_uploaded(self):
        """
        Assert that if the `updated` date of the uploaded erratum is in the unknown format, then
        a ValueError is raised.
        """
        existing_erratum, uploaded_erratum = models.Errata(), models.Errata()
        existing_erratum.updated = '2016-01-01 00:00:00 UTC'
        uploaded_erratum.updated = 'Fri Apr  1 00:00:00 UTC 2016'
        self.assertRaises(ValueError, existing_erratum.update_needed, uploaded_erratum)

    def test_update_needed_empty_date_existing(self):
        """
        Test an empty existing `updated` erratum field.

        Assert that an empty existing `updated` field is considered older than an uploaded
        erratum with a valid `updated` field.
        """
        existing_erratum, uploaded_erratum = models.Errata(), models.Errata()
        existing_erratum.updated = ''
        uploaded_erratum.updated = '2016-04-01 00:00:00 UTC'
        self.assertEqual(True, existing_erratum.update_needed(uploaded_erratum))

    def test_update_needed_empty_date_uploaded(self):
        """
        Test that an empty uploaded erratum `updated` field returns False.
        """
        existing_erratum, uploaded_erratum = models.Errata(), models.Errata()
        existing_erratum.updated = '2016-01-01 00:00:00 UTC'
        uploaded_erratum.updated = ''
        self.assertEqual(False, existing_erratum.update_needed(uploaded_erratum))

    @mock.patch('pulp_rpm.plugins.db.models.Errata.save')
    def test_merge_pkglists_oldstyle_newstyle_same_collection(self, mock_save):
        """
        Assert that _pulp_repo_id is added to the collection if it was absent and collection in the
        uploaded erratum is the same as in the existing one.
        """
        existing_erratum, uploaded_erratum = models.Errata(), models.Errata()

        # oldstyle erratum does not contain _pulp_repo_id, while the newstyle one does
        collection_wo_pulp_repo_id = copy.deepcopy(self.collection_wo_pulp_repo_id)
        existing_erratum.pkglist = [collection_wo_pulp_repo_id]
        uploaded_erratum.pkglist = [self.collection_pulp_repo_id]
        existing_erratum.merge_pkglists_and_save(uploaded_erratum)

        # make sure no additional collections are added
        self.assertEqual(len(existing_erratum.pkglist), 1)

        # make sure _pulp_repo_id is added to the existing collection
        self.assertEqual(existing_erratum.pkglist[0]['_pulp_repo_id'],
                         uploaded_erratum.pkglist[0]['_pulp_repo_id'])

        # make sure save() is called once since no collections were added
        self.assertEqual(mock_save.call_count, 1)

    @mock.patch('pulp_rpm.plugins.db.models.Errata.save')
    def test_merge_pkglists_oldstyle_newstyle_different_collection(self, mock_save):
        """
        Assert that new collection is added to the pkglist if the collection is different from the
        existing one where _pulp_repo_id is absent.
        """
        existing_erratum, uploaded_erratum = models.Errata(), models.Errata()

        # oldstyle erratum does not contain _pulp_repo_id, while the newstyle one does
        collection_wo_pulp_repo_id = copy.deepcopy(self.collection_wo_pulp_repo_id)
        existing_erratum.pkglist = [collection_wo_pulp_repo_id]

        different_collection = copy.deepcopy(self.collection_pulp_repo_id)
        different_collection['packages'][0]['version'] = '2.0'
        uploaded_erratum.pkglist = [different_collection]

        existing_erratum.merge_pkglists_and_save(uploaded_erratum)

        # make sure additional collection is added
        self.assertEqual(len(existing_erratum.pkglist), 2)
        self.assertEqual(existing_erratum.pkglist[1]['packages'][0]['version'],
                         uploaded_erratum.pkglist[0]['packages'][0]['version'])
        self.assertEqual(existing_erratum.pkglist[1]['_pulp_repo_id'],
                         uploaded_erratum.pkglist[0]['_pulp_repo_id'])

        # make sure _pulp_repo_id is not added to the existing collection
        self.assertFalse('_pulp_repo_id' in existing_erratum.pkglist[0])

    @mock.patch('pulp_rpm.plugins.db.models.Errata.save')
    @mock.patch('pulp_rpm.plugins.db.models.Errata.update_needed')
    def test_merge_pkglists_newstyle_same_repo_newer(self, mock_update_needed, mock_save):
        """
        Assert that the existing collecton is overwritten, if the uploaded erratum is newer than
        the existing one.
        """
        existing_erratum, uploaded_erratum = models.Errata(), models.Errata()

        existing_collection = copy.deepcopy(self.collection_pulp_repo_id)
        collection_same_repo_id_different_packages = copy.deepcopy(self.collection_pulp_repo_id)
        collection_same_repo_id_different_packages['packages'][0]['version'] = '2.0'

        existing_erratum.pkglist = [existing_collection]
        uploaded_erratum.pkglist = [collection_same_repo_id_different_packages]
        mock_update_needed.return_value = True
        existing_erratum.merge_pkglists_and_save(uploaded_erratum)

        # make sure no additional collections are added
        self.assertEqual(len(existing_erratum.pkglist), 1)

        # make sure the existing collection is changed
        self.assertEqual(existing_erratum.pkglist[0]['packages'][0]['version'],
                         uploaded_erratum.pkglist[0]['packages'][0]['version'])

        # make sure save() is called once since no collections were added
        self.assertEqual(mock_save.call_count, 1)

    @mock.patch('pulp_rpm.plugins.db.models.Errata.save')
    @mock.patch('pulp_rpm.plugins.db.models.Errata.update_needed')
    def test_merge_pkglists_newstyle_same_repo_older(self, mock_update_needed, mock_save):
        """
        Assert that the existing collecton is untouched, if the uploaded erratum is older than
        the existing one.
        """
        existing_erratum, uploaded_erratum = models.Errata(), models.Errata()

        existing_collection = copy.deepcopy(self.collection_pulp_repo_id)
        collection_same_repo_id_different_packages = copy.deepcopy(self.collection_pulp_repo_id)
        collection_same_repo_id_different_packages['packages'][0]['version'] = '2.0'

        existing_erratum.pkglist = [existing_collection]
        uploaded_erratum.pkglist = [collection_same_repo_id_different_packages]
        mock_update_needed.return_value = False
        existing_erratum.merge_pkglists_and_save(uploaded_erratum)

        # make sure no additional collections are added
        self.assertEqual(len(existing_erratum.pkglist), 1)

        # make sure the existing collection is untouched
        self.assertEqual(existing_erratum.pkglist[0], self.collection_pulp_repo_id)

    @mock.patch('pulp_rpm.plugins.db.models.Errata.save')
    @mock.patch('pulp_rpm.plugins.db.models.Errata.update_needed')
    def test_merge_pkglists_same_repo_Nth_merge(self, mock_update_needed, mock_save):
        """
        Assert that no new collection is added if newstyle collection for the repo exists.
        """
        existing_erratum, uploaded_erratum = models.Errata(), models.Errata()

        existing_collection_wo_pulp_repo_id = copy.deepcopy(self.collection_wo_pulp_repo_id)
        existing_collection_pulp_repo_id = copy.deepcopy(self.collection_pulp_repo_id)
        collection_same_repo_id_different_packages = copy.deepcopy(self.collection_pulp_repo_id)
        collection_same_repo_id_different_packages['packages'][0]['version'] = '2.0'

        existing_erratum.pkglist = [existing_collection_wo_pulp_repo_id,
                                    existing_collection_pulp_repo_id]
        uploaded_erratum.pkglist = [collection_same_repo_id_different_packages]
        mock_update_needed.return_value = True
        existing_erratum.merge_pkglists_and_save(uploaded_erratum)

        # make sure no additional collections are added
        self.assertEqual(len(existing_erratum.pkglist), 2)
        self.assertEqual(mock_save.call_count, 1)

        # make sure the existing collection with _pulp_repo_id is updated
        self.assertEqual(existing_erratum.pkglist[0], self.collection_wo_pulp_repo_id)
        self.assertEqual(existing_erratum.pkglist[1], uploaded_erratum.pkglist[0])

    @mock.patch('pulp_rpm.plugins.db.models.Errata.save')
    def test_merge_pkglists_newstyle_new_collection(self, mock_save):
        """
        Assert that new collection is added to the pkglist if the collection has different name.
        """
        existing_erratum, uploaded_erratum = models.Errata(), models.Errata()

        existing_collection = copy.deepcopy(self.collection_pulp_repo_id)
        new_collection = copy.deepcopy(self.collection_pulp_repo_id)
        new_collection['name'] = 'new test-name'

        existing_erratum.pkglist = [existing_collection]
        uploaded_erratum.pkglist = [new_collection]
        existing_erratum.merge_pkglists_and_save(uploaded_erratum)

        # make sure additional collection is added
        self.assertEqual(len(existing_erratum.pkglist), 2)
        self.assertEqual(existing_erratum.pkglist[0]['name'],
                         self.collection_pulp_repo_id['name'])
        self.assertEqual(existing_erratum.pkglist[1]['name'],
                         uploaded_erratum.pkglist[0]['name'])

    @mock.patch('pulp_rpm.plugins.db.models.Errata.save')
    def test_merge_pkglists_newstyle_new_repo(self, mock_save):
        """
        Assert that new collection is added to the pkglist if the uploaded erratum is from
        the different repository.
        """
        existing_erratum, uploaded_erratum = models.Errata(), models.Errata()

        existing_collection = copy.deepcopy(self.collection_pulp_repo_id)
        new_collection = copy.deepcopy(self.collection_pulp_repo_id)
        new_collection['_pulp_repo_id'] = 'other test-repo'

        existing_erratum.pkglist = [existing_collection]
        uploaded_erratum.pkglist = [new_collection]
        existing_erratum.merge_pkglists_and_save(uploaded_erratum)

        # make sure additional collection is added
        self.assertEqual(len(existing_erratum.pkglist), 2)
        self.assertEqual(existing_erratum.pkglist[0]['_pulp_repo_id'],
                         self.collection_pulp_repo_id['_pulp_repo_id'])
        self.assertEqual(existing_erratum.pkglist[1]['_pulp_repo_id'],
                         uploaded_erratum.pkglist[0]['_pulp_repo_id'])

    @mock.patch('pulp_rpm.plugins.db.models.Errata.merge_pkglists_and_save')
    @mock.patch('pulp_rpm.plugins.db.models.Errata.update_needed')
    def test_merge_errata_newer_erratum(self, mock_update_needed, mock_merge_pkglists):
        """
        Assert that the existing erratum is updated if the uploaded erratum is newer.
        """
        existing_erratum, uploaded_erratum = models.Errata(), models.Errata()
        mock_update_needed.return_value = True
        existing_erratum.mutable_erratum_fields = ('field1', 'field2')
        existing_erratum.field1 = 'existing field1'
        existing_erratum.field2 = 'existing field2'
        uploaded_erratum.field1 = 'uploaded field1'
        uploaded_erratum.field2 = 'uploaded field2'
        existing_erratum.merge_errata(uploaded_erratum)

        # make sure the erratum metadata is updated
        self.assertEqual(existing_erratum.field1, uploaded_erratum.field1)
        self.assertEqual(existing_erratum.field2, uploaded_erratum.field2)

    @mock.patch('pulp_rpm.plugins.db.models.Errata.merge_pkglists_and_save')
    @mock.patch('pulp_rpm.plugins.db.models.Errata.update_needed')
    def test_merge_errata_older_erratum(self, mock_update_needed, mock_merge_pkglists):
        """
        Assert that the existing erratum is not updated if the uploaded erratum is older.
        """
        existing_erratum, uploaded_erratum = models.Errata(), models.Errata()
        mock_update_needed.return_value = False
        existing_erratum.mutable_erratum_fields = ('field1', 'field2')
        existing_erratum.field1 = 'existing field1'
        existing_erratum.field2 = 'existing field2'
        uploaded_erratum.field1 = 'uploaded field1'
        uploaded_erratum.field2 = 'uploaded field2'
        existing_erratum.merge_errata(uploaded_erratum)

        # make sure the existing erratum is not changed
        self.assertNotEqual(existing_erratum.field1, uploaded_erratum.field1)
        self.assertNotEqual(existing_erratum.field2, uploaded_erratum.field2)

    @mock.patch('pulp_rpm.plugins.db.models.Errata.merge_pkglists_and_save')
    @mock.patch('pulp_rpm.plugins.db.models.Errata.update_needed')
    def test_merge_fixes_reboot_needed(self, mock_update_needed, mock_merge_pkglists):
        """
        Test that the reboot_suggested value is overwritten by the one on the erratum being merged.
        """
        existing_erratum, new_erratum = models.Errata(), models.Errata()
        mock_update_needed.return_value = False
        existing_erratum.reboot_suggested = True
        new_erratum.reboot_suggested = False
        existing_erratum.merge_errata(new_erratum)

        self.assertFalse(existing_erratum.reboot_suggested)

    @mock.patch('pulp_rpm.plugins.db.models.Errata.merge_pkglists_and_save')
    @mock.patch('pulp_rpm.plugins.db.models.Errata.update_needed')
    def test_merge_preserves_reboot_needed(self, mock_update_needed, mock_merge_pkglists):
        """
        Test that the reboot_suggested value is preserved when both are True.
        """
        existing_erratum, new_erratum = models.Errata(), models.Errata()
        mock_update_needed.return_value = False
        existing_erratum.reboot_suggested = True
        new_erratum.reboot_suggested = True
        existing_erratum.merge_errata(new_erratum)

        self.assertTrue(existing_erratum.reboot_suggested)


class TestISO(unittest.TestCase):
    """
    Test the ISO class.
    """

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    @skip_broken
    def test___init__(self):
        """
        Make sure __init__() sets all the proper attributes.
        """
        iso = models.ISO('name', 42, 'checksum')

        self.assertEqual(iso.name, 'name')
        self.assertEqual(iso.size, 42)
        self.assertEqual(iso.checksum, 'checksum')
        self.assertEqual(iso._unit, None)

    @skip_broken
    def test_calculate_checksum_empty_file(self):
        """
        Test the static calculate_checksum() method with an empty file.
        """
        fake_iso_data = ''
        fake_iso_file = StringIO(fake_iso_data)

        calculated_checksum = models.ISO.calculate_checksum(fake_iso_file)

        # Let's calculate the expected checksum
        hasher = hashlib.sha256()
        hasher.update(fake_iso_data)
        expected_checksum = hasher.hexdigest()

        self.assertEqual(calculated_checksum, expected_checksum)

    @skip_broken
    @mock.patch('pulp_rpm.plugins.db.models.CHECKSUM_CHUNK_SIZE', 8)
    def test_calculate_checksum_large_file(self):
        """
        Test the static calculate_checksum() method with a file that's larger than
        CHECKSUM_CHUNK_SIZE. Instead
        of testing with an actual large file, we've mocked CHECKSUM_CHUNK_SIZE to be 8 bytes,
        which is smaller
        than our test file. This will ensure that we go through the while loop in
        calculate_checksum() more than
        once.
        """
        fake_iso_data = 'I wish I were an ISO, but I am really a String. '
        # Let's just make sure that the premise of the test is correct, that our test file is
        # larger than the
        # chunk size
        self.assertTrue(len(fake_iso_data) > models.CHECKSUM_CHUNK_SIZE)
        fake_iso_file = StringIO(fake_iso_data)
        # Just for fun, to make sure the checksum calculator does seek to 0 as it should,
        # let's seek to 42
        fake_iso_file.seek(42)

        calculated_checksum = models.ISO.calculate_checksum(fake_iso_file)

        # Let's calculate the expected checksum
        hasher = hashlib.sha256()
        hasher.update(fake_iso_data)
        expected_checksum = hasher.hexdigest()

        self.assertEqual(calculated_checksum, expected_checksum)

    @skip_broken
    def test_calculate_checksum_small_file(self):
        """
        Test the static calculate_checksum() method with a file that's smaller than
        CHECKSUM_CHUNK_SIZE.
        """
        fake_iso_data = 'I wish I were an ISO, but I am really a String.'
        # Let's just make sure that the premise of the test is correct, that our small file is
        # smaller than the
        # chunk size
        self.assertTrue(len(fake_iso_data) < models.CHECKSUM_CHUNK_SIZE)
        fake_iso_file = StringIO(fake_iso_data)
        # Just for fun, to make sure the checksum calculator does seek to 0, let's seek to 13
        fake_iso_file.seek(13)

        calculated_checksum = models.ISO.calculate_checksum(fake_iso_file)

        # Let's calculate the expected checksum
        hasher = hashlib.sha256()
        hasher.update(fake_iso_data)
        expected_checksum = hasher.hexdigest()

        self.assertEqual(calculated_checksum, expected_checksum)

    @skip_broken
    def test_calculate_size(self):
        """
        Test the static calculate_size() method.
        """
        fake_iso_data = 'I am a small ISO.'
        fake_iso_file = StringIO(fake_iso_data)
        # Just for fun, let's seek to 2
        fake_iso_file.seek(2)

        size = models.ISO.calculate_size(fake_iso_file)

        self.assertEqual(size, len(fake_iso_data))

    @skip_broken
    def test_calculate_size_empty_file(self):
        """
        Test the static calculate_size() method for an empty file.
        """
        fake_iso_data = ''
        fake_iso_file = StringIO(fake_iso_data)

        size = models.ISO.calculate_size(fake_iso_file)

        self.assertEqual(size, 0)

    @skip_broken
    def test_from_unit(self):
        """
        Test correct behavior from the from_unit() method.
        """
        unit = mock.MagicMock()
        unit.unit_key = {'name': 'name', 'size': 42, 'checksum': 'checksum'}

        iso = models.ISO.from_unit(unit)

        self.assertEqual(iso.name, 'name')
        self.assertEqual(iso.size, 42)
        self.assertEqual(iso.checksum, 'checksum')
        self.assertEqual(iso._unit, unit)

    @skip_broken
    def test_init_unit(self):
        """
        Assert correct behavior from the init_unit() method.
        """
        unit = mock.MagicMock()
        conduit = mock.MagicMock()
        conduit.init_unit = mock.MagicMock(return_value=unit)
        iso = models.ISO('name', 42, 'checksum')

        iso.init_unit(conduit)

        self.assertEqual(iso._unit, unit)
        expected_relative_path = os.path.join('name', 'checksum', '42', 'name')
        conduit.init_unit.assert_called_once_with(
            ids.TYPE_ID_ISO, {'name': 'name', 'size': 42, 'checksum': 'checksum'}, {},
            expected_relative_path)

    @skip_broken
    def test_save_unit(self):
        unit = mock.MagicMock()
        iso = models.ISO('name', 42, 'checksum', unit)
        conduit = mock.MagicMock()

        iso.save_unit(conduit)

        conduit.save_unit.assert_called_once_with(unit)

    @skip_broken
    def test_storage_path(self):
        """
        Make sure the storage_path() method returns the underlying Unit's storage_path attribute.
        """
        unit = mock.MagicMock()
        unit.storage_path = '/some/path'
        iso = models.ISO('name', 42, 'checksum', unit)

        storage_path = iso.storage_path

        self.assertEqual(storage_path, unit.storage_path)

    @skip_broken
    def test_validate(self):
        """
        Assert that validate() raises no Exception when passed correct data.
        """
        destination = os.path.join(self.temp_dir, 'test.txt')
        try:
            test_file = open(destination, 'w')
            test_file.write(
                "I heard there was this band called 1023MB, they haven't got any gigs yet.")
        finally:
            test_file.close()
        unit = mock.MagicMock()
        unit.storage_path = destination
        iso = models.ISO('test.txt', 73,
                         '36891c265290bf4610b488a8eb884d32a29fd17bb9886d899e75f4cf29d3f464',
                         unit)

        # This should validate, i.e., should not raise any Exception
        iso.validate()

    @skip_broken
    def test_validate_invalid_name_full_validation_false(self):
        """
        Due to a bug[0], we don't want to allow an ISO named PULP_MANIFEST. This test checks that
        the name is validated when full_validation is set to False.

        [0] https://bugzilla.redhat.com/show_bug.cgi?id=973678
        """
        name = 'PULP_MANIFEST'
        destination = os.path.join(self.temp_dir, name)
        with open(destination, 'w') as test_file:
            test_file.write(
                "I heard there was this band called 1023MB, they haven't got any gigs yet.")
        unit = mock.MagicMock()
        unit.storage_path = destination
        iso = models.ISO(name, 73,
                         '36891c265290bf4610b488a8eb884d32a29fd17bb9886d899e75f4cf29d3f464',
                         unit)

        # This should raise a ValueError with an appropriate error message
        try:
            # We'll set full_validation to False to test that the name is validated even then
            iso.validate(full_validation=False)
            self.fail('A ValueError should have been raised, but it was not.')
        except ValueError, e:
            self.assertEqual(
                str(e), 'An ISO may not be named PULP_MANIFEST, as it conflicts with the name of '
                        'the manifest during publishing.')

    @skip_broken
    def test_validate_invalid_name_full_validation_true(self):
        """
        Due to a bug[0], we don't want to allow an ISO named PULP_MANIFEST. This test asserts that
        the name is validated when full_validation is set to True.

        [0] https://bugzilla.redhat.com/show_bug.cgi?id=973678
        """
        name = 'PULP_MANIFEST'
        destination = os.path.join(self.temp_dir, name)
        with open(destination, 'w') as test_file:
            test_file.write(
                "I heard there was this band called 1023MB, they haven't got any gigs yet.")
        unit = mock.MagicMock()
        unit.storage_path = destination
        iso = models.ISO(name, 73,
                         '36891c265290bf4610b488a8eb884d32a29fd17bb9886d899e75f4cf29d3f464',
                         unit)

        # This should raise a ValueError with an appropriate error message
        try:
            # We'll set full_validation to True for this test
            iso.validate(full_validation=True)
            self.fail('A ValueError should have been raised, but it was not.')
        except ValueError, e:
            self.assertEqual(
                str(e), 'An ISO may not be named PULP_MANIFEST, as it conflicts with the name of '
                        'the manifest during publishing.')

    @skip_broken
    def test_validate_wrong_checksum_full_validation_false(self):
        """
        Assert that validate() does not raise a ValueError when the checksum is not correct and
        full_validation is False.
        """
        destination = os.path.join(self.temp_dir, 'test.txt')
        with open(destination, 'w') as test_file:
            test_file.write(
                'Two chemists walk into a bar, the first one says "I\'ll have some H2O." to '
                'which the other adds "I\'ll have some H2O, too." The second chemist died.')
        unit = mock.MagicMock()
        unit.storage_path = destination
        iso = models.ISO('test.txt', 146, 'terrible_pun', unit)

        # This should not raise a ValueError since full_validation is False
        iso.validate(full_validation=False)

    @skip_broken
    def test_validate_wrong_checksum_full_validation_true(self):
        """
        Assert that validate() raises a ValueError when the checksum is not correct and
        full_validation is True (default).
        """
        destination = os.path.join(self.temp_dir, 'test.txt')
        try:
            test_file = open(destination, 'w')
            test_file.write(
                'Two chemists walk into a bar, the first one says "I\'ll have some H2O." to '
                'which the other adds "I\'ll have some H2O, too." The second chemist died.')
        finally:
            test_file.close()
        unit = mock.MagicMock()
        unit.storage_path = destination
        iso = models.ISO('test.txt', 146, 'terrible_pun', unit)

        # This should raise a ValueError with an appropriate error message
        try:
            iso.validate()
            self.fail('A ValueError should have been raised, but it was not.')
        except ValueError, e:
            self.assertEqual(
                str(e),
                'Downloading <test.txt> failed checksum validation. The manifest specified the '
                'checksum to be terrible_pun, but it was '
                'dfec884065223f24c3ef333d4c7dcc0eb785a683cfada51ce071410b32a905e8.')

    @skip_broken
    def test_validate_wrong_size_full_validation_false(self):
        """
        Assert that validate() does not raise a ValueError when given an incorrect size and
        full_validation is False.
        """
        destination = os.path.join(self.temp_dir, 'test.txt')
        with open(destination, 'w') as test_file:
            test_file.write(
                "Hey girl, what's your sine? It must be math.pi/2 because you're the 1.")
        unit = mock.MagicMock()
        unit.storage_path = destination
        iso = models.ISO('test.txt', math.pi,
                         '2b046422425d6f01a920278c55d8842a8989bacaea05b29d1d2082fae91c6041', unit)

        # This should not raise an Exception because full_validation is set to False
        iso.validate(full_validation=False)

    @skip_broken
    def test_validate_wrong_size_full_validation_true(self):
        """
        Assert that validate() raises a ValueError when given an incorrect size and full_validation
        is True (default).
        """
        destination = os.path.join(self.temp_dir, 'test.txt')
        try:
            test_file = open(destination, 'w')
            test_file.write(
                "Hey girl, what's your sine? It must be math.pi/2 because you're the 1.")
        finally:
            test_file.close()
        unit = mock.MagicMock()
        unit.storage_path = destination
        iso = models.ISO('test.txt', math.pi,
                         '2b046422425d6f01a920278c55d8842a8989bacaea05b29d1d2082fae91c6041', unit)

        # This should raise a ValueError with an appropriate error message
        try:
            iso.validate()
            self.fail('A ValueError should have been raised, but it was not.')
        except ValueError, e:
            self.assertEqual(
                str(e), 'Downloading <test.txt> failed validation. The manifest specified that the '
                        'file should be 3.14159265359 bytes, but the downloaded file is 70 bytes.')


@skip_broken
class TestISOManifest(unittest.TestCase):
    """
    Test the ISOManifest class.
    """

    def test___init__(self):
        """
        Assert good behavior from the __init__() method.
        """
        manifest_file = StringIO()
        manifest_file.write('test1.iso,checksum1,1\ntest2.iso,checksum2,2\ntest3.iso,checksum3,3')
        repo_url = 'http://awesomestuff.com/repo/'

        manifest = models.ISOManifest(manifest_file, repo_url)

        # There should be three ISOs with all the right stuff
        self.assertEqual(len(manifest._isos), 3)
        for index, iso in enumerate(manifest._isos):
            self.assertEqual(iso.name, 'test%s.iso' % (index + 1))
            self.assertEqual(iso.size, index + 1)
            self.assertEqual(iso.checksum, 'checksum%s' % (index + 1))
            self.assertEqual(iso.url, urljoin(repo_url, iso.name))
            self.assertEqual(iso._unit, None)

    def test___init___with_malformed_manifest(self):
        """
        Assert good behavior from the __init__() method.
        """
        manifest_file = StringIO()
        manifest_file.write(
            'test1.iso,checksum1,1\ntest2.iso,doesnt_have_a_size\ntest3.iso,checksum3,3')
        repo_url = 'http://awesomestuff.com/repo/'

        self.assertRaises(ValueError, models.ISOManifest, manifest_file, repo_url)

    def test___iter__(self):
        """
        Test the ISOManifest's __iter__() method.
        """
        manifest_file = StringIO()
        manifest_file.write('test1.iso,checksum1,1\ntest2.iso,checksum2,2\ntest3.iso,checksum3,3')
        repo_url = 'http://awesomestuff.com/repo/'

        manifest = models.ISOManifest(manifest_file, repo_url)

        num_isos = 0
        for iso in manifest:
            self.assertTrue(isinstance(iso, models.ISO))
            num_isos += 1
        self.assertEqual(num_isos, 3)

    def test___len__(self):
        """
        The ISOManifest should support the use of len() to return the number of ISOs it contains.
        """
        manifest_file = StringIO()
        manifest_file.write('test1.iso,checksum1,1\ntest2.iso,checksum2,2\ntest3.iso,checksum3,3')
        repo_url = 'http://awesomestuff.com/repo/'

        manifest = models.ISOManifest(manifest_file, repo_url)

        self.assertEqual(len(manifest), 3)


@skip_broken
class TestPackageEnvironment(unittest.TestCase):
    def test_get_group_ids(self):
        group_id_list = ['id1', 'id2']
        model = models.PackageEnvironment('foo_id', 'foo_repo', {'group_ids': group_id_list})
        self.assertEquals(group_id_list, model.group_ids)

    def test_get_options(self):
        option_list = [{'default': True, 'group': 'id1'}, {'default': False, 'group': 'id2'}]
        model = models.PackageEnvironment('foo_id', 'foo_repo', {'options': option_list})
        self.assertEquals(option_list, model.options)

    def test_get_optional_group_ids(self):
        option_list = [{'default': True, 'group': 'id1'}, {'default': False, 'group': 'id2'}]
        model = models.PackageEnvironment('foo_id', 'foo_repo', {'options': option_list})
        self.assertEquals(['id1', 'id2'], model.optional_group_ids)


class TestRPM(unittest.TestCase):
    """
    This class contains tests for the RPM class.
    """
    def test___init___sanitizes_checksum_type(self):
        """
        Ensure that __init__() calls sanitize_checksum_type correctly.
        """
        unit_metadata = {'name': 'name',
                         'epoch': 'epoch',
                         'version': 'version',
                         'release': 'release',
                         'checksumtype': 'sha',
                         'checksum': 'checksum'}

        # The sha should get changed to sha1
        rpm = models.RPM(**unit_metadata)

        self.assertEqual(rpm.checksumtype, 'sha1')


class TestRpmBaseRender(unittest.TestCase):
    FILELISTS_EXCERPT = '''
<package arch="noarch" name="cat" pkgid="{{ pkgid }}">
    <version epoch="0" rel="1" ver="1.0" />
    <file>/tmp/cat.txt</file>
</package>'''
    OTHER_EXCERPT = '''
<package arch="noarch" name="cat" pkgid="{{ pkgid }}">
    <version epoch="0" rel="1" ver="1.0" />
    <changelog>Sometimes contains {{ template vars }} description</changelog>
</package>'''
    PRIMARY_EXCERPT = '''
<package type="rpm">
  <name>cat</name>
  <arch>noarch</arch>
  <version epoch="0" rel="1" ver="1.0" />
  <checksum pkgid="YES" type="{{ checksumtype }}">{{ checksum }}</checksum>
  <summary>A dummy {{ var }} package of cat</summary>
  <description>A dummy package of cat with some description of {% character </description>
  <packager />
  <url>http://tstrachota.fedorapeople.org</url>
  <time build="1331831362" file="1331832453" />
  <size archive="292" installed="42" package="2420" />
<location href="cat-1.0-1.noarch.rpm"/>
  <format>
    <rpm:license>GPLv2</rpm:license>
    <rpm:vendor />
    <rpm:group>Internet/Applications</rpm:group>
    <rpm:buildhost>smqe-ws15</rpm:buildhost>
    <rpm:sourcerpm>cat-1.0-1.src.rpm</rpm:sourcerpm>
    <rpm:header-range end="2273" start="872" />
    <rpm:provides>
      <rpm:entry epoch="0" flags="EQ" name="cat" rel="1" ver="1.0" />
    </rpm:provides>
  </format>
</package>'''

    def setUp(self):
        super(TestRpmBaseRender, self).setUp()
        self.unit = models.RPM(name='cat', epoch='0', version='1.0', release='1', arch='noarch')
        self.unit.checksum = 'abc123'
        self.unit.checksumtype = 'sha1'
        self.unit.checksums = {'sha1': 'abc123'}
        self.unit.set_repodata('primary', self.PRIMARY_EXCERPT)
        self.unit.set_repodata('other', self.OTHER_EXCERPT)
        self.unit.set_repodata('filelists', self.FILELISTS_EXCERPT)

    def test_render_filelists(self):
        ret = self.unit.render_filelists('sha1')

        self.assertTrue('abc123' in ret)

    def test_render_other(self):
        ret = self.unit.render_other('sha1')

        self.assertTrue('abc123' in ret)

    def test_render_primary(self):
        ret = self.unit.render_primary('sha1')

        self.assertTrue('abc123' in ret)
        self.assertTrue('sha1' in ret)

    def test__escape_django_syntax_chars(self):
        """
        Test that for a requested element all syntax characters are substituted with
        the corresponding templatetag.

        List of characters and the corresponding names of the templatetag could be found in
        django.template.defaulttags.TemplateTagNode.mapping.
        For now, those characters are:
            >>> from django.template.defaulttags import TemplateTagNode
            >>> TemplateTagNode.mapping.values()
            [u'{#', u'{{', u'%}', u'#}', u'{', u'}}', u'{%', u'}']

        E.g. '{%' should be substituted with '{% templatetag openblock %}'
        """
        template = ('<tag>{some {{ var }}</tag><some_tag>text</some_tag>'
                    '<tag>some {% tag %} {# comment #} }</tag>')
        expected_template = ('<tag>{% templatetag openbrace %}some {% templatetag openvariable %}'
                             ' var {% templatetag closevariable %}</tag><some_tag>text</some_tag>'
                             '<tag>some {% templatetag openblock %} tag '
                             '{% templatetag closeblock %} {% templatetag opencomment %} comment '
                             '{% templatetag closecomment %} {% templatetag closebrace %}</tag>')
        result = self.unit._escape_django_syntax_chars(template, 'tag')
        self.assertEqual(result, expected_template)
