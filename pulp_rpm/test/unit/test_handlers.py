
import os
import tempfile
import shutil
import unittest

import mock_yum
from mock import Mock, patch
from mock_yum import YumBase
from pulp.agent.lib.container import Container, SYSTEM, CONTENT, BIND
from pulp.agent.lib.dispatcher import Dispatcher
from pulp.agent.lib.conduit import Conduit
from pulp.common.config import Config


class TestConduit(Conduit):

    def __init__(self, cfg=None):
        self.cfg = (cfg or {})

    def get_consumer_config(self):
        cfg = Config(self.cfg)
        return cfg

class Deployer:

    def __init__(self):
        self.root = None
        self.cwd = os.path.abspath(os.path.dirname(__file__))

    def install(self):
        root = tempfile.mkdtemp()
        targets = \
            (os.path.join(root, 'descriptors'),
             os.path.join(root, 'handlers'))
        self.deploydescriptors(targets[0])
        self.deployhandlers(targets[1])
        self.root = root
        return targets

    def uninstall(self):
        shutil.rmtree(self.root, ignore_errors=True)
        self.root = None

    def deploydescriptors(self, target):
        os.makedirs(target)
        root = os.path.join(self.cwd, '../../etc/pulp/agent/conf.d/')
        for fn in os.listdir(root):
            path = os.path.join(root, fn)
            shutil.copy(path, target)

    def deployhandlers(self, target):
        os.makedirs(target)
        root = os.path.join(self.cwd, '../../handlers/')
        for fn in os.listdir(root):
            path = os.path.join(root, fn)
            shutil.copy(path, target)


class HandlerTest(unittest.TestCase):

    def setUp(self):
        mock_yum.install()
        self.deployer = Deployer()
        dpath, hpath = self.deployer.install()
        self.container = Container(root=dpath, path=[hpath])
        self.dispatcher = Dispatcher(self.container)
        self.__system = os.system
        os.system = Mock()

    def tearDown(self):
        self.deployer.uninstall()
        os.system = self.__system
        YumBase.reset()


