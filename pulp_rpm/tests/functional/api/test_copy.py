"""Tests that sync rpm plugin repositories."""

import pytest

from pulp_rpm.tests.functional.constants import (
    PULP_TYPE_PACKAGE,
    RPM_FIXTURE_SUMMARY,
    RPM_KICKSTART_FIXTURE_SUMMARY,
    RPM_MODULAR_FIXTURE_URL,
    RPM_MODULAR_STATIC_FIXTURE_SUMMARY,
    RPM_MODULES_STATIC_CONTEXT_FIXTURE_URL,
)

from pulpcore.client.pulp_rpm import Copy
from pulpcore.client.pulp_rpm.exceptions import ApiException
import subprocess


def noop(uri):
    return uri


def get_prn(uri):
    """Utility to get prn without having to setup django."""
    commands = f"from pulpcore.app.util import get_prn; print(get_prn(uri='{uri}'));"
    process = subprocess.run(["pulpcore-manager", "shell", "-c", commands], capture_output=True)
    assert process.returncode == 0
    prn = process.stdout.decode().strip()
    return prn


@pytest.mark.parametrize("get_id", [noop, get_prn], ids=["without-prn", "with-prn"])
@pytest.mark.parallel
def test_modular_static_context_copy(
    init_and_sync,
    monitor_task,
    rpm_copy_api,
    rpm_modulemd_api,
    rpm_repository_factory,
    rpm_repository_api,
    get_id,
    get_content_summary,
):
    """Test copying a static_context-using repo to an empty destination."""
    src, _ = init_and_sync(url=RPM_MODULES_STATIC_CONTEXT_FIXTURE_URL)
    dest = rpm_repository_factory()

    data = Copy(
        config=[
            {
                "source_repo_version": get_id(src.latest_version_href),
                "dest_repo": get_id(dest.pulp_href),
            }
        ],
        dependency_solving=False,
    )
    monitor_task(rpm_copy_api.copy_content(data).task)

    # Check that we have the correct content counts.
    dest = rpm_repository_api.read(dest.pulp_href)
    content_summary = get_content_summary(dest)
    assert content_summary["present"] == RPM_MODULAR_STATIC_FIXTURE_SUMMARY
    assert content_summary["added"] == RPM_MODULAR_STATIC_FIXTURE_SUMMARY

    modules = rpm_modulemd_api.list(repository_version=get_id(dest.latest_version_href)).results
    module_static_contexts = [
        (module.name, module.version) for module in modules if module.static_context
    ]
    assert len(module_static_contexts) == 2


