from cStringIO import StringIO
from urlparse import urljoin
import hashlib
import math
import os
import shutil
import tempfile
import unittest

import mock

from pulp_rpm.common import ids
from pulp_rpm.devel.skip import skip_broken
from pulp_rpm.plugins.db import models


@skip_broken
class TestDistribution(unittest.TestCase):
    """
    This class contains tests for the Distribution class.
    """

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


@skip_broken
class TestDRPM(unittest.TestCase):
    """
    This class contains tests for the DRPM class.
    """

    def test___init___sanitizes_checksum_type(self):
        """
        Ensure that __init__() calls sanitize_checksum_type correctly.
        """
        # The sha should get changed to sha1
        drpm = models.DRPM('epoch', 'version', 'release', 'filename', 'sha', 'checksum', {})

        self.assertEqual(drpm.unit_key['checksumtype'], 'sha1')


@skip_broken
class TestErrata(unittest.TestCase):
    """
    This class contains tests for the Errata class.
    """

    def test_rpm_search_dicts_sanitizes_checksum_type_sum(self):
        """
        Assert that the rpm_search_dicts() method properly sanitizes checksum types with the sum
        is specified with the 'sum' attribute.
        """
        errata = models.Errata('id', {})
        errata.metadata = {
            'pkglist': [
                {'packages': [
                    {'name': 'name', 'epoch': '0', 'version': '0.0', 'sum': ['sha', 'sum'],
                     'release': 'release', 'arch': 'arch'}]}]}

        ret = errata.rpm_search_dicts

        self.assertEqual(len(ret), 1)
        self.assertEqual(ret[0]['checksumtype'], 'sha1')

    def test_rpm_search_dicts_sanitizes_checksum_type_sums(self):
        """
        Assert that the rpm_search_dicts() method properly sanitizes checksum types with the sum
        is specified with the 'type' attribute.
        """
        errata = models.Errata('id', {})
        errata.metadata = {
            'pkglist': [
                {'packages': [
                    {'name': 'name', 'epoch': '0', 'version': '0.0', 'sums': ['sum1', 'sum2'],
                     'release': 'release', 'arch': 'arch', 'type': 'sha'}]}]}

        ret = errata.rpm_search_dicts

        self.assertEqual(len(ret), 1)
        self.assertEqual(ret[0]['checksumtype'], 'sha1')


@skip_broken
class TestISO(unittest.TestCase):
    """
    Test the ISO class.
    """

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test___init__(self):
        """
        Make sure __init__() sets all the proper attributes.
        """
        iso = models.ISO('name', 42, 'checksum')

        self.assertEqual(iso.name, 'name')
        self.assertEqual(iso.size, 42)
        self.assertEqual(iso.checksum, 'checksum')
        self.assertEqual(iso._unit, None)

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

    def test_calculate_size_empty_file(self):
        """
        Test the static calculate_size() method for an empty file.
        """
        fake_iso_data = ''
        fake_iso_file = StringIO(fake_iso_data)

        size = models.ISO.calculate_size(fake_iso_file)

        self.assertEqual(size, 0)

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

    def test_save_unit(self):
        unit = mock.MagicMock()
        iso = models.ISO('name', 42, 'checksum', unit)
        conduit = mock.MagicMock()

        iso.save_unit(conduit)

        conduit.save_unit.assert_called_once_with(unit)

    def test_storage_path(self):
        """
        Make sure the storage_path() method returns the underlying Unit's storage_path attribute.
        """
        unit = mock.MagicMock()
        unit.storage_path = '/some/path'
        iso = models.ISO('name', 42, 'checksum', unit)

        storage_path = iso.storage_path

        self.assertEqual(storage_path, unit.storage_path)

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

    @skip_broken
    def test___init___sanitizes_checksum_type(self):
        """
        Ensure that __init__() calls sanitize_checksum_type correctly.
        """
        # The sha should get changed to sha1
        rpm = models.RPM('name', 'epoch', 'version', 'release', 'filename', 'sha', 'checksum', {})

        self.assertEqual(rpm.unit_key['checksumtype'], 'sha1')