class TestPackages(HandlerTest):

    TYPE_ID = 'rpm'

    def setUp(self):
        HandlerTest.setUp(self)
        handler = self.container.find(self.TYPE_ID, role=CONTENT)
        self.assertTrue(handler is not None, msg='%s handler not loaded' % self.TYPE_ID)

    def verify_succeeded(self, report, installed=[], updated=[], removed=[], reboot=False):
        resolved = []
        deps = []
        for unit in installed:
            resolved.append(unit)
            deps = YumBase.INSTALL_DEPS
        for unit in updated:
            resolved.append(unit)
            deps = YumBase.UPDATE_DEPS
        for unit in removed:
            resolved.append(unit)
            deps = YumBase.REMOVE_DEPS
        self.assertTrue(report.succeeded)
        num_changes = len(resolved) + len(deps)
        if reboot:
            num_changes += 1
        self.assertEquals(report.num_changes, num_changes)
        self.assertEquals(len(report.details), 1)
        report = report.details[self.TYPE_ID]
        self.assertTrue(report['succeeded'])
        self.assertEquals(len(report['details']['resolved']), len(resolved))
        self.assertEquals(len(report['details']['deps']), len(deps))

    def verify_failed(self, report):
        self.assertFalse(report.succeeded)
        self.assertEquals(report.num_changes, 0)
        self.assertEquals(len(report.details), 1)
        report = report.details[self.TYPE_ID]
        self.assertFalse(report['succeeded'])
        self.assertTrue('message' in report['details'])
        self.assertTrue('trace' in report['details'])

    def test_install(self):
        # Setup
        units = [
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'zsh'}},
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'ksh'}},
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'gofer'}},
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'okaara'}},
        ]
        # Test
        conduit = Conduit()
        report = self.dispatcher.install(conduit, units, {})
        # Verify
        self.verify_succeeded(report, installed=units)
        self.assertFalse(report.reboot['scheduled'])
        self.assertFalse(os.system.called)
        self.assertTrue(YumBase.processTransaction.called)

    def test_install_noapply(self):
        # Setup
        units = [
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'zsh'}},
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'ksh'}},
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'gofer'}},
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'okaara'}},
        ]
        # Test
        conduit = Conduit()
        options = {'apply':False}
        report = self.dispatcher.install(conduit, units, options)
        # Verify
        self.verify_succeeded(report, installed=units)
        self.assertFalse(report.reboot['scheduled'])
        self.assertFalse(os.system.called)
        self.assertFalse(YumBase.processTransaction.called)
        
    def test_install_importkeys(self):
        # Setup
        units = [
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'zsh'}},
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'ksh'}},
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'gofer'}},
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'okaara'}},
        ]
        # Test
        conduit = Conduit()
        options = {'importkeys':True}
        report = self.dispatcher.install(conduit, units, options)
        # Verify
        self.verify_succeeded(report, installed=units)
        self.assertFalse(report.reboot['scheduled'])
        self.assertFalse(os.system.called)
        self.assertTrue(YumBase.processTransaction.called)

    def test_install_notfound(self):
        # Setup
        units = [
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'zsh'}},
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'ksh'}},
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'gofer'}},
            {'type_id':self.TYPE_ID, 'unit_key':{'name':YumBase.UNKNOWN_PKG}},
        ]
        # Test
        conduit = Conduit()
        report = self.dispatcher.install(conduit, units, {})
        # Verify
        self.verify_failed(report)
        self.assertFalse(report.reboot['scheduled'])
        self.assertFalse(os.system.called)
        self.assertFalse(YumBase.processTransaction.called)

    def test_install_with_reboot(self):
        # Setup
        units = [
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'zsh'}},
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'ksh'}},
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'gofer'}},
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'okaara'}},
        ]
        # Test
        conduit = Conduit()
        options = {'reboot':True}
        report = self.dispatcher.install(conduit, units, options)
        # Verify
        self.verify_succeeded(report, installed=units, reboot=True)
        self.assertTrue(report.reboot['scheduled'])
        self.assertEquals(report.reboot['details']['minutes'], 1)
        os.system.assert_called_once_with('shutdown -r +1')
        self.assertTrue(YumBase.processTransaction.called)

    def test_update(self):
        # Setup
        units = [
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'zsh'}},
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'ksh'}},
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'gofer'}},
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'okaara'}},
        ]
        # Test
        conduit = Conduit()
        report = self.dispatcher.update(conduit, units, {})
        # Verify
        self.verify_succeeded(report, updated=units)
        self.assertFalse(report.reboot['scheduled'])
        self.assertFalse(os.system.called)
        self.assertTrue(YumBase.processTransaction.called)
        
    def test_update_noapply(self):
        # Setup
        units = [
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'zsh'}},
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'ksh'}},
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'gofer'}},
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'okaara'}},
        ]
        # Test
        conduit = Conduit()
        options = {'apply':False}
        report = self.dispatcher.update(conduit, units, options)
        # Verify
        self.verify_succeeded(report, updated=units)
        self.assertFalse(report.reboot['scheduled'])
        self.assertFalse(os.system.called)
        self.assertFalse(YumBase.processTransaction.called)
        
    def test_update_importkeys(self):
        # Setup
        units = [
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'zsh'}},
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'ksh'}},
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'gofer'}},
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'okaara'}},
        ]
        # Test
        conduit = Conduit()
        options = {'importkeys':True}
        report = self.dispatcher.update(conduit, units, options)
        # Verify
        self.verify_succeeded(report, updated=units)
        self.assertFalse(report.reboot['scheduled'])
        self.assertFalse(os.system.called)
        self.assertTrue(YumBase.processTransaction.called)

    def test_update_with_reboot(self):
        # Setup
        units = [
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'zsh'}},
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'ksh'}},
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'gofer'}},
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'okaara'}},
        ]
        # Test
        conduit = Conduit()
        options = {'reboot':True, 'minutes':5}
        report = self.dispatcher.update(conduit, units, options)
        # Verify
        self.verify_succeeded(report, updated=units, reboot=True)
        self.assertTrue(report.reboot['scheduled'])
        self.assertEquals(report.reboot['details']['minutes'], 5)
        os.system.assert_called_once_with('shutdown -r +5')
        self.assertTrue(YumBase.processTransaction.called)

    def test_uninstall(self):
        # Setup
        units = [
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'zsh'}},
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'okaara'}},
        ]
        # Test
        conduit = Conduit()
        report = self.dispatcher.uninstall(conduit, units, {})
        # Verify
        self.verify_succeeded(report, removed=units)
        self.assertFalse(report.reboot['scheduled'])
        self.assertFalse(os.system.called)
        self.assertTrue(YumBase.processTransaction.called)
        
    def test_uninstall_noapply(self):
        # Setup
        units = [
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'zsh'}},
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'okaara'}},
        ]
        # Test
        conduit = Conduit()
        options = {'apply':False}
        report = self.dispatcher.uninstall(conduit, units, options)
        # Verify
        self.verify_succeeded(report, removed=units)
        self.assertFalse(report.reboot['scheduled'])
        self.assertFalse(os.system.called)
        self.assertFalse(YumBase.processTransaction.called)

    def test_uninstall_with_reboot(self):
        # Setup
        units = [
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'zsh'}},
            {'type_id':self.TYPE_ID, 'unit_key':{'name':'kmod'}},
        ]
        # Test
        conduit = Conduit()
        options = {'reboot':True}
        report = self.dispatcher.uninstall(conduit, units, options)
        # Verify
        self.verify_succeeded(report, removed=units, reboot=True)
        self.assertTrue(report.reboot['scheduled'])
        self.assertEquals(report.reboot['details']['minutes'], 1)
        os.system.assert_called_once_with('shutdown -r +1')
        self.assertTrue(YumBase.processTransaction.called)