class TestCopyWithUnsignedRepoSyncedImmediate:
    def test_basic_copy_all(
        self,
        monitor_task,
        rpm_copy_api,
        rpm_repository_factory,
        rpm_repository_api,
        rpm_unsigned_repo_immediate,
        get_content_summary,
    ):
        """Test copying all the content from one repo to another."""
        src = rpm_unsigned_repo_immediate
        dest = rpm_repository_factory()

        data = Copy(
            config=[{"source_repo_version": src.latest_version_href, "dest_repo": dest.pulp_href}],
            dependency_solving=False,
        )
        monitor_task(rpm_copy_api.copy_content(data).task)

        # Check that we have the correct content counts.
        dest = rpm_repository_api.read(dest.pulp_href)
        content_summary = get_content_summary(dest)
        assert content_summary["present"] == RPM_FIXTURE_SUMMARY
        assert content_summary["added"] == RPM_FIXTURE_SUMMARY

    def test_copy_none(
        self,
        monitor_task,
        rpm_copy_api,
        rpm_repository_api,
        rpm_repository_factory,
        rpm_unsigned_repo_immediate,
    ):
        """Test copying NO CONTENT from one repo to another."""
        src = rpm_unsigned_repo_immediate
        dest = rpm_repository_factory()

        data = Copy(
            config=[
                {
                    "source_repo_version": src.latest_version_href,
                    "dest_repo": dest.pulp_href,
                    "content": [],
                }
            ],
            dependency_solving=False,
        )
        monitor_task(rpm_copy_api.copy_content(data).task)

        dest = rpm_repository_api.read(dest.pulp_href)
        # Check that no new repo-version was created in dest_repo
        assert "{}versions/0/".format(dest.pulp_href) == dest.latest_version_href

    def test_invalid_config(
        self,
        rpm_copy_api,
        rpm_repository_api,
        rpm_repository_factory,
        rpm_unsigned_repo_immediate,
    ):
        """Test invalid config."""
        src = rpm_unsigned_repo_immediate
        dest = rpm_repository_factory()

        with pytest.raises(ApiException):
            # no list
            data = Copy(
                config={
                    "source_repo_version": src.latest_version_href,
                    "dest_repo": dest.pulp_href,
                },
                dependency_solving=False,
            )
            rpm_copy_api.copy_content(data)

        with pytest.raises(ApiException):
            good = {
                "source_repo_version": src.latest_version_href,
                "dest_repo": dest.pulp_href,
            }
            bad = {"source_repo_version": src.latest_version_href}
            data = Copy(config=[good, bad], dependency_solving=False)
            rpm_copy_api.copy_content(data)

        with pytest.raises(ApiException):
            data = Copy(
                config=[{"source_repo": src.latest_version_href, "dest_repo": dest.pulp_href}],
                dependency_solving=False,
            )
            rpm_copy_api.copy_content(data)

    @pytest.mark.parametrize("get_id", [noop, get_prn], ids=["without-prn", "with-prn"])
    def test_content(
        self,
        monitor_task,
        rpm_advisory_api,
        rpm_copy_api,
        rpm_repository_api,
        rpm_repository_factory,
        rpm_unsigned_repo_immediate,
        get_id,
    ):
        """Test the content parameter."""
        src = rpm_unsigned_repo_immediate

        content = rpm_advisory_api.list(repository_version=src.latest_version_href).results
        content_to_copy = (get_id(content[0].pulp_href), get_id(content[1].pulp_href))

        dest = rpm_repository_factory()

        data = Copy(
            config=[
                {
                    "source_repo_version": get_id(src.latest_version_href),
                    "dest_repo": get_id(dest.pulp_href),
                    "content": content_to_copy,
                }
            ],
            dependency_solving=False,
        )
        monitor_task(rpm_copy_api.copy_content(data).task)

        dest = rpm_repository_api.read(dest.pulp_href)
        dc = rpm_advisory_api.list(repository_version=dest.latest_version_href)
        dest_content = [get_id(c.pulp_href) for c in dc.results]

        assert sorted(content_to_copy) == sorted(dest_content)

    def test_all_content_recursive(
        self,
        monitor_task,
        rpm_advisory_api,
        rpm_copy_api,
        rpm_package_api,
        rpm_repository_factory,
        rpm_repository_api,
        rpm_unsigned_repo_immediate,
    ):
        """Test requesting all-rpm-update-content/recursive (see #6519)."""
        src = rpm_unsigned_repo_immediate
        dest = rpm_repository_factory()

        advisory_content = rpm_advisory_api.list(repository_version=src.latest_version_href)
        advisories_to_copy = [rslt.pulp_href for rslt in advisory_content.results]

        rpm_content = rpm_package_api.list(repository_version=src.latest_version_href)
        rpms_to_copy = [rslt.pulp_href for rslt in rpm_content.results]

        content_to_copy = set()
        content_to_copy.update(advisories_to_copy)
        content_to_copy.update(rpms_to_copy)

        data = Copy(
            config=[
                {
                    "source_repo_version": src.latest_version_href,
                    "dest_repo": dest.pulp_href,
                    "content": list(content_to_copy),
                }
            ],
            dependency_solving=True,
        )
        monitor_task(rpm_copy_api.copy_content(data).task)

        dest = rpm_repository_api.read(dest.pulp_href)

        # check advisories copied
        dc = rpm_advisory_api.list(repository_version=dest.latest_version_href)
        dest_content = [c.pulp_href for c in dc.results]
        assert sorted(advisories_to_copy) == sorted(dest_content)

        # check rpms copied
        dc = rpm_package_api.list(repository_version=dest.latest_version_href)
        dest_content = [c.pulp_href for c in dc.results]
        assert sorted(rpms_to_copy) == sorted(dest_content)

    def test_strict_copy_package_to_empty_repo(
        self,
        monitor_task,
        rpm_copy_api,
        rpm_package_api,
        rpm_repository_api,
        rpm_repository_factory,
        rpm_unsigned_repo_immediate,
    ):
        """Test copy package and its dependencies to empty repository.

        - Create repository and populate it
        - Create empty repository
        - Use 'copy' to copy 'whale' package with dependencies
        - assert package and its dependencies were copied
        """
        empty_repo = rpm_repository_factory()
        repo = rpm_unsigned_repo_immediate

        packages = rpm_package_api.list(repository_version=repo.latest_version_href, name="whale")
        package_to_copy = [packages.results[0].pulp_href]

        data = Copy(
            config=[
                {
                    "source_repo_version": repo.latest_version_href,
                    "dest_repo": empty_repo.pulp_href,
                    "content": package_to_copy,
                }
            ],
            dependency_solving=True,
        )
        monitor_task(rpm_copy_api.copy_content(data).task)

        empty_repo = rpm_repository_api.read(empty_repo.pulp_href)
        packages = rpm_package_api.list(repository_version=empty_repo.latest_version_href).results
        packages = [package.name for package in packages]

        # assert that only 3 packages are copied (original package with its two dependencies)
        assert len(packages) == 3
        # assert dependencies package names
        for dependency in ["shark", "stork"]:
            assert dependency in packages

    def test_strict_copy_packagecategory_to_empty_repo(
        self,
        monitor_task,
        rpm_copy_api,
        rpm_package_api,
        rpm_package_category_api,
        rpm_package_groups_api,
        rpm_repository_api,
        rpm_repository_factory,
        rpm_unsigned_repo_immediate,
    ):
        """Test copy package and its dependencies to empty repository.

        - Create repository and populate it
        - Create empty destination repository
        - Use 'copy' to copy packagecategory recursively
        - assert packagecategory and its dependencies were copied
        """
        dest_repo = rpm_repository_factory()
        repo = rpm_unsigned_repo_immediate

        package_categories = rpm_package_category_api.list(
            repository_version=repo.latest_version_href
        )
        package_category_to_copy = [package_categories.results[0].pulp_href]
        # repository content counts
        repo_packagecategories_count = package_categories.count
        repo_packagegroups_count = rpm_package_groups_api.list(
            repository_version=repo.latest_version_href
        ).count

        # do the copy
        data = Copy(
            config=[
                {
                    "source_repo_version": repo.latest_version_href,
                    "dest_repo": dest_repo.pulp_href,
                    "content": package_category_to_copy,
                }
            ],
            dependency_solving=True,
        )
        monitor_task(rpm_copy_api.copy_content(data).task)

        # copied repository content counts
        dest_repo = rpm_repository_api.read(dest_repo.pulp_href)
        dest_repo_packages = rpm_package_api.list(repository_version=dest_repo.latest_version_href)
        dest_repo_packages_count = dest_repo_packages.count
        dest_repo_packagecategories_count = rpm_package_category_api.list(
            repository_version=dest_repo.latest_version_href
        ).count
        dest_repo_packagegroups_count = rpm_package_groups_api.list(
            repository_version=dest_repo.latest_version_href
        ).count

        # assert that all dependencies were copied
        assert repo_packagecategories_count == dest_repo_packagecategories_count
        assert repo_packagegroups_count == dest_repo_packagegroups_count
        # Not all packages in repository are dependecies,
        # only packagegroups packages and its dependencies
        assert dest_repo_packages_count == 30
        # Assert only one latest version of 'duck' pacakge was copied
        copied_duck_pkg = [
            duck_pkg.version for duck_pkg in dest_repo_packages.results if duck_pkg.name == "duck"
        ]
        assert copied_duck_pkg == ["0.8"]

    def test_strict_copy_package_to_existing_repo(
        self,
        init_and_sync,
        monitor_task,
        rpm_copy_api,
        rpm_package_api,
        rpm_repository_api,
        rpm_repository_version_api,
        rpm_unsigned_repo_immediate,
    ):
        """Test copy package and its dependencies to empty repository.

        - Create repository and populate it
        - Create second repository with package fulfilling test package dependency
        - Use 'copy' to copy 'whale' package with dependencies
        - assert package and its missing dependencies were copied
        """
        # prepare final_repo - copy to repository
        final_repo, _ = init_and_sync()

        # prepare repository - copy from repository
        repo = rpm_unsigned_repo_immediate

        # remove test package and one dependency package from final repository
        data = {
            "remove_content_units": [
                pkg.pulp_href
                for pkg in rpm_package_api.list(
                    repository_version=final_repo.latest_version_href
                ).results
                if pkg.name in ("shark", "whale")
            ]
        }
        monitor_task(rpm_repository_api.modify(final_repo.pulp_href, data).task)

        final_repo = rpm_repository_api.read(final_repo.pulp_href)

        # get package to copy
        packages = rpm_package_api.list(repository_version=repo.latest_version_href, name="whale")
        package_to_copy = [packages.results[0].pulp_href]

        data = Copy(
            config=[
                {
                    "source_repo_version": repo.latest_version_href,
                    "dest_repo": final_repo.pulp_href,
                    "content": package_to_copy,
                }
            ],
            dependency_solving=True,
        )
        copy_response = monitor_task(rpm_copy_api.copy_content(data).task)
        repository_version = rpm_repository_version_api.read(copy_response.created_resources[0])

        # check only two packages was copied, original package to copy and only one
        # of its dependency as one is already present
        content_summary = repository_version.to_dict()["content_summary"]
        assert content_summary["added"][PULP_TYPE_PACKAGE]["count"] == 2


