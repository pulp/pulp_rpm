import mock
from pulp.devel.unit import base
from pulp.bindings.exceptions import NotFoundException, BadRequestException
from pulp_rpm.extensions.consumer.pulp_cli import BindCommand, UnbindCommand

LOAD_CONSUMER_API = 'pulp_rpm.extensions.consumer.pulp_cli.load_consumer_id'


class TestBindCommand(base.PulpClientTests):

    OPTION_NAMES = set(['--repo-id'])

    def setUp(self):
        super(TestBindCommand, self).setUp()
        self.command = BindCommand(self.context, 'bind', 'desc')

    def test_structure(self):
        # Ensure the correct method is wired up
        self.assertEqual(self.command.method, self.command.bind)

    def test_options_present(self):
        options_present = set([option.name for option in self.command.options])
        self.assertEqual(self.OPTION_NAMES, options_present)

    def test_name(self):
        self.assertEqual(self.command.name, 'bind')
        self.assertEqual(self.command.description, 'desc')

    @mock.patch('pulp.bindings.consumer.BindingsAPI.bind')
    @mock.patch(LOAD_CONSUMER_API, return_value='c1')
    def test_bind_no_repo(self, mock_consumer, mock_bind):
        mock_bind.side_effect = BadRequestException({'property_names': ['repo_id']})
        self.context.prompt = mock.MagicMock()

        # Test
        data = {'repo-id': 'repo1'}
        self.command.bind(**data)

        # Verify
        self.assertEqual(self.context.server.bind.bind.call_count, 1)
        self.assertEqual(self.context.prompt.render_success_message.call_count, 0)
        self.assertEqual(self.context.prompt.render_failure_message.call_count, 1)
        m = ('Repository [repo1] does not exist on the server')
        self.context.prompt.render_failure_message.assert_called_once_with(m, tag='not-found')

    @mock.patch('pulp.bindings.consumer.BindingsAPI.bind')
    @mock.patch(LOAD_CONSUMER_API, return_value='c1')
    def test_bind_no_dist(self, mock_consumer, mock_bind):
        mock_bind.side_effect = BadRequestException({'property_names': ['distributor_id']})
        self.context.prompt = mock.MagicMock()

        # Test
        data = {'repo-id': 'repo1'}
        self.command.bind(**data)

        # Verify
        self.assertEqual(self.context.server.bind.bind.call_count, 1)
        self.assertEqual(self.context.prompt.render_success_message.call_count, 0)
        self.assertEqual(self.context.prompt.render_failure_message.call_count, 1)
        m = ('Repository [repo1] does not have a distributor')
        self.context.prompt.render_failure_message.assert_called_once_with(m, tag='not-found')

    @mock.patch(LOAD_CONSUMER_API, return_value=None)
    def test_unbind_no_registered_consumer(self, mock_consumer):
        self.command.prompt = mock.MagicMock()

        # Test
        data = {'repo-id': 'repo1'}
        self.command.bind(**data)

        # Verify
        self.assertEqual(self.command.prompt.render_success_message.call_count, 0)
        self.assertEqual(self.command.prompt.render_failure_message.call_count, 1)
        m = ('This consumer is not registered to the Pulp server')
        self.command.prompt.render_failure_message.assert_called_once_with(m)


class TestUnbindCommand(base.PulpClientTests):

    OPTION_NAMES = set(['--repo-id', '--force'])

    def setUp(self):
        super(TestUnbindCommand, self).setUp()
        self.command = UnbindCommand(self.context, 'unbind', 'desc')

    def test_structure(self):
        # Ensure the correct method is wired up
        self.assertEqual(self.command.method, self.command.unbind)

    def test_options_present(self):
        options_present = set([option.name for option in self.command.options])
        self.assertEqual(self.OPTION_NAMES, options_present)

    def test_name(self):
        self.assertEqual(self.command.name, 'unbind')
        self.assertEqual(self.command.description, 'desc')

    @mock.patch('pulp.bindings.consumer.BindingsAPI.unbind')
    @mock.patch(LOAD_CONSUMER_API, return_value='c1')
    def test_unbind_no_repo(self, mock_consumer, mock_unbind):
        mock_unbind.side_effect = NotFoundException({'resources': ['repo_id']})
        self.context.prompt = mock.MagicMock()

        # Test
        data = {'repo-id': 'repo1', 'force': 'false'}
        self.command.unbind(**data)

        # Verify
        self.assertEqual(self.context.server.bind.unbind.call_count, 1)
        self.assertEqual(self.context.prompt.render_success_message.call_count, 0)
        self.assertEqual(self.context.prompt.render_failure_message.call_count, 1)
        m = ('Repository [repo1] does not exist on the server')
        self.context.prompt.render_failure_message.assert_called_once_with(m, tag='not-found')

    @mock.patch('pulp.bindings.consumer.BindingsAPI.unbind')
    @mock.patch(LOAD_CONSUMER_API, return_value='c1')
    def test_unbind_no_binding(self, mock_consumer, mock_unbind):
        mock_unbind.side_effect = NotFoundException({'resources': ['bind_id']})
        self.context.prompt = mock.MagicMock()

        # Test
        data = {'repo-id': 'repo1', 'force': 'false'}
        self.command.unbind(**data)

        # Verify
        self.assertEqual(self.context.server.bind.unbind.call_count, 1)
        self.assertEqual(self.context.prompt.render_success_message.call_count, 0)
        self.assertEqual(self.context.prompt.render_failure_message.call_count, 1)
        m = ('Binding [consumer: c1, repository: repo1] does not exist on the server')
        self.context.prompt.render_failure_message.assert_called_once_with(m, tag='not-found')

    @mock.patch(LOAD_CONSUMER_API, return_value=None)
    def test_unbind_no_registered_consumer(self, mock_consumer):
        self.command.prompt = mock.MagicMock()

        # Test
        data = {'repo-id': 'repo1', 'force': 'false'}
        self.command.unbind(**data)

        # Verify
        self.assertEqual(self.command.prompt.render_success_message.call_count, 0)
        self.assertEqual(self.command.prompt.render_failure_message.call_count, 1)
        m = ('This consumer is not registered to the Pulp server')
        self.command.prompt.render_failure_message.assert_called_once_with(m)