class TestGroups(HandlerTest):

    TYPE_ID = 'package_group'

    def setUp(self):
        HandlerTest.setUp(self)
        handler = self.container.find(self.TYPE_ID, role=CONTENT)
        self.assertTrue(handler is not None, msg='%s handler not loaded' % self.TYPE_ID)

    def verify_succeeded(self, report, installed=[], removed=[], reboot=False):
        resolved = []
        deps = []
        for group in installed:
            resolved += [str(p) for p in YumBase.GROUPS[group]]
            deps = YumBase.INSTALL_DEPS
        for group in removed:
            resolved += [str(p) for p in YumBase.GROUPS[group]]
            deps = YumBase.REMOVE_DEPS
        self.assertTrue(report.succeeded)
        num_changes = len(resolved)+len(deps)
        if reboot:
            num_changes += 1
        self.assertEquals(report.num_changes, num_changes)
        self.assertEquals(len(report.details), 1)
        report = report.details[self.TYPE_ID]
        self.assertTrue(report['succeeded'])
        self.assertEquals(len(report['details']['resolved']), len(resolved))
        self.assertEquals(len(report['details']['deps']), len(deps))

    def verify_failed(self, report):
        self.assertFalse(report.succeeded)
        self.assertEquals(report.num_changes, 0)
        self.assertEquals(len(report.details), 1)
        report = report.details[self.TYPE_ID]
        self.assertFalse(report['succeeded'])
        self.assertTrue('message' in report['details'])
        self.assertTrue('trace' in report['details'])

    def test_install(self):
        # Setup
        groups = ['mygroup', 'pulp']
        units = [dict(type_id=self.TYPE_ID, unit_key=dict(name=g)) for g in groups]
        # Test
        conduit = Conduit()
        report = self.dispatcher.install(conduit, units, {})
        # Verify
        self.verify_succeeded(report, installed=groups)
        self.assertFalse(report.reboot['scheduled'])
        self.assertFalse(os.system.called)
        self.assertTrue(YumBase.processTransaction.called)
        
    def test_install_importkeys(self):
        # Setup
        groups = ['mygroup', 'pulp']
        units = [dict(type_id=self.TYPE_ID, unit_key=dict(name=g)) for g in groups]
        # Test
        conduit = Conduit()
        options = {'importkeys':True}
        report = self.dispatcher.install(conduit, units, options)
        # Verify
        self.verify_succeeded(report, installed=groups)
        self.assertFalse(report.reboot['scheduled'])
        self.assertFalse(os.system.called)
        self.assertTrue(YumBase.processTransaction.called)
        
    def test_install_noapply(self):
        # Setup
        groups = ['mygroup', 'pulp']
        units = [dict(type_id=self.TYPE_ID, unit_key=dict(name=g)) for g in groups]
        # Test
        conduit = Conduit()
        options = {'apply':False}
        report = self.dispatcher.install(conduit, units, options)
        # Verify
        self.verify_succeeded(report, installed=groups)
        self.assertFalse(report.reboot['scheduled'])
        self.assertFalse(os.system.called)
        self.assertFalse(YumBase.processTransaction.called)

    def test_install_notfound(self):
        # Setup
        groups = ['mygroup', 'pulp', 'xxxx']
        units = [dict(type_id=self.TYPE_ID, unit_key=dict(name=g)) for g in groups]
        # Test
        conduit = Conduit()
        report = self.dispatcher.install(conduit, units, {})
        # Verify
        self.verify_failed(report)
        self.assertFalse(report.reboot['scheduled'])
        self.assertFalse(os.system.called)
        self.assertFalse(YumBase.processTransaction.called)

    def test_install_with_reboot(self):
        # Setup
        groups = ['mygroup']
        units = [dict(type_id=self.TYPE_ID, unit_key=dict(name=g)) for g in groups]
        # Test
        conduit = Conduit()
        options = {'reboot':True}
        report = self.dispatcher.install(conduit, units, options)
        # Verify
        self.verify_succeeded(report, installed=groups, reboot=True)
        self.assertTrue(report.reboot['scheduled'])
        self.assertEquals(report.reboot['details']['minutes'], 1)
        os.system.assert_called_once_with('shutdown -r +1')
        self.assertTrue(YumBase.processTransaction.called)

    def test_uninstall(self):
        # Setup
        groups = ['mygroup', 'pulp']
        units = [dict(type_id=self.TYPE_ID, unit_key=dict(name=g)) for g in groups]
        # Test
        conduit = Conduit()
        report = self.dispatcher.uninstall(conduit, units, {})
        # Verify
        self.verify_succeeded(report, removed=groups)
        self.assertFalse(report.reboot['scheduled'])
        self.assertFalse(os.system.called)
        self.assertTrue(YumBase.processTransaction.called)
        
    def test_uninstall_noapply(self):
        # Setup
        groups = ['mygroup', 'pulp']
        units = [dict(type_id=self.TYPE_ID, unit_key=dict(name=g)) for g in groups]
        # Test
        conduit = Conduit()
        options = {'apply':False}
        report = self.dispatcher.uninstall(conduit, units, options)
        # Verify
        self.verify_succeeded(report, removed=groups)
        self.assertFalse(report.reboot['scheduled'])
        self.assertFalse(report.reboot['scheduled'])
        self.assertFalse(os.system.called)
        self.assertFalse(YumBase.processTransaction.called)

    def test_uninstall_with_reboot(self):
        # Setup
        groups = ['mygroup']
        units = [dict(type_id=self.TYPE_ID, unit_key=dict(name=g)) for g in groups]
        # Test
        conduit = Conduit()
        options = {'reboot':True}
        report = self.dispatcher.uninstall(conduit, units, options)
        # Verify
        self.verify_succeeded(report, removed=groups, reboot=True)
        self.assertTrue(report.reboot['scheduled'])
        self.assertEquals(report.reboot['details']['minutes'], 1)
        os.system.assert_called_once_with('shutdown -r +1')
        self.assertTrue(YumBase.processTransaction.called)


