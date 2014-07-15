import unittest

from mock import Mock, patch
from yum import constants
from yum.Errors import InstallError, GroupsError

import mock_yum

from mock_yum import YumBase


class ToolTest(unittest.TestCase):

    def setUp(self):
        mock_yum.install()
        from pulp_rpm.handlers.rpmtools import Package, PackageGroup
        self.Package = Package
        self.PackageGroup = PackageGroup

    def tearDown(self):
        YumBase.reset()


class TestPackages(ToolTest):

    def verify(self, report, installed=None, updated=None, removed=None, failed=None):
        resolved = []
        deps = []
        for package in installed or []:
            resolved.append(package)
            deps = YumBase.INSTALL_DEPS
        for package in updated or []:
            resolved.append(package)
            deps = YumBase.UPDATE_DEPS
        for package in removed or []:
            resolved.append(package)
            deps = YumBase.ERASE_DEPS
        self.assertEquals([p['name'] for p in report['resolved']], resolved)
        self.assertEquals([p['name'] for p in report['deps']], [p.name for p in deps])
        self.assertEquals([p['name'] for p in report['failed']], failed or [])

    def test_tx_summary(self):
        # Setup
        repo_id = 'fedora'
        deps = [
            mock_yum.TxMember(
                constants.TS_INSTALL, repo_id, mock_yum.Pkg('D1', '1.0'), isDep=True),
            mock_yum.TxMember(
                constants.TS_INSTALL, repo_id, mock_yum.Pkg('D2', '1.0'), isDep=True),
            mock_yum.TxMember(
                constants.TS_INSTALL, repo_id, mock_yum.Pkg('D3', '1.0'), isDep=True),
        ]
        install = [
            mock_yum.TxMember(constants.TS_INSTALL, repo_id, mock_yum.Pkg('A', '1.0')),
            mock_yum.TxMember(constants.TS_INSTALL, repo_id, mock_yum.Pkg('B', '1.0')),
            mock_yum.TxMember(constants.TS_INSTALL, repo_id, mock_yum.Pkg('C', '1.0')),
        ]
        erase = [
            mock_yum.TxMember(constants.TS_ERASE, repo_id, mock_yum.Pkg('D', '1.0')),
        ]
        failed = [
            mock_yum.TxMember(constants.TS_FAILED, repo_id, mock_yum.Pkg('E', '1.0')),
            mock_yum.TxMember(constants.TS_FAILED, repo_id, mock_yum.Pkg('F', '1.0')),
        ]
        ts_info = install + deps + erase + failed
        package = self.Package()
        states = [constants.TS_FAILED, constants.TS_INSTALL]
        # Test
        report = package.tx_summary(ts_info, states)
        # Verify
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

    def test_install(self):
        # Setup
        packages = [
            'zsh',
            'ksh',
            'gofer',
            'okaara',
        ]
        # Test
        package = self.Package()
        report = package.install(packages)
        # Verify
        self.verify(report, installed=packages)
        self.assertTrue(YumBase.processTransaction.called)
        self.assertTrue(YumBase.close.called)

    def test_install_failed(self):
        # Setup
        packages = [
            'zsh',
            'ksh',
            'gofer',
            'okaara',
            YumBase.FAILED_PKG,
        ]
        # Test
        package = self.Package()
        report = package.install(packages)
        # Verify
        self.verify(report, installed=packages, failed=[YumBase.FAILED_PKG])
        self.assertTrue(YumBase.processTransaction.called)
        self.assertTrue(YumBase.close.called)

    def test_install_noapply(self):
        # Setup
        packages = [
            'zsh',
            'ksh',
            'gofer',
            'okaara',
        ]
        # Test
        package = self.Package(apply=False)
        report = package.install(packages)
        # Verify
        self.verify(report, installed=packages)
        self.assertFalse(YumBase.processTransaction.called)
        self.assertTrue(YumBase.close.called)

    def test_install_importkeys(self):
        # Setup
        packages = [
            'zsh',
            'ksh',
            'gofer',
            'okaara',
        ]
        # Test
        package = self.Package(importkeys=True)
        report = package.install(packages)
        # Verify
        self.verify(report, installed=packages)
        self.assertTrue(YumBase.processTransaction.called)
        self.assertTrue(YumBase.close.called)

    def test_install_not_found(self):
        # Setup
        packages = [
            'zsh',
            'ksh',
            'gofer',
            'okaara',
            YumBase.UNKNOWN_PKG,
        ]
        # Test & verify
        package = self.Package()
        self.assertRaises(InstallError, package.install, packages)
        self.assertFalse(YumBase.processTransaction.called)
        self.assertTrue(YumBase.close.called)

    def test_update(self):
        # Setup
        packages = [
            'zsh',
            'ksh',
            'gofer',
            'okaara',
        ]
        # Test
        package = self.Package()
        report = package.update(packages)
        # Verify
        self.verify(report, updated=packages)
        self.assertTrue(YumBase.processTransaction.called)
        self.assertTrue(YumBase.close.called)

    def test_update_all(self):
        # Setup
        packages = []
        # Test
        package = self.Package()
        report = package.update(packages)
        # Verify
        self.verify(report, updated=[p.name for p in YumBase.NEED_UPDATE])
        self.assertTrue(YumBase.processTransaction.called)
        self.assertTrue(YumBase.close.called)

    def test_update_failed(self):
        # Setup
        packages = [
            'zsh',
            'ksh',
            'gofer',
            YumBase.FAILED_PKG,
            'okaara',
        ]
        # Test
        package = self.Package()
        report = package.update(packages)
        # Verify
        self.verify(report, updated=packages, failed=[YumBase.FAILED_PKG])
        self.assertTrue(YumBase.processTransaction.called)
        self.assertTrue(YumBase.close.called)

    def test_update_noapply(self):
        # Setup
        packages = [
            'zsh',
            'ksh',
            'gofer',
            'okaara',
        ]
        # Test
        package = self.Package(apply=False)
        report = package.update(packages)
        # Verify
        self.verify(report, updated=packages)
        self.assertFalse(YumBase.processTransaction.called)
        self.assertTrue(YumBase.close.called)

    def test_update_importkeys(self):
        # Setup
        packages = [
            'zsh',
            'ksh',
            'gofer',
            'okaara',
        ]
        # Test
        package = self.Package(importkeys=True)
        report = package.update(packages)
        # Verify
        self.verify(report, updated=packages)
        self.assertTrue(YumBase.processTransaction.called)
        self.assertTrue(YumBase.close.called)

    def test_update_notfound(self):
        # Setup
        packages = [
            'zsh',
            'ksh',
            'gofer',
            'okaara',
            YumBase.UNKNOWN_PKG,
        ]
        # Test & verify
        package = self.Package()
        report = package.update(packages)
        self.verify(report, updated=packages[:-1])
        self.assertTrue(YumBase.processTransaction.called)
        self.assertTrue(YumBase.close.called)

    def test_uninstall(self):
        # Setup
        packages = [
            'zsh',
            'ksh',
        ]
        # Test
        package = self.Package()
        report = package.uninstall(packages)
        # Verify
        self.verify(report, removed=packages)
        self.assertTrue(YumBase.processTransaction.called)
        self.assertTrue(YumBase.close.called)

    def test_uninstall_failed(self):
        # Setup
        packages = [
            'zsh',
            'ksh',
            YumBase.FAILED_PKG,
        ]
        # Test
        package = self.Package()
        report = package.uninstall(packages)
        # Verify
        self.verify(report, removed=packages, failed=[YumBase.FAILED_PKG])
        self.assertTrue(YumBase.processTransaction.called)
        self.assertTrue(YumBase.close.called)

    def test_uninstall_noapply(self):
        # Setup
        packages = [
            'zsh',
            'ksh',
        ]
        # Test
        package = self.Package(apply=False)
        report = package.uninstall(packages)
        # Verify
        self.verify(report, removed=packages)
        self.assertFalse(YumBase.processTransaction.called)
        self.assertTrue(YumBase.close.called)

    def test_uninstall_notfound(self):
        # Setup
        packages = [
            'zsh',
            'ksh',
            YumBase.UNKNOWN_PKG,
        ]
        # Test
        package = self.Package(apply=False)
        report = package.uninstall(packages)
        # Verify
        self.verify(report, removed=packages[:-1])
        self.assertFalse(YumBase.processTransaction.called)
        self.assertTrue(YumBase.close.called)


