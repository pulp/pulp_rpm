# -*- coding: utf-8 -*-

import unittest

from mock import patch

from pulp_rpm.extensions.admin import units_display
from pulp_rpm.common.ids import (TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM, TYPE_ID_ERRATA,
                                 TYPE_ID_DISTRO, TYPE_ID_PKG_GROUP, TYPE_ID_PKG_CATEGORY,
                                 TYPE_ID_YUM_REPO_METADATA_FILE)


class UnitsDisplayTests(unittest.TestCase):

    def test_details_package(self):
        unit = {'name': 'foo',
                'version': 'bar',
                'release': 'baz',
                'arch': 'qux'}
        self.assertEquals(units_display._details_package(unit), 'foo-bar-baz-qux')

    def test_details_drpm(self):
        self.assertEquals(units_display._details_drpm({'filename': 'foo'}), 'foo')

    def test_details_id_only(self):
        self.assertEquals(units_display._details_id_only({'id': 'foo'}), 'foo')

    def test__yum_repo_metadata_name_only(self):
        self.assertEqual(units_display._yum_repo_metadata_name_only({'data_type': 'foo'}), 'foo')

    @patch('pulp_rpm.extensions.admin.units_display._details_id_only')
    @patch('pulp_rpm.extensions.admin.units_display._details_package')
    @patch('pulp_rpm.extensions.admin.units_display._details_drpm')
    @patch('pulp_rpm.extensions.admin.units_display._yum_repo_metadata_name_only')
    def test_get_formatter_for_type(self, mock_metadata, mock_drpm, mock_package, mock_id_only):
        self.assertTrue(mock_package is units_display.get_formatter_for_type(TYPE_ID_RPM))
        self.assertTrue(mock_package is units_display.get_formatter_for_type(TYPE_ID_SRPM))
        self.assertTrue(mock_drpm is units_display.get_formatter_for_type(TYPE_ID_DRPM))
        self.assertTrue(mock_id_only is units_display.get_formatter_for_type(TYPE_ID_ERRATA))
        self.assertTrue(mock_id_only is units_display.get_formatter_for_type(TYPE_ID_DISTRO))
        self.assertTrue(mock_id_only is units_display.get_formatter_for_type(TYPE_ID_PKG_GROUP))
        self.assertTrue(mock_id_only is units_display.get_formatter_for_type(TYPE_ID_PKG_CATEGORY))
        self.assertTrue(mock_metadata is units_display.get_formatter_for_type(TYPE_ID_YUM_REPO_METADATA_FILE))