class TestCopyWithKickstartRepoSyncedImmediate:
    def test_kickstart_content(
        self,
        monitor_task,
        rpm_copy_api,
        rpm_content_distribution_trees_api,
        rpm_kickstart_repo_immediate,
        rpm_repository_api,
        rpm_repository_factory,
    ):
        """Test the content parameter."""
        src = rpm_kickstart_repo_immediate
        dest = rpm_repository_factory()

        content = rpm_content_distribution_trees_api.list(
            repository_version=src.latest_version_href
        )
        content_to_copy = [content.results[0].pulp_href]
        data = Copy(
            config=[
                {
                    "source_repo_version": src.latest_version_href,
                    "dest_repo": dest.pulp_href,
                    "content": content_to_copy,
                }
            ],
            dependency_solving=False,
        )
        monitor_task(rpm_copy_api.copy_content(data).task)

        dest = rpm_repository_api.read(dest.pulp_href)
        content = rpm_content_distribution_trees_api.list(
            repository_version=dest.latest_version_href
        )
        dest_content = [c.pulp_href for c in content.results]

        assert content_to_copy == dest_content

    def test_kickstart_copy_all(
        self,
        monitor_task,
        rpm_copy_api,
        rpm_kickstart_repo_immediate,
        rpm_repository_api,
        rpm_repository_factory,
        get_content_summary,
    ):
        """Test copying all the content from one repo to another."""
        src = rpm_kickstart_repo_immediate
        dest = rpm_repository_factory()

        data = Copy(
            config=[{"source_repo_version": src.latest_version_href, "dest_repo": dest.pulp_href}],
            dependency_solving=False,
        )
        monitor_task(rpm_copy_api.copy_content(data).task)

        # Check that we have the correct content counts.
        dest = rpm_repository_api.read(dest.pulp_href)
        content_summary = get_content_summary(dest)
        assert content_summary["present"] == RPM_KICKSTART_FIXTURE_SUMMARY
        assert content_summary["added"] == RPM_KICKSTART_FIXTURE_SUMMARY


