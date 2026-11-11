"""Unit tests for copy_content in the copy task."""

import json
import re
import uuid
from dataclasses import dataclass

import pytest

from pulp_rpm.app.models import RpmRepository
from pulp_rpm.app.tasks.copy import copy_content
from pulp_rpm.tests.unit.utils.content_factory import RepoContentFactory
from pulp_rpm.tests.unit.utils.query_recorder import QueryRecorder, detect_n1


class GrowthProfiles:
    """Builders for parent/child content relationships, one repo version each.

    Each builder takes (count, repo_name) and returns (repo_version, only_content_ids selecting
    just the parent, expected child pks).
    """

    @staticmethod
    def packages_within_advisories(count, repo_name):
        """Grow the packages one advisory references via an UpdateCollection."""
        with RepoContentFactory(repo_name=repo_name) as repo:
            package_names = [f"{repo_name}-pkg-{i}" for i in range(count)]
            package_pks = repo.add_packages(package_names)
            advisory_pk = repo.add_advisory(f"{repo_name}-advisory", package_names=package_names)
        return repo.version, [advisory_pk], set(package_pks)

    @staticmethod
    def modules_within_advisories(count, repo_name):
        """Grow the modules one advisory references, one UpdateCollection each."""
        with RepoContentFactory(repo_name=repo_name) as repo:
            module_names = [f"{repo_name}-mod-{i}" for i in range(count)]
            module_nsvcas, module_pks = repo.add_modulemds(module_names)
            advisory_pk = repo.add_advisory(f"{repo_name}-advisory", module_nsvcas=module_nsvcas)
        return repo.version, [advisory_pk], set(module_pks)

    @staticmethod
    def packages_within_packagegroups(count, repo_name):
        """Grow the packages one package group references."""
        with RepoContentFactory(repo_name=repo_name) as repo:
            package_names = [f"{repo_name}-pkg-{i}" for i in range(count)]
            package_pks = repo.add_packages(package_names)
            group_pk = repo.add_package_group(f"{repo_name}-group", packages=package_names)
        return repo.version, [group_pk], set(package_pks)

    @staticmethod
    def packagegroups_within_packageenv(count, repo_name):
        """Grow the package groups one environment references via group_ids (mandatory groups)."""
        with RepoContentFactory(repo_name=repo_name) as repo:
            group_names = [f"{repo_name}-grp-{i}" for i in range(count)]
            group_pks = [repo.add_package_group(name) for name in group_names]
            env_pk = repo.add_package_environment(f"{repo_name}-env", group_names=group_names)
        return repo.version, [env_pk], set(group_pks)

    @staticmethod
    def packagegroups_within_packagecategory(count, repo_name):
        """Grow the package groups one category references."""
        with RepoContentFactory(repo_name=repo_name) as repo:
            group_names = [f"{repo_name}-grp-{i}" for i in range(count)]
            group_pks = [repo.add_package_group(name) for name in group_names]
            category_pk = repo.add_package_category(f"{repo_name}-cat", group_names=group_names)
        return repo.version, [category_pk], set(group_pks)

    @staticmethod
    def advisories(count, repo_name):
        """Grow the number of empty advisories explicitly selected for copy.

        Unlike the other profiles, what grows here is the *selection* itself
        (content_pks/only_ids), not the children of a single fixed parent.
        """
        with RepoContentFactory(repo_name=repo_name) as repo:
            advisory_pks = [repo.add_advisory(f"{repo_name}-advisory-{i}") for i in range(count)]
        return repo.version, advisory_pks, set()

    @staticmethod
    def packagecategories(count, repo_name):
        """Grow the number of empty package categories explicitly selected for copy."""
        with RepoContentFactory(repo_name=repo_name) as repo:
            category_pks = [
                repo.add_package_category(f"{repo_name}-cat-{i}", group_names=[])
                for i in range(count)
            ]
        return repo.version, category_pks, set()

    @staticmethod
    def packageenvironments(count, repo_name):
        """Grow the number of empty package environments explicitly selected for copy."""
        with RepoContentFactory(repo_name=repo_name) as repo:
            env_pks = [
                repo.add_package_environment(f"{repo_name}-env-{i}", group_names=[])
                for i in range(count)
            ]
        return repo.version, env_pks, set()

    @staticmethod
    def packagegroups_within_packageenv_options(count, repo_name):
        """Grow the package groups one environment references via option_ids (optional groups),
        instead of group_ids (mandatory groups) - that loop is never exercised otherwise.
        """
        with RepoContentFactory(repo_name=repo_name) as repo:
            group_names = [f"{repo_name}-grp-{i}" for i in range(count)]
            group_pks = [repo.add_package_group(name) for name in group_names]
            env_pk = repo.add_package_environment(
                f"{repo_name}-env", group_names=[], option_names=group_names
            )
        return repo.version, [env_pk], set(group_pks)

    @staticmethod
    def packages_already_selected_within_packagegroup(count, repo_name):
        """Grow the packages a group references that are ALSO part of the explicit selection.

        Exercises the existing_package_names/missing_package_names dedup branch: since the
        packages are already selected, none of them should be looked up via annotate_with_age.
        """
        with RepoContentFactory(repo_name=repo_name) as repo:
            package_names = [f"{repo_name}-pkg-{i}" for i in range(count)]
            package_pks = repo.add_packages(package_names)
            group_pk = repo.add_package_group(f"{repo_name}-group", packages=package_names)
        return repo.version, [group_pk, *package_pks], set()

    @staticmethod
    def packagegroups(count, repo_name):
        """Grow the number of empty package groups explicitly selected for copy."""
        with RepoContentFactory(repo_name=repo_name) as repo:
            group_pks = [repo.add_package_group(f"{repo_name}-grp-{i}") for i in range(count)]
        return repo.version, group_pks, set()

    PROFILES = {
        "grow_packages_within_advisories": packages_within_advisories,
        "grow_modules_within_advisories": modules_within_advisories,
        "grow_packages_within_packagegroups": packages_within_packagegroups,
        "grow_packagegroups_within_packageenv": packagegroups_within_packageenv,
        "grow_packagegroups_within_packagecategory": packagegroups_within_packagecategory,
        "grow_advisories": advisories,
        "grow_packagecategories": packagecategories,
        "grow_packagegroups_within_packageenv_options": packagegroups_within_packageenv_options,
        "grow_packages_already_selected_within_packagegroup": (
            packages_already_selected_within_packagegroup
        ),
        "grow_packagegroups": packagegroups,
        "grow_packageenvironments": packageenvironments,
    }


