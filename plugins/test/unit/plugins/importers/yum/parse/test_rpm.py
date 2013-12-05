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
