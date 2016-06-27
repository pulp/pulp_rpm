from unittest import TestCase

from mock import patch, call, Mock
from yum import constants
from yum.Errors import InstallError
from yum.callbacks import PT_MESSAGES

from pulp_rpm.handlers.rpmtools import (
    Package,
    PackageGroup,
    ProcessTransCallback,
    RPMCallback,
    DownloadCallback,
    ProgressReport,
    Yum)


MODULE = 'pulp_rpm.handlers.rpmtools'


class Pkg(object):

    def __init__(self, name, version, release='1', arch='noarch'):
        self.name = name
        self.ver = version
        self.rel = str(release)
        self.arch = arch
        self.epoch = '0'

    def __str__(self):
        if int(self.epoch) > 0:
            _format = '%(epoch)s:%(name)s-%(ver)s-%(rel)s.%(arch)s'
        else:
            _format = '%(name)s-%(ver)s-%(rel)s.%(arch)s'
        return _format % self.__dict__


class TxMember(object):
    def __init__(self, state, repoid, pkg, isDep=0):
        self.output_state = state
        self.repoid = repoid
        self.isDep = isDep
        self.po = pkg


class TestPackage(TestCase):

    def test_tx_summary(self):
        repo_id = 'fedora'
        deps = [
            TxMember(constants.TS_INSTALL, repo_id, Pkg('D1', '1.0'), isDep=True),
            TxMember(constants.TS_INSTALL, repo_id, Pkg('D2', '1.0'), isDep=True),
            TxMember(constants.TS_INSTALL, repo_id, Pkg('D3', '1.0'), isDep=True),
        ]
        install = [
            TxMember(constants.TS_INSTALL, repo_id, Pkg('A', '1.0')),
            TxMember(constants.TS_INSTALL, repo_id, Pkg('B', '1.0')),
            TxMember(constants.TS_TRUEINSTALL, repo_id, Pkg('C', '1.0')),
        ]
        erase = [
            TxMember(constants.TS_ERASE, repo_id, Pkg('D', '1.0')),
        ]
        failed = [
            TxMember(constants.TS_FAILED, repo_id, Pkg('E', '1.0')),
            TxMember(constants.TS_FAILED, repo_id, Pkg('F', '1.0')),
        ]
        ts_info = install + deps + erase + failed
        package = Package()
        states = [
            constants.TS_FAILED,
            constants.TS_INSTALL,
            constants.TS_TRUEINSTALL
        ]

        # test
        report = package.tx_summary(ts_info, states)

        # validation
        _resolved = [
            {'epoch': '0', 'version': '1.0', 'name': 'A', 'release': '1',
             'arch': 'noarch', 'qname': 'A-1.0-1.noarch', 'repoid': 'fedora'},
            {'epoch': '0', 'version': '1.0', 'name': 'B', 'release': '1',
             'arch': 'noarch', 'qname': 'B-1.0-1.noarch', 'repoid': 'fedora'},
            {'epoch': '0', 'version': '1.0', 'name': 'C', 'release': '1',
             'arch': 'noarch', 'qname': 'C-1.0-1.noarch', 'repoid': 'fedora'},
            {'epoch': '0', 'version': '1.0', 'name': 'E', 'release': '1',
             'arch': 'noarch', 'qname': 'E-1.0-1.noarch', 'repoid': 'fedora'},
            {'epoch': '0', 'version': '1.0', 'name': 'F', 'release': '1',
             'arch': 'noarch', 'qname': 'F-1.0-1.noarch', 'repoid': 'fedora'},
        ]
        _failed = [
            {'epoch': '0', 'version': '1.0', 'name': 'E', 'release': '1',
             'arch': 'noarch', 'qname': 'E-1.0-1.noarch', 'repoid': 'fedora'},
            {'epoch': '0', 'version': '1.0', 'name': 'F', 'release': '1',
             'arch': 'noarch', 'qname': 'F-1.0-1.noarch', 'repoid': 'fedora'},
        ]
        _deps = [
            {'epoch': '0', 'version': '1.0', 'name': 'D1', 'release': '1',
             'arch': 'noarch', 'qname': 'D1-1.0-1.noarch', 'repoid': 'fedora'},
            {'epoch': '0', 'version': '1.0', 'name': 'D2', 'release': '1',
             'arch': 'noarch', 'qname': 'D2-1.0-1.noarch', 'repoid': 'fedora'},
            {'epoch': '0', 'version': '1.0', 'name': 'D3', 'release': '1',
             'arch': 'noarch', 'qname': 'D3-1.0-1.noarch', 'repoid': 'fedora'},
        ]

        self.assertEqual(report['resolved'], _resolved)
        self.assertEqual(report['deps'], _deps)
        self.assertEqual(report['failed'], _failed)

    def test_affected(self):
        details = {
            'resolved': [
                {'qname': 'dog-1.0'},
                {'qname': 'cat-2.0'},
            ],
            'deps': [
                {'qname': 'kennel-1.0'},
            ]
        }
        self.assertEqual(
            Package.affected(details),
            ['dog-1.0', 'cat-2.0', 'kennel-1.0'])

    @patch(MODULE + '.Package.tx_summary')
    def test_installed(self, tx_summary):
        # test
        ts_info = Mock()
        installed = Package.installed(ts_info)

        # validation
        states = (
            constants.TS_FAILED,
            constants.TS_INSTALL,
            constants.TS_TRUEINSTALL,
            constants.TS_UPDATE
        )
        tx_summary.assert_called_once_with(ts_info, states)
        self.assertEqual(installed, tx_summary.return_value)

    @patch(MODULE + '.Package.tx_summary')
    def test_updated(self, tx_summary):
        # test
        ts_info = Mock()
        updated = Package.updated(ts_info)

        # validation
        states = (
            constants.TS_FAILED,
            constants.TS_INSTALL,
            constants.TS_TRUEINSTALL,
            constants.TS_UPDATE
        )
        tx_summary.assert_called_once_with(ts_info, states)
        self.assertEqual(updated, tx_summary.return_value)

    @patch(MODULE + '.Package.tx_summary')
    def test_erased(self, tx_summary):
        # test
        ts_info = Mock()
        erased = Package.erased(ts_info)

        # validation
        states = (
            constants.TS_FAILED,
            constants.TS_ERASE
        )
        tx_summary.assert_called_once_with(ts_info, states)
        self.assertEqual(erased, tx_summary.return_value)

    @patch(MODULE + '.Yum')
    @patch(MODULE + '.Package.affected')
    @patch(MODULE + '.Package.installed')
    def test_install(self, installed, affected, yum):
        names = [
            'zsh',
            'ksh',
            'gofer',
            'okaara',
            'kernel',
        ]

        progress = Mock()
        yum.return_value.tsInfo.__len__.return_value = len(names)

        # test
        package = Package(importkeys=123, progress=progress)
        details = package.install(names)

        # validation
        yum.assert_called_once_with(123, progress)
        self.assertEqual(
            yum.return_value.install.call_args_list,
            [
                call(pattern=n) for n in names
            ])
        yum.return_value.resolveDeps.assert_called_once_with()
        yum.return_value.processTransaction.assert_called_once_with()
        yum.return_value.close.assert_called_once_with()
        installed.assert_called_once_with(yum.return_value.tsInfo)
        affected.assert_called_once_with(installed.return_value)
        self.assertEqual(details, installed.return_value)

    @patch(MODULE + '.Yum')
    @patch(MODULE + '.Package.affected')
    @patch(MODULE + '.Package.installed')
    def test_install_not_applied(self, installed, affected, yum):
        names = [
            'zsh',
            'ksh',
            'gofer',
            'okaara',
            'kernel',
        ]

        progress = Mock()
        yum.return_value.tsInfo.__len__.return_value = len(names)
        yum.return_value.progress = progress

        # test
        package = Package(apply=False, progress=progress)
        details = package.install(names)

        # validation
        self.assertEqual(
            yum.return_value.install.call_args_list,
            [
                call(pattern=n) for n in names
            ])
        yum.return_value.resolveDeps.assert_called_once_with()
        yum.return_value.close.assert_called_once_with()
        progress.set_status.assert_called_once_with(True)
        installed.assert_called_once_with(yum.return_value.tsInfo)
        affected.assert_called_once_with(installed.return_value)
        self.assertFalse(yum.return_value.processTransaction.called)
        self.assertEqual(details, installed.return_value)

    @patch(MODULE + '.Yum')
    @patch(MODULE + '.Package.affected')
    @patch(MODULE + '.Package.installed')
    def test_install_no_transactions(self, installed, affected, yum):
        names = [
            'zsh',
            'kernel',
        ]

        progress = Mock()
        yum.return_value.tsInfo.__len__.return_value = 0
        yum.return_value.progress = progress

        # test
        package = Package(progress=progress)
        details = package.install(names)

        # validation
        self.assertEqual(
            yum.return_value.install.call_args_list,
            [
                call(pattern=n) for n in names
            ])
        yum.return_value.resolveDeps.assert_called_once_with()
        yum.return_value.close.assert_called_once_with()
        progress.set_status.assert_called_once_with(True)
        installed.assert_called_once_with(yum.return_value.tsInfo)
        affected.assert_called_once_with(installed.return_value)
        self.assertFalse(yum.return_value.processTransaction.called)
        self.assertEqual(details, installed.return_value)

    @patch(MODULE + '.Yum')
    def test_install_error(self, yum):
        names = ['kernel']
        yum.return_value.install.side_effect = InstallError(value=u'D' + unichr(246) + 'g')

        # test
        package = Package()
        self.assertRaises(InstallError, package.install, names)

    @patch(MODULE + '.Yum')
    @patch(MODULE + '.Package.affected')
    @patch(MODULE + '.Package.updated')
    def test_update(self, updated, affected, yum):
        names = [
            'zsh',
            'ksh',
            'gofer',
            'okaara',
            'kernel',
        ]

        progress = Mock()
        yum.return_value.tsInfo.__len__.return_value = len(names)

        # test
        package = Package(importkeys=123, progress=progress)
        details = package.update(names)

        # validation
        yum.assert_called_once_with(123, progress)
        self.assertEqual(
            yum.return_value.update.call_args_list,
            [
                call(pattern=n) for n in names
            ])
        yum.return_value.resolveDeps.assert_called_once_with()
        yum.return_value.processTransaction.assert_called_once_with()
        yum.return_value.close.assert_called_once_with()
        updated.assert_called_once_with(yum.return_value.tsInfo)
        affected.assert_called_once_with(updated.return_value)
        self.assertEqual(details, updated.return_value)

    @patch(MODULE + '.Yum')
    @patch(MODULE + '.Package.affected')
    @patch(MODULE + '.Package.updated')
    def test_update_all(self, updated, affected, yum):
        progress = Mock()
        yum.return_value.tsInfo.__len__.return_value = 10

        # test
        package = Package(importkeys=123, progress=progress)
        details = package.update()

        # validation
        yum.assert_called_once_with(123, progress)
        yum.return_value.update.assert_called_once_with()
        yum.return_value.resolveDeps.assert_called_once_with()
        yum.return_value.processTransaction.assert_called_once_with()
        yum.return_value.close.assert_called_once_with()
        updated.assert_called_once_with(yum.return_value.tsInfo)
        affected.assert_called_once_with(updated.return_value)
        self.assertEqual(details, updated.return_value)

    @patch(MODULE + '.Yum')
    @patch(MODULE + '.Package.affected')
    @patch(MODULE + '.Package.updated')
    def test_update_not_applied(self, updated, affected, yum):
        names = [
            'zsh',
            'ksh',
            'gofer',
            'okaara',
            'kernel',
        ]

        progress = Mock()
        yum.return_value.tsInfo.__len__.return_value = len(names)
        yum.return_value.progress = progress

        # test
        package = Package(apply=False, progress=progress)
        details = package.update(names)

        # validation
        self.assertEqual(
            yum.return_value.update.call_args_list,
            [
                call(pattern=n) for n in names
            ])
        yum.return_value.resolveDeps.assert_called_once_with()
        progress.set_status.assert_called_once_with(True)
        updated.assert_called_once_with(yum.return_value.tsInfo)
        affected.assert_called_once_with(updated.return_value)
        self.assertFalse(yum.return_value.processTransaction.called)
        self.assertEqual(details, updated.return_value)

    @patch(MODULE + '.Yum')
    @patch(MODULE + '.Package.affected')
    @patch(MODULE + '.Package.updated')
    def test_update_no_transactions(self, updated, affected, yum):
        names = [
            'zsh',
            'kernel',
        ]

        progress = Mock()
        yum.return_value.tsInfo.__len__.return_value = 0
        yum.return_value.progress = progress

        # test
        package = Package(progress=progress)
        details = package.update(names)

        # validation
        self.assertEqual(
            yum.return_value.update.call_args_list,
            [
                call(pattern=n) for n in names
            ])
        yum.return_value.resolveDeps.assert_called_once_with()
        progress.set_status.assert_called_once_with(True)
        updated.assert_called_once_with(yum.return_value.tsInfo)
        affected.assert_called_once_with(updated.return_value)
        self.assertFalse(yum.return_value.processTransaction.called)
        self.assertEqual(details, updated.return_value)

    @patch(MODULE + '.Yum')
    @patch(MODULE + '.Package.affected')
    @patch(MODULE + '.Package.erased')
    def test_uninstall(self, erased, affected, yum):
        names = [
            'zsh',
            'ksh',
            'gofer',
            'okaara',
            'kernel',
        ]

        progress = Mock()
        yum.return_value.tsInfo.__len__.return_value = len(names)

        # test
        package = Package(progress=progress)
        details = package.uninstall(names)

        # validation
        yum.assert_called_once_with(progress=progress)
        self.assertEqual(
            yum.return_value.remove.call_args_list,
            [
                call(pattern=n) for n in names
            ])
        yum.return_value.resolveDeps.assert_called_once_with()
        yum.return_value.processTransaction.assert_called_once_with()
        yum.return_value.close.assert_called_once_with()
        erased.assert_called_once_with(yum.return_value.tsInfo)
        affected.assert_called_once_with(erased.return_value)
        self.assertEqual(details, erased.return_value)

    @patch(MODULE + '.Yum')
    @patch(MODULE + '.Package.affected')
    @patch(MODULE + '.Package.erased')
    def test_uninstall_not_applied(self, errased, affected, yum):
        names = [
            'zsh',
            'ksh',
            'gofer',
            'okaara',
            'kernel',
        ]

        progress = Mock()
        yum.return_value.tsInfo.__len__.return_value = len(names)
        yum.return_value.progress = progress

        # test
        package = Package(apply=False, progress=progress)
        details = package.uninstall(names)

        # validation
        self.assertEqual(
            yum.return_value.remove.call_args_list,
            [
                call(pattern=n) for n in names
            ])
        yum.return_value.resolveDeps.assert_called_once_with()
        progress.set_status.assert_called_once_with(True)
        errased.assert_called_once_with(yum.return_value.tsInfo)
        affected.assert_called_once_with(errased.return_value)
        self.assertFalse(yum.return_value.processTransaction.called)
        self.assertEqual(details, errased.return_value)

    @patch(MODULE + '.Yum')
    @patch(MODULE + '.Package.affected')
    @patch(MODULE + '.Package.erased')
    def test_uninstall_no_transactions(self, erased, affected, yum):
        names = [
            'zsh',
            'kernel',
        ]

        progress = Mock()
        yum.return_value.tsInfo.__len__.return_value = 0
        yum.return_value.progress = progress

        # test
        package = Package(progress=progress)
        details = package.uninstall(names)

        # validation
        self.assertEqual(
            yum.return_value.remove.call_args_list,
            [
                call(pattern=n) for n in names
            ])
        yum.return_value.resolveDeps.assert_called_once_with()
        progress.set_status.assert_called_once_with(True)
        erased.assert_called_once_with(yum.return_value.tsInfo)
        affected.assert_called_once_with(erased.return_value)
        self.assertFalse(yum.return_value.processTransaction.called)
        self.assertEqual(details, erased.return_value)


