import mock

from pulp.bindings.exceptions import NotFoundException
from pulp.devel.unit import base
from pulp_rpm.extensions.admin.rpm_admin_consumer import consumer_group_bind as group_bind


class TestConsumerGroupUnbindCommand(base.PulpClientTests):

    OPTION_NAMES = set(['--repo-id', '--consumer-group-id'])

    def setUp(self):
        super(TestConsumerGroupUnbindCommand, self).setUp()
        self.command = group_bind.ConsumerGroupUnbindCommand(self.context, 'unbind', 'desc')

    def test_structure(self):
        # Ensure the correct method is wired up
        self.assertEqual(self.command.method, self.command.unbind)

    def test_options_present(self):
        options_present = set([option.name for option in self.command.options])
        self.assertEqual(self.OPTION_NAMES, options_present)

    def test_name(self):
        self.assertEqual(self.command.name, 'unbind')
        self.assertEqual(self.command.description, 'desc')

    @mock.patch('pulp.bindings.consumer_groups.ConsumerGroupBindAPI.unbind')
    def test_unbind_no_repo(self, mock_unbind):
        # Setup
        mock_unbind.side_effect = NotFoundException({'resources': ['repo_id']})
        self.context.prompt = mock.MagicMock()
        kwargs = {'consumer-group-id': 'test-group',
                  'repo-id': 'some-repo'}

        # Test
        self.command.unbind(**kwargs)

        # Verify
        self.assertEqual(self.context.server.consumer_group_bind.unbind.call_count, 1)
        self.assertEqual(self.context.prompt.render_success_message.call_count, 0)
        self.assertEqual(self.context.prompt.render_failure_message.call_count, 1)
        m = ('Repository [some-repo] does not exist on the server ')
        self.context.prompt.render_failure_message.assert_called_once_with(m, tag='not-found')

    @mock.patch('pulp.bindings.consumer_groups.ConsumerGroupBindAPI.unbind')
    def test_unbind_no_consumer(self, mock_unbind):
        # Setup
        mock_unbind.side_effect = NotFoundException({'resources': ['consumer_id']})
        self.context.prompt = mock.MagicMock()
        kwargs = {'consumer-group-id': 'test-group',
                  'repo-id': 'some-repo'}

        # Test
        self.command.unbind(**kwargs)

        # Verify
        self.assertEqual(self.context.server.consumer_group_bind.unbind.call_count, 1)
        self.assertEqual(self.context.prompt.render_success_message.call_count, 0)
        self.assertEqual(self.context.prompt.render_failure_message.call_count, 1)
        m = ('Consumer Group [test-group] does not exist on the server ')
        self.context.prompt.render_failure_message.assert_called_once_with(m, tag='not-found')