class TestGroups(ToolTest):

    def verify(self, report, installed=None, removed=None, failed=None):
        resolved = []
        deps = []
        for group in installed or []:
            resolved += [p.name for p in YumBase.GROUPS[group]]
            deps = YumBase.INSTALL_DEPS
        for group in removed or []:
            resolved += [p.name for p in YumBase.GROUPS[group]]
            deps = YumBase.ERASE_DEPS
        self.assertEquals([p['name'] for p in report['resolved']], resolved)
        self.assertEquals([p['name'] for p in report['deps']], [p.name for p in deps])
        self.assertEquals([p['name'] for p in report['failed']], failed or [])

    def test_install(self):
        # Setup
        groups = ['plain', 'pulp']
        # Test
        group = self.PackageGroup()
        report = group.install(groups)
        # Verify
        self.verify(report, installed=groups)
        self.assertTrue(YumBase.processTransaction.called)
        self.assertTrue(YumBase.close.called)

    def test_install_failed(self):
        # Setup
        groups = ['plain-failed', 'pulp']
        # Test
        group = self.PackageGroup()
        report = group.install(groups)
        # Verify
        self.verify(report, installed=groups, failed=[YumBase.FAILED_PKG])
        self.assertTrue(YumBase.processTransaction.called)
        self.assertTrue(YumBase.close.called)

    def test_install_importkeys(self):
        # Setup
        groups = ['plain', 'pulp']
        # Test
        group = self.PackageGroup(importkeys=True)
        report = group.install(groups)
        # Verify
        self.verify(report, installed=groups)
        self.assertTrue(YumBase.processTransaction.called)
        self.assertTrue(YumBase.close.called)

    def test_install_noapply(self):
        # Setup
        groups = ['plain', 'pulp']
        # Test
        group = self.PackageGroup(apply=False)
        report = group.install(groups)
        # Verify
        self.verify(report, installed=groups)
        self.assertFalse(YumBase.processTransaction.called)
        self.assertTrue(YumBase.close.called)

    def test_install_notfound(self):
        # Setup
        groups = ['plain', 'pulp', 'xxxx']
        # Test & verify
        group = self.PackageGroup()
        self.assertRaises(GroupsError, group.install, groups)
        self.assertFalse(YumBase.processTransaction.called)
        self.assertTrue(YumBase.close.called)

    def test_uninstall(self):
        # Setup
        groups = ['plain', 'pulp']
        # Test
        group = self.PackageGroup()
        report = group.uninstall(groups)
        # Verify
        self.verify(report, removed=groups)
        self.assertTrue(YumBase.processTransaction.called)
        self.assertTrue(YumBase.close.called)

    def test_uninstall_failed(self):
        # Setup
        groups = ['plain-failed', 'pulp']
        # Test
        group = self.PackageGroup()
        report = group.uninstall(groups)
        # Verify
        self.verify(report, removed=groups, failed=[YumBase.FAILED_PKG])
        self.assertTrue(YumBase.processTransaction.called)
        self.assertTrue(YumBase.close.called)

    def test_uninstall_noapply(self):
        # Setup
        groups = ['plain', 'pulp']
        # Test
        group = self.PackageGroup(apply=False)
        report = group.uninstall(groups)
        # Verify
        self.verify(report, removed=groups)
        self.assertFalse(YumBase.processTransaction.called)
        self.assertTrue(YumBase.close.called)