class TestPackageGroup(TestCase):

    @patch(MODULE + '.Yum')
    @patch(MODULE + '.Package.affected')
    @patch(MODULE + '.Package.installed')
    def test_install(self, installed, affected, yum):
        names = [
            'group_1',
            'group_2'
        ]

        progress = Mock()
        yum.return_value.tsInfo.__len__.return_value = len(names)

        # test
        package = PackageGroup(importkeys=123, progress=progress)
        details = package.install(names)

        # validation
        yum.assert_called_once_with(123, progress)
        self.assertEqual(
            yum.return_value.selectGroup.call_args_list,
            [
                call(n) for n in names
            ])
        yum.return_value.resolveDeps.assert_called_once_with()
        yum.return_value.processTransaction.assert_called_once_with()
        yum.return_value.close.assert_called_once_with()
        installed.assert_called_once_with(yum.return_value.tsInfo)
        affected.assert_called_once_with(installed.return_value)
        self.assertEqual(details, installed.return_value)

    @patch(MODULE + '.Yum')
    @patch(MODULE + '.Package.affected')
    @patch(MODULE + '.Package.installed')
    def test_install_not_applied(self, installed, affected, yum):
        names = [
            'group_1',
            'group_2'
        ]

        progress = Mock()
        yum.return_value.tsInfo.__len__.return_value = len(names)
        yum.return_value.progress = progress

        # test
        package = PackageGroup(apply=False, progress=progress)
        details = package.install(names)

        # validation
        self.assertEqual(
            yum.return_value.selectGroup.call_args_list,
            [
                call(n) for n in names
            ])
        yum.return_value.resolveDeps.assert_called_once_with()
        yum.return_value.close.assert_called_once_with()
        progress.set_status.assert_called_once_with(True)
        installed.assert_called_once_with(yum.return_value.tsInfo)
        affected.assert_called_once_with(installed.return_value)
        self.assertFalse(yum.return_value.processTransaction.called)
        self.assertEqual(details, installed.return_value)

    @patch(MODULE + '.Yum')
    @patch(MODULE + '.Package.affected')
    @patch(MODULE + '.Package.installed')
    def test_install_no_transactions(self, installed, affected, yum):
        names = [
            'group_1',
            'group_2'
        ]

        progress = Mock()
        yum.return_value.tsInfo.__len__.return_value = 0
        yum.return_value.progress = progress

        # test
        package = PackageGroup(progress=progress)
        details = package.install(names)

        # validation
        self.assertEqual(
            yum.return_value.selectGroup.call_args_list,
            [
                call(n) for n in names
            ])
        yum.return_value.resolveDeps.assert_called_once_with()
        yum.return_value.close.assert_called_once_with()
        progress.set_status.assert_called_once_with(True)
        installed.assert_called_once_with(yum.return_value.tsInfo)
        affected.assert_called_once_with(installed.return_value)
        self.assertFalse(yum.return_value.processTransaction.called)
        self.assertEqual(details, installed.return_value)

    @patch(MODULE + '.Yum')
    @patch(MODULE + '.Package.affected')
    @patch(MODULE + '.Package.erased')
    def test_uninstall(self, erased, affected, yum):
        names = [
            'group_1',
            'group_2'
        ]

        progress = Mock()
        yum.return_value.tsInfo.__len__.return_value = len(names)

        # test
        package = PackageGroup(progress=progress)
        details = package.uninstall(names)

        # validation
        yum.assert_called_once_with(progress=progress)
        self.assertEqual(
            yum.return_value.groupRemove.call_args_list,
            [
                call(n) for n in names
            ])
        yum.return_value.resolveDeps.assert_called_once_with()
        yum.return_value.processTransaction.assert_called_once_with()
        yum.return_value.close.assert_called_once_with()
        erased.assert_called_once_with(yum.return_value.tsInfo)
        affected.assert_called_once_with(erased.return_value)
        self.assertEqual(details, erased.return_value)

    @patch(MODULE + '.Yum')
    @patch(MODULE + '.Package.affected')
    @patch(MODULE + '.Package.erased')
    def test_uninstall_not_applied(self, errased, affected, yum):
        names = [
            'group_1',
            'group_2'
        ]

        progress = Mock()
        yum.return_value.tsInfo.__len__.return_value = len(names)
        yum.return_value.progress = progress

        # test
        package = PackageGroup(apply=False, progress=progress)
        details = package.uninstall(names)

        # validation
        self.assertEqual(
            yum.return_value.groupRemove.call_args_list,
            [
                call(n) for n in names
            ])
        yum.return_value.resolveDeps.assert_called_once_with()
        progress.set_status.assert_called_once_with(True)
        errased.assert_called_once_with(yum.return_value.tsInfo)
        affected.assert_called_once_with(errased.return_value)
        self.assertFalse(yum.return_value.processTransaction.called)
        self.assertEqual(details, errased.return_value)

    @patch(MODULE + '.Yum')
    @patch(MODULE + '.Package.affected')
    @patch(MODULE + '.Package.erased')
    def test_uninstall_no_transactions(self, erased, affected, yum):
        names = [
            'group_1',
            'group_2'
        ]

        progress = Mock()
        yum.return_value.tsInfo.__len__.return_value = 0
        yum.return_value.progress = progress

        # test
        package = PackageGroup(progress=progress)
        details = package.uninstall(names)

        # validation
        self.assertEqual(
            yum.return_value.groupRemove.call_args_list,
            [
                call(n) for n in names
            ])
        yum.return_value.resolveDeps.assert_called_once_with()
        progress.set_status.assert_called_once_with(True)
        erased.assert_called_once_with(yum.return_value.tsInfo)
        affected.assert_called_once_with(erased.return_value)
        self.assertFalse(yum.return_value.processTransaction.called)
        self.assertEqual(details, erased.return_value)


