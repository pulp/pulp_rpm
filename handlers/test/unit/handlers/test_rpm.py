from unittest import TestCase

from mock import patch, Mock

from pulp_rpm.handlers.rpm import (
    PackageReport,
    GroupReport,
    PackageProgress,
    PackageHandler,
    GroupHandler)


MODULE = 'pulp_rpm.handlers.rpm'


class TestPackageReport(TestCase):

    @patch(MODULE + '.ContentReport')
    def test_succeeded(self, content_report):
        details = {
            'resolved': [1, 2, 3],
            'deps': [4, 5]
        }

        # test
        report = PackageReport()
        report.set_succeeded(details)

        # validation
        content_report.set_succeeded(details, 5)


class TestGroupReport(TestCase):

    @patch(MODULE + '.ContentReport')
    def test_succeeded(self, content_report):
        details = {
            'resolved': [1, 2, 3],
            'deps': [4, 5]
        }

        # test
        report = GroupReport()
        report.set_succeeded(details)

        # validation
        content_report.set_succeeded(details, 5)


class TestPackageProgress(TestCase):

    def test_init(self):
        conduit = Mock()

        # test
        report = PackageProgress(conduit)

        # validation
        report.conduit = conduit

    def test_updated(self):
        conduit = Mock()

        # test
        report = PackageProgress(conduit)
        report._updated()

        # validation
        _report = {
            'steps': report.steps,
            'details': report.details
        }
        conduit.update_progress.assert_called_once_with(_report)


class TestPackageHandler(TestCase):

    @patch(MODULE + '.PackageReport')
    @patch(MODULE + '.PackageHandler._impl')
    def test_install(self, _impl, report):
        impl = Mock()
        impl.install.return_value = dict(failed=[])
        _impl.return_value = impl
        cfg = {}
        conduit = Mock()
        options = {}
        units = [
            {'name': 'dog'},
            {'name': 'cat', 'version': '1.0'},
            {'name': 'lion', 'version': '2.0', 'release': '1'},
            {'name': 'wolf', 'version': '3.0', 'release': '2', 'epoch': '1'},
            {'name': 'bird', 'version': '4.0', 'release': '3', 'epoch': '2', 'arch': 'x86'},
        ]

        # test
        handler = PackageHandler(cfg)
        details = handler.install(conduit, units, options)

        # validation
        impl.install.assert_called_once_with(
            [
                '*:dog-*-*.*',
                '*:cat-1.0-*.*',
                '*:lion-2.0-1.*',
                '1:wolf-3.0-2.*',
                '2:bird-4.0-3.x86'
            ])
        report.return_value.set_succeeded.assert_called_once_with(impl.install.return_value)
        self.assertEqual(report.return_value, details)

    @patch(MODULE + '.PackageReport')
    @patch(MODULE + '.PackageHandler._impl')
    def test_install_failed(self, _impl, report):
        impl = Mock()
        impl.install.return_value = dict(failed=[Mock(), Mock()])
        _impl.return_value = impl
        cfg = {}
        conduit = Mock()
        options = {}
        units = [
            {'name': 'dog'},
            {'name': 'cat', 'version': '1.0'}
        ]

        # test
        handler = PackageHandler(cfg)
        details = handler.install(conduit, units, options)

        # validation
        report.return_value.set_failed.assert_called_once_with(impl.install.return_value)
        self.assertEqual(report.return_value, details)

    @patch(MODULE + '.PackageReport')
    @patch(MODULE + '.PackageHandler._impl')
    def test_update(self, _impl, report):
        impl = Mock()
        impl.update.return_value = dict(failed=[])
        _impl.return_value = impl
        cfg = {}
        conduit = Mock()
        options = {}
        units = [
            {'name': 'dog'},
            {'name': 'cat'},
        ]

        # test
        handler = PackageHandler(cfg)
        details = handler.update(conduit, units, options)

        # validation
        impl.update.assert_called_once_with([u['name'] for u in units])
        report.return_value.set_succeeded.assert_called_once_with(impl.update.return_value)
        self.assertEqual(report.return_value, details)

    @patch(MODULE + '.PackageReport')
    @patch(MODULE + '.PackageHandler._impl')
    def test_update_all(self, _impl, report):
        impl = Mock()
        impl.update.return_value = dict(failed=[])
        _impl.return_value = impl
        cfg = {}
        conduit = Mock()
        options = {'all': True}
        units = []

        # test
        handler = PackageHandler(cfg)
        details = handler.update(conduit, units, options)

        # validation
        impl.update.assert_called_once_with([])
        report.return_value.set_succeeded.assert_called_once_with(impl.update.return_value)
        self.assertEqual(report.return_value, details)

    @patch(MODULE + '.PackageReport')
    @patch(MODULE + '.PackageHandler._impl')
    def test_update_failed(self, _impl, report):
        impl = Mock()
        impl.update.return_value = dict(failed=[Mock(), Mock()])
        _impl.return_value = impl
        cfg = {}
        conduit = Mock()
        options = {}
        units = [
            {'name': 'dog'},
            {'name': 'cat'}
        ]

        # test
        handler = PackageHandler(cfg)
        details = handler.update(conduit, units, options)

        # validation
        report.return_value.set_failed.assert_called_once_with(impl.update.return_value)
        self.assertEqual(report.return_value, details)

    @patch(MODULE + '.PackageReport')
    @patch(MODULE + '.PackageHandler._impl')
    def test_uninstall(self, _impl, report):
        impl = Mock()
        impl.uninstall.return_value = dict(failed=[])
        _impl.return_value = impl
        cfg = {}
        conduit = Mock()
        options = {}
        units = [
            {'name': 'dog'},
            {'name': 'cat'},
        ]

        # test
        handler = PackageHandler(cfg)
        details = handler.uninstall(conduit, units, options)

        # validation
        impl.uninstall.assert_called_once_with([u['name'] for u in units])
        report.return_value.set_succeeded.assert_called_once_with(impl.uninstall.return_value)
        self.assertEqual(report.return_value, details)

    @patch(MODULE + '.PackageReport')
    @patch(MODULE + '.PackageHandler._impl')
    def test_uninstall_failed(self, _impl, report):
        impl = Mock()
        impl.uninstall.return_value = dict(failed=[Mock()])
        _impl.return_value = impl
        cfg = {}
        conduit = Mock()
        options = {}
        units = [
            {'name': 'dog'},
            {'name': 'cat'},
        ]

        # test
        handler = PackageHandler(cfg)
        details = handler.uninstall(conduit, units, options)

        # validation
        impl.uninstall.assert_called_once_with([u['name'] for u in units])
        report.return_value.set_failed.assert_called_once_with(impl.uninstall.return_value)
        self.assertEqual(report.return_value, details)

    @patch(MODULE + '.ProfileReport')
    @patch(MODULE + '.get_profile')
    def test_profile(self, get_profile, profile_report):
        cfg = {}
        conduit = Mock()

        # test
        handler = PackageHandler(cfg)
        report = handler.profile(conduit)

        # validation
        get_profile.assert_called_once_with('rpm')
        get_profile.return_value.collect.assert_called_once_with()
        profile_report.return_value.set_succeeded.assert_called_once_with(
            get_profile.return_value.collect.return_value)
        self.assertEqual(report, profile_report.return_value)

    @patch(MODULE + '.Package')
    @patch(MODULE + '.PackageProgress')
    def test_impl(self, progress, package):
        cfg = {}
        conduit = Mock()
        options = {
            'apply': 123,
            'importkeys': 345
        }

        # test
        handler = PackageHandler(cfg)
        impl = handler._impl(conduit, options)

        # validation
        progress.assert_called_once_with(conduit)
        package.assert_called_once_with(
            apply=options['apply'],
            importkeys=options['importkeys'],
            progress=progress.return_value)
        self.assertEqual(impl, package.return_value)