def test_strict_copy_module_to_empty_repo(
    monitor_task,
    rpm_copy_api,
    rpm_modulemd_api,
    rpm_repository_api,
    rpm_repository_factory,
    rpm_modular_repo_on_demand,
):
    """Test copy module and its dependencies to empty repository.

    - Create repository and populate it
    - Create empty repository
    - Use 'copy' to copy 'nodejs' module with dependencies
    - assert module and its dependencies and relevant artifacts were copied
    """
    empty_repo = rpm_repository_factory()
    repo = rpm_modular_repo_on_demand

    modules = rpm_modulemd_api.list(
        repository_version=repo.latest_version_href,
        name="nodejs",
        stream="11",
        version="20180920144611",
    )
    module_to_copy = [modules.results[0].pulp_href]

    data = Copy(
        config=[
            {
                "source_repo_version": repo.latest_version_href,
                "dest_repo": empty_repo.pulp_href,
                "content": module_to_copy,
            }
        ],
        dependency_solving=True,
    )
    monitor_task(rpm_copy_api.copy_content(data).task)

    empty_repo = rpm_repository_api.read(empty_repo.pulp_href)
    modules = rpm_modulemd_api.list(repository_version=empty_repo.latest_version_href).results
    module_names = [module.name for module in modules]

    # assert that only 3 modules are copied (original and one dependency)
    assert len(modules) == 2
    # assert dependencies package names
    for dependency in ["nodejs", "postgresql"]:
        assert dependency in module_names


