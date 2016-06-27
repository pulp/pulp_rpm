from unittest import TestCase

from mock import patch, Mock

from pulp_rpm.handlers.linux import LinuxHandler


MODULE = 'pulp_rpm.handlers.linux'


class TestLinuxHandler(TestCase):

    @patch('os.system')
    @patch(MODULE + '.RebootReport')
    def test_reboot(self, reboot_report, system):
        cfg = {}
        conduit = Mock()
        options = {
            'apply': True,
            'minutes': 4
        }

        # test
        handler = LinuxHandler(cfg)
        report = handler.reboot(conduit, options)

        # validation
        system.assert_called_once_with('shutdown -r +4')
        reboot_report.assert_called_once_with()
        reboot_report.return_value.set_succeeded.assert_called_once_with(dict(minutes=4))
        self.assertEqual(report, reboot_report.return_value)

    @patch('os.system')
    @patch(MODULE + '.RebootReport')
    def test_reboot_not_applied(self, reboot_report, system):
        cfg = {}
        conduit = Mock()
        options = {
            'apply': False,
            'minutes': 4
        }

        # test
        handler = LinuxHandler(cfg)
        report = handler.reboot(conduit, options)

        # validation
        reboot_report.assert_called_once_with()
        reboot_report.return_value.succeeded.assert_called_once_with()
        self.assertFalse(system.called)
        self.assertEqual(report, reboot_report.return_value)