class TestGroupHandler(TestCase):

    @patch(MODULE + '.GroupReport')
    @patch(MODULE + '.GroupHandler._impl')
    def test_install(self, _impl, report):
        impl = Mock()
        impl.install.return_value = dict(failed=[])
        _impl.return_value = impl
        cfg = {}
        conduit = Mock()
        options = {}
        units = [
            {'name': 'dog'},
            {'name': 'cat'},
        ]

        # test
        handler = GroupHandler(cfg)
        details = handler.install(conduit, units, options)

        # validation
        impl.install.assert_called_once_with([u['name'] for u in units])
        report.return_value.set_succeeded.assert_called_once_with(impl.install.return_value)
        self.assertEqual(report.return_value, details)

    @patch(MODULE + '.GroupReport')
    @patch(MODULE + '.GroupHandler._impl')
    def test_uninstall(self, _impl, report):
        impl = Mock()
        impl.uninstall.return_value = dict(failed=[])
        _impl.return_value = impl
        cfg = {}
        conduit = Mock()
        options = {}
        units = [
            {'name': 'dog'},
            {'name': 'cat'},
        ]

        # test
        handler = GroupHandler(cfg)
        details = handler.uninstall(conduit, units, options)

        # validation
        impl.uninstall.assert_called_once_with([u['name'] for u in units])
        report.return_value.set_succeeded.assert_called_once_with(impl.uninstall.return_value)
        self.assertEqual(report.return_value, details)

    @patch(MODULE + '.PackageGroup')
    @patch(MODULE + '.PackageProgress')
    def test_impl(self, progress, group):
        cfg = {}
        conduit = Mock()
        options = {
            'apply': 123,
            'importkeys': 345
        }

        # test
        handler = GroupHandler(cfg)
        impl = handler._impl(conduit, options)

        # validation
        progress.assert_called_once_with(conduit)
        group.assert_called_once_with(
            apply=options['apply'],
            importkeys=options['importkeys'],
            progress=progress.return_value)
        self.assertEqual(impl, group.return_value)
