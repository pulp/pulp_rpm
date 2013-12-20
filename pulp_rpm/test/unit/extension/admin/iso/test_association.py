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

from mock import MagicMock, patch

from pulp_rpm.common.ids import (TYPE_ID_ISO)

from pulp_rpm.extension.admin.iso import association


class TestGetFormatter(unittest.TestCase):

    def test_get_formatter(self):
        method = association._get_formatter(TYPE_ID_ISO)
        self.assertEquals('foo', method({'name': 'foo'}))

    def test_get_formatter_error_if_not_iso(self):
        self.assertRaises(ValueError, association._get_formatter, 'foo_type')


class TestIsoRemoveCommand(unittest.TestCase):

    def test_setup(self):
        mock_context = MagicMock()
        command = association.IsoRemoveCommand(mock_context)
        self.assertEquals(TYPE_ID_ISO, command.type_id)

    @patch('pulp_rpm.extension.admin.iso.association._get_formatter')
    def test_get_formatter(self, mock_formatter):
        mock_context = MagicMock()
        command = association.IsoRemoveCommand(mock_context)
        command.get_formatter_for_type(TYPE_ID_ISO)
        mock_formatter.assert_called_once_with(TYPE_ID_ISO)


class TestIsoCopyCommand(unittest.TestCase):

    def test_setup(self):
        mock_context = MagicMock()
        command = association.IsoCopyCommand(mock_context)
        self.assertEquals(TYPE_ID_ISO, command.type_id)

    @patch('pulp_rpm.extension.admin.iso.association._get_formatter')
    def test_get_formatter(self, mock_formatter):
        mock_context = MagicMock()
        command = association.IsoCopyCommand(mock_context)
        command.get_formatter_for_type(TYPE_ID_ISO)
        mock_formatter.assert_called_once_with(TYPE_ID_ISO)

