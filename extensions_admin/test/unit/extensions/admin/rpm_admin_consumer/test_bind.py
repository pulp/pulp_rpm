"""
This module contains tests for the pulp_rpm.extensions.admin.rpm_admin_consumer.bind module
"""
from gettext import gettext as _
import unittest

import mock

from pulp.bindings.exceptions import NotFoundException
from pulp.client.extensions.exceptions import CODE_NOT_FOUND
from pulp_rpm.extensions.admin.rpm_admin_consumer.bind import YumConsumerUnbindCommand, UnbindExceptionHandler


class TestYumConsumerUnbindCommand(unittest.TestCase):

    def test_init(self):
        """
        Assert that the exception handler is the custom unbind handler
        """
        mock_context = mock.MagicMock()
        command = YumConsumerUnbindCommand(mock_context)

        self.assertTrue(isinstance(command.context.exception_handler, UnbindExceptionHandler))


class TestUnbindExceptionHandler(unittest.TestCase):

    def test_handle_not_found_bind_id(self):
        """
        Test that when the bind_id is returned, a user-friendly message is printed
        """
        # Setup
        exception = NotFoundException({'resources': {'bind_id': 'much unfriendly'}})
        mock_prompt = mock.Mock()
        handler = UnbindExceptionHandler(mock_prompt, mock.Mock())

        result = handler.handle_not_found(exception)
        self.assertEquals(result, CODE_NOT_FOUND)
        mock_prompt.render_failure_message.assert_called_once_with(_('The binding could not be found.'))

    @mock.patch('pulp.client.extensions.exceptions.ExceptionHandler.handle_not_found', autospec=True)
    def test_handle_not_found_default(self, mock_super_not_found):
        """
        Test that for all other cases, the parent class handler is called
        """
        # Setup
        exception = NotFoundException({})
        handler = UnbindExceptionHandler(mock.Mock(), mock.Mock())

        result = handler.handle_not_found(exception)
        self.assertEquals(result, CODE_NOT_FOUND)
        mock_super_not_found.assert_called_once_with(handler, exception)

