"""Tests for the retention policy feature of repositories."""

from collections import defaultdict

from pulp_smash.pulp3.bindings import (
    delete_orphans,
    monitor_task,
    PulpTestCase,
)
from pulp_smash.pulp3.utils import (
    gen_repo,
    get_added_content_summary,
    get_content,
    get_content_summary,
    get_removed_content,
    get_removed_content_summary,
)

from pulp_rpm.tests.functional.constants import (
    PULP_TYPE_PACKAGE,
    RPM_FIXTURE_SUMMARY,
    RPM_PACKAGE_COUNT,
    RPM_MODULAR_PACKAGE_COUNT,
    RPM_MODULES_STATIC_CONTEXT_FIXTURE_URL,
    RPM_MODULAR_STATIC_FIXTURE_SUMMARY,
)
from pulp_rpm.tests.functional.utils import (
    gen_rpm_client,
    gen_rpm_remote,
)
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401

from pulpcore.client.pulp_rpm import (
    RepositoriesRpmApi,
    RpmRepositorySyncURL,
    RemotesRpmApi,
)
from pulpcore.client.pulp_rpm.exceptions import ApiException


class RetentionPolicyTestCase(PulpTestCase):
    """Verify functionality of the "retain_package_versions" setting on a Repository."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.client = gen_rpm_client()
        cls.repo_api = RepositoriesRpmApi(cls.client)
        cls.remote_api = RemotesRpmApi(cls.client)

    def test_sync_with_retention(self):
        """Verify functionality with sync.

        Do the following:

        1. Create a repository, and a remote.
        2. Sync the remote.
        3. Assert that the correct number of units were added and are present
           in the repo.
        4. Change the "retain_package_versions" on the repository to 1 (retain the latest
           version only).
        5. Sync the remote one more time.
        6. Assert that repository version is different from the previous one.
        7. Assert the repository version we end with has only one version of each package.
        """
        delete_orphans()

        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        remote = self.remote_api.create(gen_rpm_remote(policy="on_demand"))
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        task = self.sync(repository=repo, remote=remote, optimize=False)
        repo = self.repo_api.read(repo.pulp_href)

        # Test that, by default, everything is retained / nothing is tossed out.
        self.assertDictEqual(get_content_summary(repo.to_dict()), RPM_FIXTURE_SUMMARY)
        self.assertDictEqual(get_added_content_summary(repo.to_dict()), RPM_FIXTURE_SUMMARY)
        # Test that the # of packages processed is correct
        reports = self.get_progress_reports_by_code(task)
        self.assertEqual(reports["sync.parsing.packages"].total, RPM_PACKAGE_COUNT)

        # Set the retention policy to retain only 1 version of each package
        repo_data = repo.to_dict()
        repo_data.update({"retain_package_versions": 1})
        self.repo_api.update(repo.pulp_href, repo_data)
        repo = self.repo_api.read(repo.pulp_href)

        task = self.sync(repository=repo, remote=remote, optimize=False)
        repo = self.repo_api.read(repo.pulp_href)

        # Test that only one version of each package is present
        self.assertTrue(
            self.check_retention_policy(get_content(repo.to_dict())[PULP_TYPE_PACKAGE], 1)
        )
        # Test that (only) 4 RPMs were removed (no advisories etc. touched)
        self.assertDictEqual(get_removed_content_summary(repo.to_dict()), {PULP_TYPE_PACKAGE: 4})
        # Test that the versions that were removed are the versions we expect.
        versions_for_packages = self.versions_for_packages(
            get_removed_content(repo.to_dict())[PULP_TYPE_PACKAGE]
        )
        self.assertDictEqual(
            versions_for_packages,
            {"duck": ["0.6", "0.7"], "kangaroo": ["0.2"], "walrus": ["0.71"]},
            versions_for_packages,
        )
        # Test that the number of packages processed is correct (doesn't include older ones)
        reports = self.get_progress_reports_by_code(task)
        self.assertEqual(reports["sync.parsing.packages"].total, RPM_PACKAGE_COUNT)
        self.assertEqual(reports["sync.skipped.packages"].total, 4)

    def test_sync_with_retention_and_modules(self):
        """Verify functionality with sync.

        Do the following:

        1. Create a repository, and a remote.
        2. Sync the remote.
        3. Assert that the correct number of units were added and are present in the repo.
        4. Change the "retain_package_versions" on the repository to 1 (retain the latest
           version only).
        5. Sync the remote one more time.
        6. Assert that repository version is the same as the previous one, because the older
           versions are part of modules, and they should be ignored by the retention policy.
        """
        delete_orphans()

        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        remote = self.remote_api.create(
            gen_rpm_remote(
                url=RPM_MODULES_STATIC_CONTEXT_FIXTURE_URL,
                policy="on_demand",
            )
        )
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        task = self.sync(repository=repo, remote=remote, optimize=False)
        repo = self.repo_api.read(repo.pulp_href)

        self.addCleanup(delete_orphans)  # TODO: #2587

        # Test that, by default, everything is retained / nothing is tossed out.
        self.assertDictEqual(
            get_content_summary(repo.to_dict()), RPM_MODULAR_STATIC_FIXTURE_SUMMARY
        )
        self.assertDictEqual(
            get_added_content_summary(repo.to_dict()), RPM_MODULAR_STATIC_FIXTURE_SUMMARY
        )
        # Test that the # of packages processed is correct
        reports = self.get_progress_reports_by_code(task)
        self.assertEqual(reports["sync.parsing.packages"].total, RPM_MODULAR_PACKAGE_COUNT)
        self.assertEqual(reports["sync.skipped.packages"].total, 0)

        # Set the retention policy to retain only 1 version of each package
        repo_data = repo.to_dict()
        repo_data.update({"retain_package_versions": 1})
        self.repo_api.update(repo.pulp_href, repo_data)
        repo = self.repo_api.read(repo.pulp_href)

        task = self.sync(repository=repo, remote=remote, optimize=False)
        repo = self.repo_api.read(repo.pulp_href)

        # Test that no RPMs were removed (and no advisories etc. touched)
        # it should be the same because the older version are covered by modules)
        self.assertDictEqual(get_removed_content_summary(repo.to_dict()), {})
        # Test that the number of packages processed is correct
        reports = self.get_progress_reports_by_code(task)
        self.assertEqual(reports["sync.parsing.packages"].total, RPM_MODULAR_PACKAGE_COUNT)
        self.assertEqual(reports["sync.skipped.packages"].total, 0)

    def test_mirror_sync_with_retention_fails(self):
        """Verify functionality with sync.

        Do the following:

        1. Create a repository with 'retain_package_versions' set, and a remote.
        2. Sync the remote in mirror mode.
        3. Assert that the sync fails.
        """
        repo_data = gen_repo()
        repo_data.update({"retain_package_versions": 1})
        repo = self.repo_api.create(repo_data)
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        remote = self.remote_api.create(gen_rpm_remote())
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        with self.assertRaises(ApiException) as exc:
            self.sync(repository=repo, remote=remote, optimize=False, mirror=True)
            self.assertEqual(exc.code, 400)

    def get_progress_reports_by_code(self, task):
        """Return the progress reports in a dictionary keyed by codename."""
        return {report.code: report for report in task.progress_reports}

    def versions_for_packages(self, packages):
        """Get a list of versions for each package present in a list of Package dicts.

        Args:
            packages: List of Package info dicts
        """
        packages_by_version = defaultdict(list)

        for package in packages:
            packages_by_version[package["name"]].append(package["version"])

        for pkg_list in packages_by_version.values():
            pkg_list.sort()

        return packages_by_version

    def check_retention_policy(self, packages, retain_package_versions):
        """Check that the number of versions of each package <= permitted number.

        Args:
            packages: List of Package info dicts
            retention_policy: Number of package versions permitted.
        """
        return all(
            [
                len(versions) <= retain_package_versions
                for versions in self.versions_for_packages(packages).values()
            ]
        )

    def sync(self, repository, remote, optimize=True, mirror=False):
        """Sync a repository and return the task.

        Args:
            repository (pulp_rpm.app.models.repository.RpmRepository):
                object of RPM repository
            remote (pulp_rpm.app.models.repository.RpmRemote):
                object of RPM Remote
            optimize (bool):
                whether to enable optimized sync
            mirror (bool):
                whether to use mirror-mode sync
        Returns (list):
            list of the ProgressReport objects created from this sync
        """
        repository_sync_data = RpmRepositorySyncURL(
            remote=remote.pulp_href, optimize=optimize, mirror=mirror
        )
        sync_response = self.repo_api.sync(repository.pulp_href, repository_sync_data)
        return monitor_task(sync_response.task)
