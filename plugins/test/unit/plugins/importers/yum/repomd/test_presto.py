"""
This module contains tests for the pulp_rpm.plugins.importers.yum.repomd.presto module.
"""
from xml.etree import ElementTree
import unittest

import mock

from pulp_rpm.plugins.importers.yum.repomd import presto


class TestProcessPackageElement(unittest.TestCase):
    """
    This class contains tests for the process_package_element() function.
    """
    def test_sanitizes_checksum_type(self):
        """
        Ensure that the checksum_type is properly sanitized.
        """
        element = mock.MagicMock()
        element.attrib = {
            'name': 'some name', 'epoch': '89', 'version': '1.2.4', 'release': '2',
            'arch': 'x86_64', 'oldepoch': '88', 'oldversion': '1.2.3', 'oldrelease': '1'}
        delta = mock.MagicMock()
        checksum = mock.MagicMock()
        checksum.attrib = {'type': 'sha'}

        def delta_find(element_name):
            if element_name == 'checksum':
                return checksum
            return mock.MagicMock()

        delta.find.side_effect = delta_find
        element.find.return_value = delta

        drpm = presto.process_package_element(element)

        self.assertEqual(drpm.checksumtype, 'sha1')
