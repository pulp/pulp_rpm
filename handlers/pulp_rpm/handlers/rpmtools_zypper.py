"""
Contains classes used by the RPM handler to perform
operations using zypper.
"""

import zypp
import sys
import traceback
from multiprocessing import Process, Queue

FILE_DEBUG = False
USE_DRY_RUN = False

# Logging
if not FILE_DEBUG:
    from logging import getLogger
    log = getLogger(__name__)
else:
    import logging
    log = logging.getLogger(__name__)
    log.setLevel(logging.DEBUG)

    ch = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    log.addHandler(ch)


def _fix_pkg_names(names):
    """
    While using this classes together with foreman / katello, the package names are
    something like "*:apache2-utils-*-*.*". zypper is not able to handle this. Therefore,
    we are removing "*:" and "-*-*.*"
    :param names: List of packages names
    :type names: list
    :return: New, fixed list of packages
    :rtype: list
    """
    return [str(x.replace('-*-*.*', '').replace('*:', '')) for x in names]


class Zypp:
    """
    Uses the python Zypp binding to install / update / uninstall packages.
    """

    @staticmethod
    def packageInfo(item):
        """
        Collect and return package information as it is required by tx_summary().

        :param item: Package for which Information should be collected
        :type item: PoolItemList
        :return: {resolved=[Package,],deps=[Package,], failed=[Package,]}
        :rtype: dict
        """
        return dict(
            qname=item.name(),
            repoid=item.repoInfo().alias(),
            name=item.name(),
            version=item.edition().version(),
            release=item.edition().release(),
            arch=str(item.arch()),
            epoch=item.edition().epoch()
        )

    def __init__(self):
        """
        Initialize Zypp and load all enabled repositories.
        """
        self.Z = zypp.ZYppFactory_instance().getZYpp()

        # Load system rooted at "/"...
        self.Z.initializeTarget(zypp.Pathname("/"))
        self.Z.target().load()

        # Load all enabled repositories...
        repoManager = zypp.RepoManager()
        for repo in repoManager.knownRepositories():
            if not repo.enabled():
                continue
            if not repoManager.isCached(repo):
                repoManager.buildCache(repo)
            repoManager.loadFromCache(repo)

        # Now all installed and available items are in the pool:
        log.debug("Known items: %d" % (self.Z.pool().size()))

    def poolInstall(self, capstr):
        """
        Install capability specified by capstr.

        :param capstr: Capability to install
        :type capstr: str
        """
        log.debug("Request: install %s", capstr)
        self.Z.resolver().addRequire(zypp.Capability(capstr))

    def poolUpdate(self, capstr):
        """
        Update capability specified by capstr.

        :param capstr: Capability to update
        :type capstr: str
        """
        log.debug("Request: update %s", capstr)
        self.Z.resolver().addRequire(zypp.Capability(capstr))

    def poolRemove(self, capstr):
        """
        Remove capability specified by capstr.

        :param capstr: Capability to remove
        :type capstr: str
        """
        log.debug("Request: delete %s", capstr)
        self.Z.resolver().addConflict(zypp.Capability(capstr))

    def poolUpdateAll(self):
        """
        Update all
        """
        log.debug("Request: update")
        self.Z.resolver().doUpdate()

    def tx_summary(self, action):
        """
        Get transaction summary.

        :param action: Could be install, update or uninstall
        :type action: str
        :return: {resolved=[Package,],deps=[Package,], failed=[Package,]}
        :rtype: tuple
        """
        count_transactions = 0
        todo = self.Z.pool().getTransaction()

        deps = []
        resolved = []
        failed = []

        if action == "install" or action == "update":

            for item in todo._toInstall:
                count_transactions += 1
                log.debug('++ %s | %s-%s | %s',
                          item.repoInfo().alias(), item.name(), item.edition(), item.status())
                p = Zypp.packageInfo(item)
                resolved.append(p)

        elif action == "uninstall":

            for item in todo._toDelete:
                count_transactions += 1
                log.debug('-- %s | %s-%s | %s',
                          item.repoInfo().alias(), item.name(), item.edition(), item.status())
                p = Zypp.packageInfo(item)
                resolved.append(p)

        else:
            log.error("Unknown action %s", action)

        if count_transactions == 0:
            log.warning("No transaction is necessary. Means, no install / uninstall happens")
        else:
            log.debug("Therea are %d transaction(s) necessary", count_transactions)

        return dict(resolved=resolved, deps=deps, failed=failed)

    def poolResolve(self):
        """
        Resolve the dependencies of a package. This does store the tasks
        of how to install / uninstall a package in the pool itself.

        :return: True if resolving the dependencies was successful
        :rtype: bool
        """
        log.debug("Resolve pool")

        result = self.Z.resolver().resolvePool()

        if not result:
            # Print _all_ problems and possible solutions:
            problems = self.Z.resolver().problems()
            pn = 0
            for problem in problems:
                pn += 1
                if problem.details():
                    log.warning("Problem: %d\nDesc:\n%s\nDetails:\n%s",
                                pn, problem.description(), problem.details())
                else:
                    log.warning("Problem: %d\nDesc:\n%s\nDetails:\n(no details)",
                                pn, problem.description())
                sn = 0

                for solution in problem.solutions():
                    sn += 1
                    if solution.details():
                        log.warning("Solution %d.%d\nDesc:\n%s\nDetails:\n%s",
                                    pn, sn, solution.description(), solution.details())
                    else:
                        log.warning("Solution %d.%d\nDesc:\n%s\nDetails:\n(no details)",
                                    pn, sn, solution.description())

        return result

    def poolCommit(self, dryrun):
        """
        Commit the transaction. This does actually install / update / uninstall.

        :param dryrun: Dry-Run the action but don't change anything on the system.
        :type dryrun: bool
        """
        result = False

        policy = zypp.ZYppCommitPolicy()

        policy.syncPoolAfterCommit(False)

        if dryrun:
            log.debug("Use dry run to commit the ZYpp policy.")

        policy.dryRun(dryrun)
        result = self.Z.commit(policy)
        log.info("%s", result)

    def finish(self):
        """
        Finish and cleanup Zypp
        """
        self.Z.finishTarget()
        del(self.Z)


