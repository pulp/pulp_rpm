import mock

from yum import constants
from yum.Errors import InstallError, GroupsError

# A list of "install-only" packages that is used in deciding transaction states in some cases.
# It is defined in the yum python lib as `yum.config.YumConf.installonlypkgs.default`.
INSTALLONLY_PKGS = ['kernel']


def install():
    import yum

    yum.YumBase = YumBase


class Pkg:
    ARCH = 'noarch'

    def __init__(self, name, version, release='1', arch=ARCH):
        self.name = name
        self.ver = version
        self.rel = str(release)
        self.arch = arch
        self.epoch = '0'

    def __str__(self):
        if int(self.epoch) > 0:
            format = '%(epoch)s:%(name)s-%(ver)s-%(rel)s.%(arch)s'
        else:
            format = '%(name)s-%(ver)s-%(rel)s.%(arch)s'
        return format % self.__dict__


class TxMember:
    def __init__(self, state, repoid, pkg, isDep=0):
        self.output_state = state
        self.repoid = repoid
        self.isDep = isDep
        self.po = pkg


class Config(object):
    pass


class YumBase:
    FAILED_PKG = '__failed__'
    UNKNOWN_PKG = '__unknown__'

    NEED_UPDATE = [
        Pkg('openssl', '3.2'),
        Pkg('libc', '2.5'),
        Pkg('kernel', '3.10.0'),
    ]

    INSTALL_DEPS = [
        Pkg('dep1', '3.2'),
        Pkg('dep2', '2.5'),
    ]

    UPDATE_DEPS = [
        Pkg('dep1', '3.2'),
        Pkg('dep2', '2.5'),
    ]

    ERASE_DEPS = [
        Pkg('dep1', '3.2'),
        Pkg('dep2', '2.5'),
    ]

    TRUEINSTALL_DEPS = []

    STATES = {
        constants.TS_INSTALL: INSTALL_DEPS,
        constants.TS_TRUEINSTALL: TRUEINSTALL_DEPS,
        constants.TS_UPDATE: UPDATE_DEPS,
        constants.TS_ERASE: ERASE_DEPS,
    }

    REPOID = 'fedora'

    GROUPS = {
        'plain': [
            Pkg('zsh', '3.2'),
            Pkg('xchat', '1.3'),
            Pkg('thunderbird', '10.1.7'),
            Pkg('kernel', '3.10.0'),
        ],
        'plain-failed': [
            Pkg('zsh', '3.2'),
            Pkg('xchat', '1.3'),
            Pkg('thunderbird', '10.1.7'),
            Pkg('kernel', '3.10.0'),
            Pkg(FAILED_PKG, '6.3'),
        ],
        'pulp': [
            Pkg('okaara', '0.25'),
            Pkg('gofer', '0.70', '2'),
            Pkg('mongo', '1.3.2'),
            Pkg('qpid', '0.70'),
        ],
    }

    def process_transaction(self, *args, **kwargs):
        for t in self.tsInfo:
            if t.po.name == self.FAILED_PKG:
                t.output_state = constants.TS_FAILED

    doPluginSetup = mock.Mock()
    registerCommand = mock.Mock()
    processTransaction = mock.Mock(side_effect=process_transaction)
    close = mock.Mock()
    closeRpmDB = mock.Mock()

    @classmethod
    def reset(cls):
        cls.doPluginSetup.reset_mock()
        cls.registerCommand.reset_mock()
        cls.processTransaction = mock.Mock(side_effect=cls.process_transaction)
        cls.close.reset_mock()
        cls.closeRpmDB.reset_mock()

    def __init__(self, *args, **kwargs):
        self.conf = Config()
        self.preconf = Config()
        self.tsInfo = []
        self.repos = mock.Mock()

    def _tx_member_for_instup(self, pkg, update=False):
        # When installing or updating a package, packages in yum's "installonlypkgs" list
        # have a special transaction state, as these are the packages that are never updated.
        # Instead, they have multiple versions installed (e.g. kernel packages). This encapsulates
        # the logic for the yum test mock: If one of the installonlypkgs is being installed or
        # updated, use the special transaction state represented by TS_TRUEINSTALL. Otherwise,
        # return the TS_INSTALL state if installing (update kwarg is False), or TS_UPDATE if
        # updating (update kwarg is True).
        if pkg.name in INSTALLONLY_PKGS:
            t = TxMember(constants.TS_TRUEINSTALL, self.REPOID, pkg)
        else:
            if update:
                t = TxMember(constants.TS_UPDATE, self.REPOID, pkg)
            else:
                t = TxMember(constants.TS_INSTALL, self.REPOID, pkg)
        return t

    def install(self, pattern):
        if YumBase.UNKNOWN_PKG in pattern:
            name = u'D' + unichr(246) + 'g'
            raise InstallError('package %s not found' % name)
        pkg = Pkg(pattern, '1.0')
        t = self._tx_member_for_instup(pkg)
        self.tsInfo.append(t)

    def update(self, pattern=None):
        # all
        if not pattern:
            for pkg in self.NEED_UPDATE:
                t = self._tx_member_for_instup(pkg, update=True)
                self.tsInfo.append(t)
            return
        # specific package
        if YumBase.UNKNOWN_PKG in pattern:
            return []
        pkg = Pkg(pattern, '1.0')
        t = self._tx_member_for_instup(pkg, update=True)
        self.tsInfo.append(t)

    def remove(self, pattern):
        if YumBase.UNKNOWN_PKG in pattern:
            return []
        pkg = Pkg(pattern, '1.0')
        t = TxMember(constants.TS_ERASE, self.REPOID, pkg)
        self.tsInfo.append(t)

    def selectGroup(self, name):
        grp = self.GROUPS.get(name)
        if grp is None:
            raise GroupsError('Group not found')
        for pkg in grp:
            t = self._tx_member_for_instup(pkg)
            self.tsInfo.append(t)

    def groupRemove(self, name):
        grp = self.GROUPS.get(name)
        if grp is None:
            raise GroupsError('Group not found')
        for pkg in grp:
            t = TxMember(constants.TS_ERASE, self.REPOID, pkg)
            self.tsInfo.append(t)

    def resolveDeps(self):
        deps = {}
        for t in self.tsInfo:
            deps[t.output_state] = self.STATES[t.output_state]
        for state, pkglist in deps.items():
            for pkg in pkglist:
                t = TxMember(state, self.REPOID, pkg, 1)
                self.tsInfo.append(t)
