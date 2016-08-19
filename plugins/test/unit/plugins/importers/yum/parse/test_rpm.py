from __future__ import absolute_import
import os

import rpm as rpm_module

from mock import patch, Mock
from pulp.common.compat import unittest
from pulp.devel.unit import util
from pulp.server.exceptions import PulpCodedException

from pulp_rpm.plugins.importers.yum.parse import rpm

DATA_DIR = os.path.join(os.path.dirname(__file__), '../../../../../data')


class TesGetPackageXml(unittest.TestCase):
    """
    tests for the get_package_xml method,  most
    of this methods functionality is tested indirectly
    by the upload tests.
    """

    @patch('createrepo.yumbased')
    def test_get_package_xml_yum_exception(self, mock_yumbased):
        mock_yumbased.CreateRepoPackage.side_effect = Exception()
        result = rpm.get_package_xml("/bad/package/path")
        util.compare_dict(result, {})


class TestStringToUnicode(unittest.TestCase):
    """
    tests for the string_to_unicode
    """

    def test_non_supported_encoding(self):
        start_string = Mock()
        start_string.decode.side_effect = UnicodeError()
        result_string = rpm.string_to_unicode(start_string)
        self.assertEquals(None, result_string)


class PackageHeaders(unittest.TestCase):
    """
    tests for package headers and signature extraction
    """

    def test_package_signature_from_header(self):
        sample_rpm_filename = os.path.join(DATA_DIR, 'walrus-5.21-1.noarch.rpm')
        headers = rpm.package_headers(sample_rpm_filename)
        self.assertTrue(isinstance(headers, rpm_module.hdr))
        signing_key = rpm.package_signature(headers)
        self.assertEquals(signing_key, 'f78fb195')
        self.assertEquals(len(signing_key), 8)

    def test_invalid_package_headers(self):
        fake_rpm_file = os.path.join(DATA_DIR, 'fake.rpm')
        with self.assertRaises(rpm_module.error) as e:
            rpm.package_headers(fake_rpm_file)
        self.assertEquals(e.exception.message, 'error reading package header')


class SignatureEnabled(unittest.TestCase):
    """
    tests for signature policy state
    """

    def test_signature_check_enabled(self):
        config = {"require_signature": True, "allowed_keys": []}
        response = rpm.signature_enabled(config)
        self.assertTrue(response)

    def test_signature_check_disabled(self):
        config = {"require_signature": False, "allowed_keys": []}
        response = rpm.signature_enabled(config)
        self.assertFalse(response)


class FilterSignature(unittest.TestCase):
    """
    test for package signature filtering
    """

    def test_reject_unsigned_packages(self):
        unit = Mock()
        unit.signing_key = None
        config = {"require_signature": True}

        with self.assertRaises(PulpCodedException) as cm:
                rpm.filter_signature(unit, config)
                self.assertEqual(cm.exception.error_code.code, 'RPM1013')

    def test_invalid_package_signature(self):
        unit = Mock()
        unit.signing_key = '12345678'
        config = {"allowed_keys": ['87654321']}

        with self.assertRaises(PulpCodedException) as cm:
            rpm.filter_signature(unit, config)
            self.assertEqual(cm.exception.error_code.code, 'RPM1014')