class Package:
    """
    Package management.
    Returned *Package* NEVRA+ objects:
      - qname   : qualified name
      - repoid  : repository id
      - name    : package name
      - epoch   : package epoch
      - version : package version
      - release : package release
      - arch    : package arch
    """

    def __init__(self, apply=True, importkeys=False, progress=None):
        """
        :param apply: Apply changes (not dry-run).
        :type apply: bool
        :param importkeys: Allow the import of GPG keys.
        :type importkeys: bool
        :param progress: A progress report.
        :type progress: ProgressReport
        """
        self.apply = apply
        self.importkeys = importkeys
        self.progress = progress

    def _install_p(self, names, q):
        result = None

        z = Zypp()
        for package in names:
            log.info('Want to install package %s', package)
            z.poolInstall(package)

        if z.poolResolve():
            result = z.tx_summary("install")
            z.poolCommit(USE_DRY_RUN)
        z.finish()
        q.put(result)

    def install(self, names):
        """
        Install packages by name.

        :param names: A list of package names.
        :type names: [str,]
        :return: Packages installed.
            {resolved=[Package,],deps=[Package,], failed=[Package,]}
        :rtype: dict
        """

        result = None
        names = _fix_pkg_names(names)

        try:
            log.debug("Starting process for installing %s", names)

            q = Queue()
            p = Process(target=self._install_p, args=(names, q, ))
            p.start()

            p.join()
            result = q.get()
        except Exception:
            var = traceback.format_exc()
            log.error("Exception happend during install: %s", var)
        finally:
            log.debug("Install transaction finished.")

        return result

    def _uninstall_p(self, names, q):
        z = Zypp()
        for package in names:
            log.info('Want to uninstall package %s', package)
            z.poolRemove(package)

        if z.poolResolve():
            result = z.tx_summary("uninstall")
            z.poolCommit(USE_DRY_RUN)
        z.finish()
        q.put(result)

    def uninstall(self, names):
        """
        Uninstall (erase) packages by name.

        :param names: A list of package names to be removed.
        :type names: list
        :return: Packages uninstalled (erased).
            {resolved=[Package,],deps=[Package,], failed=[Package,]}
        :rtype: dict
        """

        result = None

        # TODO: looks like that this is not necessary for "uninstall". Only str() is required!
        names = _fix_pkg_names(names)

        try:
            log.debug("Starting process for uninstalling %s", names)

            q = Queue()
            p = Process(target=self._uninstall_p, args=(names, q, ))
            p.start()

            p.join()
            result = q.get()
        except Exception:
            var = traceback.format_exc()
            log.error("Exception happend during uninstall: %s", var)
        finally:
            log.debug("Uninstall transaction finished.")

        return result

    def _update_p(self, names, q):
        z = Zypp()
        if names:
            for package in names:
                log.info('Want to update package %s', package)
                z.poolUpdate(package)

                if z.poolResolve():
                    result = z.tx_summary("update")
                    z.poolCommit(USE_DRY_RUN)
        else:
            log.info('Want to update all packages')
            z.poolUpdateAll()
            result = z.tx_summary("update")
            z.poolCommit(USE_DRY_RUN)
        z.finish()
        q.put(result)

    def update(self, names=()):
        """
        Update installed packages.
        When (names) is not specified, all packages are updated.

        :param names: A list of package names.
        :type names: [str,]
        :return: Packages installed (updated).
            {resolved=[Package,],deps=[Package,], failed=[Package,]}
        :rtype: dict
        """

        result = None

        # TODO: looks like that this is not necessary for "update". Only str() is required!
        names = _fix_pkg_names(names)

        try:
            log.debug("Starting process for updating %s", names)

            q = Queue()
            p = Process(target=self._update_p, args=(names, q, ))
            p.start()

            p.join()
            result = q.get()
        except Exception:
            var = traceback.format_exc()
            log.error("Exception happend during update: %s", var)
        finally:
            log.debug("Update transaction finished.")

        return result

    def update_minimal(self, advisories=[]):
        """
        Update installed packages.
        When (names) is not specified, all packages are updated.

        :param advisories: A list of advisory ids.
        :type advisories: [str,]
        :return: Packages installed (updated).
            {resolved=[Package,],deps=[Package,], failed=[Package,]}
        :rtype: dict
        """

        # As far as I can see, there is no difference between update and
        # update_minimal in zypper

        result = None

        # TODO: looks like that this is not necessary for "update_minimal". Only str() is required!
        advisories = _fix_pkg_names(advisories)

        try:
            log.debug("Starting process for updating %s (minimal)", advisories)

            q = Queue()
            p = Process(target=self._update_p, args=(advisories, q, ))
            p.start()

            p.join()
            result = q.get()
        except Exception:
            var = traceback.format_exc()
            log.error("Exception happend during update minimal: %s", var)
        finally:
            log.debug("Update minimal transaction finished.")

        return result