class TestProgressReport(unittest.TestCase):

    def setUp(self):
        from yum.callbacks import PT_MESSAGES
        from pulp_rpm.handlers.rpmtools import\
            ProcessTransCallback,\
            RPMCallback,\
            DownloadCallback,\
            ProgressReport
        self.PT_MESSAGES = PT_MESSAGES
        self.ProcessTransCallback = ProcessTransCallback
        self.RPMCallback = RPMCallback
        self.DownloadCallback = DownloadCallback
        self.ProgressReport = ProgressReport

    @patch('pulp_rpm.handlers.rpmtools.ProgressReport._updated')
    def test_push_step(self, _updated):
        pr = self.ProgressReport()
        step = 'started'
        pr.push_step(step)
        self.assertEqual(pr.details, {})
        self.assertEqual(pr.steps, [[step, None]])
        self.assertTrue(_updated.called)

    @patch('pulp_rpm.handlers.rpmtools.ProgressReport._updated')
    def test_set_status(self, _updated):
        pr = self.ProgressReport()
        step = 'started'
        pr.push_step(step)
        pr.set_status(True)
        self.assertEqual(pr.steps, [[step, True]])
        self.assertEqual(pr.details, {})
        self.assertTrue(_updated.called)

    @patch('pulp_rpm.handlers.rpmtools.ProgressReport._updated')
    def test_set_status_no_steps(self, _updated):
        pr = self.ProgressReport()
        pr.set_status(True)
        self.assertEqual(pr.steps, [])
        self.assertEqual(pr.details, {})
        self.assertFalse(_updated.called)

    @patch('pulp_rpm.handlers.rpmtools.ProgressReport._updated')
    def test_set_action(self, _updated):
        pr = self.ProgressReport()
        package = 'openssl'
        action = '100'
        pr.set_action(action, package)
        self.assertEqual(pr.details, dict(action=action, package=package))
        self.assertTrue(_updated.called)

    @patch('pulp_rpm.handlers.rpmtools.ProgressReport._updated')
    def test_error(self, _updated):
        pr = self.ProgressReport()
        step = 'started'
        pr.push_step(step)
        message = 'This is bad'
        pr.error(message)
        self.assertEqual(pr.details, dict(error=message))
        self.assertEqual(pr.steps, [[step, False]])
        self.assertTrue(_updated.called)

    def test_report_steps(self):
        STEPS = ('A', 'B', 'C')
        ACTION = ('downloading', 'package-xyz-1.0-1.f16.rpm')
        pr = self.ProgressReport()
        pr._updated = Mock()
        for s in STEPS:
            # validate steps pushed with status of None
            pr.push_step(s)
            name, status = pr.steps[-1]
            self.assertEqual(name, s)
            self.assertTrue(status is None)
            # validate details cleared on state pushed
            self.assertEqual(len(pr.details), 0)
            # set the action
            pr.set_action(ACTION[0], ACTION[1])
            # validate action
            self.assertEqual(pr.details['action'], ACTION[0])
            self.assertEqual(pr.details['package'], ACTION[1])
            # validate previous step status is set (True) on next
            # push when status is None
            prev = pr.steps[-2:-1]
            if prev:
                self.assertTrue(prev[0][1])

    def test_report_steps_with_errors(self):
        # Test that previous state with status=False is not
        # set (True) on next state push
        STEPS = ('A', 'B', 'C')
        pr = self.ProgressReport()
        pr._updated = Mock()
        pr.push_step(STEPS[0])
        pr.push_step(STEPS[1])
        pr.set_status(False)
        pr.push_step(STEPS[2])
        self.assertTrue(pr.steps[0][1])
        self.assertFalse(pr.steps[1][1])
        self.assertTrue(pr.steps[2][1] is None)

    def test_trans_callback(self):
        pr = self.ProgressReport()
        pr._updated = Mock()
        cb = self.ProcessTransCallback(pr)
        for state in sorted(self.PT_MESSAGES.keys()):
            cb.event(state)
        pr.set_status(True)
        self.assertEqual(len(self.PT_MESSAGES), len(pr.steps))
        i = 0
        for state in sorted(self.PT_MESSAGES.keys()):
            step = pr.steps[i]
            name = self.PT_MESSAGES[state]
            self.assertEqual(step[0], name)
            self.assertTrue(step[1])
            i += 1

    def test_event(self):
        package = 'openssl'
        pr = Mock()
        cb = self.RPMCallback(pr)
        expected_actions = set()
        for action, description in cb.action.items():
            cb.event(package, action)
            cb.event(package, action)  # test 2nd (dup) ignored
            expected_actions.add((package, action))
            self.assertEqual(cb.events, expected_actions)
            pr.set_action.assert_called_with(description, package)

    def test_action(self):
        pr = self.ProgressReport()
        pr._updated = Mock()
        cb = self.RPMCallback(pr)
        for action in sorted(cb.action.keys()):
            package = '%s_package' % action
            cb.event(package, action)
            self.assertEqual(pr.details['action'], cb.action[action])
            self.assertEqual(pr.details['package'], package)
        self.assertEqual(len(pr.steps), 0)

    def test_action_invalid_action(self):
        pr = self.ProgressReport()
        pr._updated = Mock()
        cb = self.RPMCallback(pr)
        package = 'openssl'
        action = 12345678
        cb.event(package, action)
        self.assertEqual(pr.details['action'], str(action))
        self.assertEqual(pr.details['package'], package)
        self.assertEqual(len(pr.steps), 0)

    def test_filelog(self):
        pr = self.ProgressReport()
        pr._updated = Mock()
        cb = self.RPMCallback(pr)
        for action in sorted(cb.fileaction.keys()):
            package = '%s_package' % action
            cb.filelog(package, action)
            self.assertEqual(pr.details['action'], cb.fileaction[action])
            self.assertEqual(pr.details['package'], package)
        self.assertEqual(len(pr.steps), 0)

    def test_filelog_invalid_action(self):
        pr = self.ProgressReport()
        pr._updated = Mock()
        cb = self.RPMCallback(pr)
        package = 'openssl'
        action = 12345678
        cb.filelog(package, action)
        self.assertEqual(pr.details['action'], str(action))
        self.assertEqual(pr.details['package'], package)
        self.assertEqual(len(pr.steps), 0)

    def test_errorlog(self):
        pr = self.ProgressReport()
        pr._updated = Mock()
        cb = self.RPMCallback(pr)
        message = 'Something bad happened'
        cb.errorlog(message)
        self.assertEqual(pr.details['error'], message)
        self.assertEqual(len(pr.steps), 0)

    def test_verify_txmbr(self):
        pr = Mock()
        tx = Mock()
        tx.po = 'openssl'
        cb = self.RPMCallback(pr)
        cb.verify_txmbr(None, tx, 10)
        pr.set_action.assert_called_with('Verifying', tx.po)

    def test_download_callback(self):
        FILES = ('A', 'B', 'C')
        pr = self.ProgressReport()
        pr._updated = Mock()
        cb = self.DownloadCallback(pr)
        for file in FILES:
            path = '/path/%s' % file
            cb.start(filename=path, basename=file, size=1024)
            self.assertEqual(pr.details['action'], 'Downloading')
            self.assertEqual(pr.details['package'], '%s | 1.0 k' % file)
        self.assertEqual(len(pr.steps), 0)