class TestProgressReport(TestCase):

    @patch(MODULE + '.ProgressReport._updated')
    def test_push_step(self, _updated):
        step = 'started'

        # test
        pr = ProgressReport()
        pr.push_step(step)

        # validation
        self.assertEqual(pr.details, {})
        self.assertEqual(pr.steps, [[step, None]])
        self.assertTrue(_updated.called)

    @patch(MODULE + '.ProgressReport._updated')
    def test_set_status(self, _updated):
        step = 'started'

        # test
        pr = ProgressReport()
        pr.push_step(step)
        pr.set_status(True)

        # validation
        self.assertEqual(pr.steps, [[step, True]])
        self.assertEqual(pr.details, {})
        self.assertTrue(_updated.called)

    @patch(MODULE + '.ProgressReport._updated')
    def test_set_status_no_steps(self, _updated):
        # test
        pr = ProgressReport()
        pr.set_status(True)

        # validation
        self.assertEqual(pr.steps, [])
        self.assertEqual(pr.details, {})
        self.assertFalse(_updated.called)

    @patch(MODULE + '.ProgressReport._updated')
    def test_set_action(self, _updated):
        pr = ProgressReport()
        package = 'openssl'
        action = '100'

        # test
        pr.set_action(action, package)

        # validation
        self.assertEqual(pr.details, dict(action=action, package=package))
        self.assertTrue(_updated.called)

    @patch(MODULE + '.ProgressReport._updated')
    def test_error(self, _updated):
        pr = ProgressReport()
        step = 'started'
        pr.push_step(step)
        message = 'This is bad'

        # test
        pr.error(message)

        # validation
        self.assertEqual(pr.details, dict(error=message))
        self.assertEqual(pr.steps, [[step, False]])
        self.assertTrue(_updated.called)

    def test_report_steps(self):
        steps = ('A', 'B', 'C')
        action = ('downloading', 'package-xyz-1.0-1.f16.rpm')

        # test and validation
        pr = ProgressReport()
        pr._updated = Mock()
        for s in steps:
            # validate steps pushed with status of None
            pr.push_step(s)
            name, status = pr.steps[-1]
            self.assertEqual(name, s)
            self.assertTrue(status is None)
            # validate details cleared on state pushed
            self.assertEqual(len(pr.details), 0)
            # set the action
            pr.set_action(action[0], action[1])
            # validate action
            self.assertEqual(pr.details['action'], action[0])
            self.assertEqual(pr.details['package'], action[1])
            # validate previous step status is set (True) on next
            # push when status is None
            prev = pr.steps[-2:-1]
            if prev:
                self.assertTrue(prev[0][1])

    def test_report_steps_with_errors(self):
        # Test that previous state with status=False is not
        # set (True) on next state push
        steps = ('A', 'B', 'C')

        # test
        pr = ProgressReport()
        pr._updated = Mock()
        pr.push_step(steps[0])
        pr.push_step(steps[1])
        pr.set_status(False)
        pr.push_step(steps[2])

        # validation
        self.assertTrue(pr.steps[0][1])
        self.assertFalse(pr.steps[1][1])
        self.assertTrue(pr.steps[2][1] is None)

    @patch(MODULE + '.log')
    def test_updated(self, log):
        # test
        pr = ProgressReport()
        pr._updated()

        # validation
        self.assertTrue(log.info.called)


