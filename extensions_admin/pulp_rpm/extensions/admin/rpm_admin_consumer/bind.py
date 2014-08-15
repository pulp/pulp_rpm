from gettext import gettext as _

from pulp.client.commands.consumer.bind import (
    ConsumerBindCommand, ConsumerUnbindCommand)
from pulp.client.extensions.exceptions import ExceptionHandler, CODE_NOT_FOUND


YUM_DISTRIBUTOR_ID = 'yum_distributor'


class YumConsumerBindCommand(ConsumerBindCommand):

    def add_distributor_option(self):
        pass

    def get_distributor_id(self, kwargs):
        return YUM_DISTRIBUTOR_ID


class YumConsumerUnbindCommand(ConsumerUnbindCommand):

    def __init__(self, context, name=None, description=None):
        """
        Create a new YumConsumerUnbindCommand

        :param context:     The context to use for this command
        :type  context:     pulp.client.extensions.core.ClientContext
        :param name:        The name to use for this command
        :type  name:        str
        :param description: The description for this command
        :type  description: str
        """
        ConsumerUnbindCommand.__init__(self, context, name, description)
        self.context.exception_handler = UnbindExceptionHandler(self.prompt, context.config)

    def add_distributor_option(self):
        pass

    def get_distributor_id(self, kwargs):
        return YUM_DISTRIBUTOR_ID


class UnbindExceptionHandler(ExceptionHandler):
    """
    Override the default exception handler so we can report the missing binding
    in a user-friendly way.
    """

    def handle_not_found(self, e):
        """
        Handles a not found (HTTP 404) error from the server.

        :param e: An exception to handle
        :type  e: pulp.bindings.exceptions.NotFoundException

        :return: The appropriate exit code (in this case os.EX_DATAERR)
        :rtype:  int
        """
        if 'resources' in e.extra_data and 'bind_id' in e.extra_data['resources']:
            # The binding doesn't exist, but the way the server reports this is not
            # rendered in a user-friendly way by the default handler.
            self._log_server_exception(e)
            msg = _('The binding could not be found.')
            self.prompt.render_failure_message(msg)
        else:
            ExceptionHandler.handle_not_found(self, e)

        return CODE_NOT_FOUND
