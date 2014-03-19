import unittest

from mock import patch, Mock
from pulp.devel.unit import util

from pulp_rpm.plugins.importers.yum.parse import rpm


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