class TestProcessTransCallback(TestCase):

    def test_trans_callback(self):
        pr = ProgressReport()
        pr._updated = Mock()

        # test
        cb = ProcessTransCallback(pr)
        for state in sorted(PT_MESSAGES.keys()):
            cb.event(state)
        pr.set_status(True)

        # validation
        self.assertEqual(len(PT_MESSAGES), len(pr.steps))
        i = 0
        for state in sorted(PT_MESSAGES.keys()):
            step = pr.steps[i]
            name = PT_MESSAGES[state]
            self.assertEqual(step[0], name)
            self.assertTrue(step[1])
            i += 1


class TestRPMCallback(TestCase):

    def test_event(self):
        package = 'openssl'
        pr = Mock()

        # test and validation
        cb = RPMCallback(pr)
        expected_actions = set()
        for action, description in cb.action.items():
            cb.event(package, action)
            cb.event(package, action)  # test 2nd (dup) ignored
            expected_actions.add((package, action))
            self.assertEqual(cb.events, expected_actions)
            pr.set_action.assert_called_with(description, package)

    def test_action(self):
        pr = ProgressReport()
        pr._updated = Mock()

        # test and validation
        cb = RPMCallback(pr)
        for action in sorted(cb.action.keys()):
            package = '%s_package' % action
            cb.event(package, action)
            self.assertEqual(pr.details['action'], cb.action[action])
            self.assertEqual(pr.details['package'], package)
        self.assertEqual(len(pr.steps), 0)

    def test_action_invalid_action(self):
        pr = ProgressReport()
        pr._updated = Mock()

        # test
        cb = RPMCallback(pr)
        package = 'openssl'
        action = 12345678
        cb.event(package, action)

        # validation
        self.assertEqual(pr.details['action'], str(action))
        self.assertEqual(pr.details['package'], package)
        self.assertEqual(len(pr.steps), 0)

    def test_filelog(self):
        pr = ProgressReport()
        pr._updated = Mock()

        # test and validation
        cb = RPMCallback(pr)
        for action in sorted(cb.fileaction.keys()):
            package = '%s_package' % action
            cb.filelog(package, action)
            self.assertEqual(pr.details['action'], cb.fileaction[action])
            self.assertEqual(pr.details['package'], package)
        self.assertEqual(len(pr.steps), 0)

    def test_filelog_invalid_action(self):
        pr = ProgressReport()
        pr._updated = Mock()

        # test
        cb = RPMCallback(pr)
        package = 'openssl'
        action = 12345678
        cb.filelog(package, action)

        # validation
        self.assertEqual(pr.details['action'], str(action))
        self.assertEqual(pr.details['package'], package)
        self.assertEqual(len(pr.steps), 0)

    def test_errorlog(self):
        pr = ProgressReport()
        pr._updated = Mock()

        # test
        cb = RPMCallback(pr)
        message = 'Something bad happened'
        cb.errorlog(message)

        # validation
        self.assertEqual(pr.details['error'], message)
        self.assertEqual(len(pr.steps), 0)

    def test_verify_txmbr(self):
        pr = Mock()
        tx = Mock()
        tx.po = 'openssl'
        cb = RPMCallback(pr)

        # test
        cb.verify_txmbr(None, tx, 10)

        # validation
        pr.set_action.assert_called_with('Verifying', tx.po)

    def test_download_callback(self):
        files = ('A', 'B', 'C')
        pr = ProgressReport()
        pr._updated = Mock()

        # test and validation
        cb = DownloadCallback(pr)
        for file in files:
            path = '/path/%s' % file
            cb.start(filename=path, basename=file, size=1024)
            self.assertEqual(pr.details['action'], 'Downloading')
            self.assertEqual(pr.details['package'], '%s | 1.0 k' % file)
        self.assertEqual(len(pr.steps), 0)