class PackageGroup:
    """
    PackageGroup management.
    """

    def __init__(self, apply=True, importkeys=False, progress=None):
        """
        :param apply: Apply changes (not dry-run).
        :type apply: bool
        :param importkeys: Allow the import of GPG keys.
        :type importkeys: bool
        """
        self.apply = apply
        self.importkeys = importkeys
        self.progress = progress

    def _install_p(self, names, q):
        z = Zypp()
        for pattern in names:
            log.info('Want to install group with pattern %s', pattern)
            z.poolInstall("pattern:" + pattern)

        if z.poolResolve():
            result = z.tx_summary("install")
            z.poolCommit(USE_DRY_RUN)
        z.finish()
        q.put(result)

    def install(self, names):
        """
        Install package groups by name.

        :param names: A list of package group names.
        :type names: list
        :return: Packages installed.
            {resolved=[Package,],deps=[Package,], failed=[Package,]}
        :rtype: dict
        """
        result = None

        # TODO: looks like that this is not necessary for package groups. Only str() is required!
        names = _fix_pkg_names(names)

        try:
            log.debug("Starting process for installing group %s", names)

            q = Queue()
            p = Process(target=self._install_p, args=(names, q, ))
            p.start()

            p.join()
            result = q.get()
        except Exception:
            var = traceback.format_exc()
            log.error("Exception happend during installation of group: %s", var)
        finally:
            log.debug("Group install transaction finished.")

        return result

    def _uninstall_p(self, names, q):
        z = Zypp()
        for pattern in names:
            log.info('Want to uninstall group %s', pattern)
            z.poolRemove("pattern:" + pattern)

        if z.poolResolve():
            result = z.tx_summary("uninstall")
            z.poolCommit(USE_DRY_RUN)
        z.finish()
        q.put(result)

    def uninstall(self, names):
        """
        Uninstall package groups by name.

        :param names: A list of package group names.
        :type names: [str,]
        :return: Packages uninstalled.
            {resolved=[Package,],deps=[Package,], failed=[Package,]}
        :rtype: dict
        """
        result = None

        # TODO: looks like that this is not necessary for package groups. Only str() is required!
        names = _fix_pkg_names(names)

        try:
            log.debug("Starting process for uninstalling group %s", names)

            q = Queue()
            p = Process(target=self._uninstall_p, args=(names, q, ))
            p.start()

            p.join()
            result = q.get()
        except Exception:
            var = traceback.format_exc()
            log.error("Exception happend during uninstallation of group: %s", var)
        finally:
            log.debug("Group uninstall transaction finished.")

        return result


class ProgressReport:
    """
    Package (and group) progress reporting object.

    :ivar step: A list package steps.
        Each step is: (name, status)
    :type step: tuple
    :ivar details: Details about package actions taking place
        in the current step.
    """
    PENDING = None
    SUCCEEDED = True
    FAILED = False

    def __init__(self):
        """
        Constructor.
        """
        self.steps = []
        self.details = {}

    def push_step(self, name):
        """
        Push the specified step.

        First, update the last status to SUCCEEDED.
        :param name: The step name to push.
        :type name: str
        """
        self.set_status(self.SUCCEEDED)
        self.steps.append([name, self.PENDING])
        self.details = {}
        self._updated()

    def set_status(self, status):
        """
        Update the status of the current step.

        :param status: The status.
        :type status: bool
        """
        if not self.steps:
            return
        last = self.steps[-1]
        if last[1] is self.PENDING:
            last[1] = status
            self.details = {}
            self._updated()

    def set_action(self, action, package):
        """
        Set the specified package action for the current step.

        :param action: The action being performed.
        :type action: str
        """
        self.details = dict(action=action, package=str(package))
        self._updated()

    def error(self, msg):
        """
        Report an error on the current step.

        :param msg: The error message to report.
        :type msg: str
        """
        self.set_status(self.FAILED)
        self.details = dict(error=msg)
        self._updated()

    def _updated(self):
        """
        Notification that the report has been updated.
        Designed to be overridden and reported.
        """
        log.info('Progress [%s]:\n%s', self.steps, self.details)