@pytest.mark.parallel
def test_advisory_copy_child_detection(
    init_and_sync,
    monitor_task,
    rpm_advisory_api,
    rpm_copy_api,
    rpm_modulemd_api,
    rpm_package_api,
    rpm_repository_api,
    rpm_repository_factory,
):
    """Test copy advisory and its direct package & module dependencies to empty repository.

    No recursive dependencies.

    - Create repository and populate it
    - Create empty repository
    - Use 'copy' to copy an advisory
    - assert advisory and its dependencies were copied
    """
    empty_repo = rpm_repository_factory()
    repo, _ = init_and_sync(url=RPM_MODULAR_FIXTURE_URL)

    test_advisory_href = get_all_content_hrefs(
        rpm_advisory_api, repository_version=repo.latest_version_href, id="FEDORA-2019-0329090518"
    )[0]
    content_to_copy = [test_advisory_href]

    data = Copy(
        config=[
            {
                "source_repo_version": repo.latest_version_href,
                "dest_repo": empty_repo.pulp_href,
                "content": content_to_copy,
            }
        ],
        dependency_solving=False,
    )
    monitor_task(rpm_copy_api.copy_content(data).task)

    empty_repo = rpm_repository_api.read(empty_repo.pulp_href)

    empty_repo_packages = [
        pkg.name
        for pkg in rpm_package_api.list(repository_version=empty_repo.latest_version_href).results
    ]
    empty_repo_advisories = [
        advisory.id
        for advisory in rpm_advisory_api.list(
            repository_version=empty_repo.latest_version_href
        ).results
    ]
    empty_repo_modules = [
        module.name
        for module in rpm_modulemd_api.list(
            repository_version=empty_repo.latest_version_href
        ).results
    ]

    # check the specific advisory was copied
    assert len(empty_repo_advisories) == 1
    # assert that all dependant packages were copied, the direct children of the advisory
    assert len(empty_repo_packages) == 2
    # assert dependencies package names
    for dependency in ["postgresql", "nodejs"]:
        assert dependency in empty_repo_packages
        assert dependency in empty_repo_modules


def get_all_content_hrefs(api, **kwargs):
    """Fetch all the content using the provided content API and query params.

    De-paginates the results.
    """
    content_list = []

    while True:
        content = api.list(**kwargs, offset=len(content_list))
        page = content.results
        content_list.extend([content.pulp_href for content in page])
        if not content.next:
            break

    return content_list