class TestYum(TestCase):

    @patch(MODULE + '.DownloadCallback')
    @patch(MODULE + '.OptionParser')
    @patch(MODULE + '.Yum.repos', Mock())
    def test_init(self, parser, download):
        parser.return_value.parse_args.return_value = (Mock(), Mock())
        progress = Mock()

        # test
        yum = Yum(True, progress)

        # validation
        parser.assert_called_with()
        parser.return_value.parse_args.assert_called_with([])
        download.assert_called_once_with(progress)
        yum.repos.setProgressBar.assert_called_once_with(download.return_value)
        self.assertEqual(yum.progress, progress)
        self.assertTrue(progress.push_step.called)

    @patch(MODULE + '.OptionParser')
    @patch(MODULE + '.YumBase.doPluginSetup')
    def test_doPluginSetup(self, setup, parser):
        parser.return_value.parse_args.return_value = (Mock(), Mock())
        yum = Yum()
        yum.plugins = Mock()
        parser.return_value.parse_args.reset_mock()
        setup.reset_mock()

        # test
        yum.doPluginSetup()

        # validation
        setup.assert_called_once_with(yum)
        parser.return_value.parse_args.assert_once_called_with([])
        yum.plugins.setCmdLine.assert_called_once_with(*parser.return_value.parse_args.return_value)

    def test_registerCommand(self):
        # test
        yum = Yum()
        yum.registerCommand('')

        # validation
        # called for coverage only.

    @patch(MODULE + '.RPMCallback')
    @patch(MODULE + '.ProcessTransCallback')
    @patch(MODULE + '.YumBase.processTransaction')
    def test_processTransaction(self, process, trans_callback, rpm_callback):
        progress = Mock()

        # test
        yum = Yum(progress=progress)
        yum.processTransaction()

        # validation
        process.assert_called_once_with(
            yum, trans_callback.return_value, rpmDisplay=rpm_callback.return_value)
        trans_callback.assert_called_once_with(yum.progress)
        rpm_callback.assert_called_once_with(yum.progress)
        yum.progress.set_status.assert_called_once_with(True)

    @patch(MODULE + '.RPMCallback')
    @patch(MODULE + '.ProcessTransCallback')
    @patch(MODULE + '.YumBase.processTransaction')
    def test_processTransaction_raised(self, process, trans_callback, rpm_callback):
        process.side_effect = ValueError
        progress = Mock()

        # test
        yum = Yum(progress=progress)
        self.assertRaises(ValueError, yum.processTransaction)

        # validation
        process.assert_called_once_with(
            yum, trans_callback.return_value, rpmDisplay=rpm_callback.return_value)
        trans_callback.assert_called_once_with(yum.progress)
        rpm_callback.assert_called_once_with(yum.progress)
        yum.progress.set_status.assert_called_once_with(False)
        del yum