class TestBind(HandlerTest):

    TYPE_ID = 'yum_distributor'
    REPO_ID = 'test-repo'
    REPO_NAME = 'My test-repository'
    DETAILS = {
        'protocols':{'http':'http://myfake.com/content'},
        'server_name':'test-server',
        'relative_path':'/tmp/lib/pulp/xxx',
        'ca_cert':'CA-CERT',
        'client_cert':'CLIENT-CERT',
        'repo_name':REPO_NAME,
    }
    BINDING = {'type_id':TYPE_ID, 'repo_id':REPO_ID, 'details':DETAILS}
    UNBINDING = {'type_id':TYPE_ID, 'repo_id':REPO_ID}
    TEST_DIR = '/tmp/pulp-test'
    MIRROR_DIR = os.path.join(TEST_DIR, 'mirrors')
    GPG_DIR = os.path.join(TEST_DIR, 'gpg')
    CERT_DIR = os.path.join(TEST_DIR, 'certs')
    REPO_DIR = os.path.join(TEST_DIR, 'etc/yum.repos.d')
    REPO_FILE = os.path.join(REPO_DIR, 'pulp-test.repo')
    CONFIGURATION = {
        'filesystem':{
            'repo_file':REPO_FILE,
            'mirror_list_dir':MIRROR_DIR,
            'gpg_keys_dir':GPG_DIR,
            'cert_dir':CERT_DIR,
        }
    }

    def setUp(self):
        HandlerTest.setUp(self)
        handler = self.container.find(self.TYPE_ID, role=BIND)
        self.assertTrue(handler is not None, msg='%s handler not loaded' % self.TYPE_ID)
        shutil.rmtree(self.TEST_DIR, ignore_errors=True)
        os.makedirs(self.TEST_DIR)
        os.makedirs(self.REPO_DIR)
        os.makedirs(self.MIRROR_DIR)
        os.makedirs(self.GPG_DIR)
        os.makedirs(self.CERT_DIR)

    def tearDown(self):
        HandlerTest.tearDown(self)
        shutil.rmtree(self.TEST_DIR, ignore_errors=True)

    @patch('pulp_rpm.handler.repolib.Lock')
    def test_bind(self, mock_lock):
        # Test
        options = {}
        conduit = TestConduit(self.CONFIGURATION)
        bindings = [dict(self.BINDING)]
        report = self.dispatcher.bind(conduit, bindings, options)
        # Verify
        self.assertTrue(report.succeeded)
        self.assertTrue(os.path.isfile(self.REPO_FILE))
        repofile = Config(self.REPO_FILE)
        self.assertEqual(repofile[self.REPO_ID]['name'], self.REPO_NAME)
        self.assertEqual(repofile[self.REPO_ID]['enabled'], '1')

    @patch('pulp_rpm.handler.repolib.Lock')
    def test_unbind(self, mock_lock):
        # Setup
        options = {}
        conduit = TestConduit(self.CONFIGURATION)
        bindings = [dict(self.BINDING)]
        self.dispatcher.bind(conduit, bindings, options)
        # Test
        options = {}
        conduit = TestConduit(self.CONFIGURATION)
        bindings = [self.UNBINDING]
        report = self.dispatcher.unbind(conduit, bindings, options)
        # Verify
        self.assertTrue(report.succeeded)
        self.assertTrue(os.path.isfile(self.REPO_FILE))
        repofile = Config(self.REPO_FILE)
        self.assertFalse(self.REPO_ID in repofile)

    @patch('pulp_rpm.handler.repolib.Lock')
    def test_unbind_all(self, mock_lock):
        # Setup
        options = {}
        conduit = TestConduit(self.CONFIGURATION)
        bindings = [dict(self.BINDING)]
        self.dispatcher.bind(conduit, bindings, options)
        # Test
        options = {}
        conduit = TestConduit(self.CONFIGURATION)
        bindings = [dict(self.UNBINDING)]
        bindings[0]['type_id'] = None
        report = self.dispatcher.unbind(conduit, bindings, options)
        # Verify
        self.assertTrue(report.succeeded)
        self.assertTrue(os.path.isfile(self.REPO_FILE))
        repofile = Config(self.REPO_FILE)
        self.assertFalse(self.REPO_ID in repofile)

    @patch('pulp_rpm.handler.repolib.Lock')
    def test_clean(self, mock_lock):
        # Setup
        options = {}
        conduit = TestConduit(self.CONFIGURATION)
        bindings = [dict(self.BINDING)]
        self.dispatcher.bind(conduit, bindings, options)
        self.assertTrue(os.path.isfile(self.REPO_FILE))
        # Test
        self.dispatcher.clean(conduit)
        # Verify
        self.assertFalse(os.path.isfile(self.REPO_FILE))


class TestLinux(HandlerTest):

    TYPE_ID = 'Linux'

    def setUp(self):
        HandlerTest.setUp(self)
        handler = self.container.find(self.TYPE_ID, role=SYSTEM)
        self.assertTrue(handler is not None, msg='%s handler not loaded' % self.TYPE_ID)

    def test_linux(self):
        # TODO: implement test
        pass