@dataclass
class CopyWorkflowResult:
    children: set
    resolved: set
    recorder: QueryRecorder


@dataclass
class IgnoreFromPath:
    pattern: str
    reason: str


def make_growth_candidate_filter(ignore_paths=None):
    """Build a get_queries() filter_fn matching non-ignored SELECTs with bound params."""
    ignore_paths = ignore_paths or []

    def is_growth_candidate(query) -> bool:
        if query.statement_type != "SELECT" or query.num_params == 0:
            return False
        if any(
            re.search(ignore.pattern, site) for ignore in ignore_paths for site in query.call_site
        ):
            return False
        return True

    return is_growth_candidate


def make_not_ignored_filter(ignore_paths=None):
    """Build a get_queries() filter_fn excluding queries matching one of `ignore_paths`."""
    ignore_paths = ignore_paths or []

    def not_ignored(query) -> bool:
        return not any(
            re.search(ignore.pattern, site) for ignore in ignore_paths for site in query.call_site
        )

    return not_ignored


class TestCopyContentBase:
    def call_copy_workflow(self, content_count: int, profile_name: str) -> CopyWorkflowResult:
        build = GrowthProfiles.PROFILES[profile_name]
        repo_name = f"{profile_name}-{content_count}"
        version, ids, children = build(content_count, repo_name)
        dest_repo = RpmRepository.objects.create(name=str(uuid.uuid4()))
        config = [
            {
                "source_repo_version": version.pk,
                "dest_repo": dest_repo.pk,
                "content": list(ids),
            }
        ]
        recorder = QueryRecorder()
        with recorder:
            copy_content(config, dependency_solving=False)
        dest_content = dest_repo.latest_version().content
        resolved = set(dest_content.values_list("pk", flat=True))
        return CopyWorkflowResult(children=children, resolved=resolved, recorder=recorder)

    @pytest.mark.parametrize("profile_name", GrowthProfiles.PROFILES.keys())
    @pytest.mark.django_db
    def test_query_count_is_size_invariant(self, profile_name, save_artifact):
        """copy_content() must issue the same NUMBER of queries regardless of how much content
        is being copied. A differing count for the same profile means an N+1 query bug (e.g. one
        query per referenced item in a Python loop), as opposed to a query whose own bound-param
        count merely grows - that's covered separately.
        """
        SMALL_COUNT = 20
        SCALE_FACTOR = 10
        LARGE_COUNT = SMALL_COUNT * SCALE_FACTOR
        IGNORE_PATHS = [
            IgnoreFromPath(
                pattern=r"advisory\.py:\d+ in (get_pkglist|get_module_list)",
                reason="needs further investigation",
            ),
        ]

        small = self.call_copy_workflow(SMALL_COUNT, profile_name)
        large = self.call_copy_workflow(LARGE_COUNT, profile_name)
        save_artifact(small.recorder.summary_text(include_sql=True), suffix="small")

        not_ignored = make_not_ignored_filter(IGNORE_PATHS)
        small_queries = small.recorder.get_queries(not_ignored)
        large_queries = large.recorder.get_queries(not_ignored)
        offenders = detect_n1(small_queries, large_queries)

        passed = not offenders  # keeps error msg clean
        assert passed, (
            json.dumps(offenders, indent=4)
            + f"\n\n[{profile_name}] {len(offenders)} quer(ies) fired a different number of "
            f"times between runs:\n"
        )

    @pytest.mark.parametrize("profile_name", GrowthProfiles.PROFILES.keys())
    @pytest.mark.django_db
    def test_scales_sublinearly_across_content_relationships(self, profile_name, save_artifact):
        """The SQL param count from the COPY API should remain stable with input grow.

        A query with growing param count rate means it could reach postgres's limit of 65532
        for big enough input.
        """
        IGNORE_PATHS = [
            IgnoreFromPath(
                pattern=r"pulpcore/app/models/repository\.py:\d+ in __exit__",
                reason="should be fixed in pulpcore",
            ),
        ]

        SMALL_COUNT = 20
        SCALE_FACTOR = 10
        LARGE_COUNT = SMALL_COUNT * SCALE_FACTOR
        THRESHOLD_FACTOR = 1.1  # only tolerate small growth rates
        small = self.call_copy_workflow(SMALL_COUNT, profile_name)
        large = self.call_copy_workflow(LARGE_COUNT, profile_name)

        small_summary = small.recorder.summary_text(include_sql=True)
        save_artifact(small_summary, suffix="small")

        assert small.children < small.resolved
        assert large.children < large.resolved

        is_growth_candidate = make_growth_candidate_filter(IGNORE_PATHS)
        small_queries = small.recorder.get_queries(is_growth_candidate)
        large_queries = large.recorder.get_queries(is_growth_candidate)

        failures = []
        for small_query, large_query in zip(small_queries, large_queries):
            growth_rate = large_query.num_params / small_query.num_params
            if growth_rate >= THRESHOLD_FACTOR:
                failures.append({**large_query.summary, "growth_rate": round(growth_rate, 2)})

        passed = not failures  # keeps error msg clean
        assert passed, (
            json.dumps(failures, indent=4)
            + f"\n\n[{profile_name}] {len(failures)} quer(ies) grew params count too fast:\n"
        )
