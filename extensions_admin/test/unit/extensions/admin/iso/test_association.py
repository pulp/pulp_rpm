import unittest

from mock import MagicMock, patch

from pulp_rpm.extensions.admin.iso import association
from pulp_rpm.common.ids import (TYPE_ID_ISO)


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

    @patch('pulp_rpm.extensions.admin.iso.association._get_formatter')
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

    @patch('pulp_rpm.extensions.admin.iso.association._get_formatter')
    def test_get_formatter(self, mock_formatter):
        mock_context = MagicMock()
        command = association.IsoCopyCommand(mock_context)
        command.get_formatter_for_type(TYPE_ID_ISO)
        mock_formatter.assert_called_once_with(TYPE_ID_ISO)
