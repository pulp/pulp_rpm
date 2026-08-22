"""Tests for comps content management: field verification and publish round-trip."""

import os
from tempfile import NamedTemporaryFile
from xml.etree import ElementTree

import pytest
import requests
import rpmrepo_metadata as rpmmd

from pulpcore.client.pulp_rpm import RpmRpmPublication

from pulp_rpm.tests.functional.constants import (
    BIG_COMPS_XML,
    RPM_UNSIGNED_FIXTURE_URL,
    SMALL_COMPS_XML,
)
from pulp_rpm.tests.functional.utils import get_metadata_content_helper

PACKAGE_TYPE_MAPPING = {
    rpmmd.PackageReqType.DEFAULT: 0,
    rpmmd.PackageReqType.OPTIONAL: 1,
    rpmmd.PackageReqType.CONDITIONAL: 2,
    rpmmd.PackageReqType.MANDATORY: 3,
}
PACKAGE_TYPE_REVERSE = {v: k for k, v in PACKAGE_TYPE_MAPPING.items()}


def _parse_comps(xml):
    """Parse a comps XML string or bytes into a libcomps.Comps object."""
    if isinstance(xml, bytes):
        xml = xml.decode("utf-8")
    return rpmmd.CompsData.from_xml(xml)


def _upload_comps(rpm_comps_api, repo_href, xml, monitor_task, replace=False):
    """Upload a comps XML string into a repository and wait for the task."""
    with NamedTemporaryFile("w+", suffix=".xml") as f:
        f.write(xml)
        f.flush()
        response = rpm_comps_api.rpm_comps_upload(
            file=f.name, repository=repo_href, replace=replace
        )
    return monitor_task(response.task)


def _modify_comps_group_name(xml, group_id, new_name):
    """Return a copy of the comps XML with one group's untranslated name changed.

    The group `id` is preserved, so the result is a genuinely modified variant
    of the same logical group (which yields a new content unit on upload).
    """
    if isinstance(xml, bytes):
        xml = xml.decode("utf-8")
    root = ElementTree.fromstring(xml)
    for group in root.findall("group"):
        gid = group.find("id")
        if gid is not None and gid.text == group_id:
            for name in group.findall("name"):
                if not name.attrib:  # the untranslated <name>, not an xml:lang variant
                    name.text = new_name
    return ElementTree.tostring(root, encoding="unicode")


def _api_group_to_rpmmd(api_grp):
    """Build an rpmmd CompsGroup from an API PackageGroup response."""
    group = rpmmd.CompsGroup(
        id=api_grp.id,
        name=api_grp.name,
        description=api_grp.description or "",
        default=api_grp.default,
        uservisible=api_grp.user_visible,
        biarchonly=api_grp.biarch_only,
        langonly=api_grp.langonly,
        display_order=api_grp.display_order,
    )
    group.packages = [
        rpmmd.CompsPackageReq(
            name=p["name"],
            reqtype=PACKAGE_TYPE_REVERSE.get(p["type"], rpmmd.PackageReqType.DEFAULT),
            requires=p["requires"],
            basearchonly=bool(p["basearchonly"]) if p["basearchonly"] else None,
        )
        for p in api_grp.packages
    ]
    group.name_by_lang = api_grp.name_by_lang
    group.desc_by_lang = api_grp.desc_by_lang
    return group


def _api_category_to_rpmmd(api_cat):
    """Build an rpmmd CompsCategory from an API PackageCategory response."""
    cat = rpmmd.CompsCategory(
        id=api_cat.id,
        name=api_cat.name,
        description=api_cat.description or "",
        display_order=api_cat.display_order,
    )
    cat.group_ids = [g["name"] for g in api_cat.group_ids]
    cat.name_by_lang = api_cat.name_by_lang
    cat.desc_by_lang = api_cat.desc_by_lang
    return cat


def _api_environment_to_rpmmd(api_env):
    """Build an rpmmd CompsEnvironment from an API PackageEnvironment response."""
    env = rpmmd.CompsEnvironment(
        id=api_env.id,
        name=api_env.name,
        description=api_env.description or "",
        display_order=api_env.display_order,
    )
    env.group_ids = [g["name"] for g in api_env.group_ids]
    env.option_ids = [
        rpmmd.CompsEnvironmentOption(group_id=o["name"], default=o["default"])
        for o in api_env.option_ids
    ]
    env.name_by_lang = api_env.name_by_lang
    env.desc_by_lang = api_env.desc_by_lang
    return env


def _assert_comps_equal(original_xml, published_xml):
    """Assert that two comps XML documents are semantically equivalent.

    Element ordering in comps is not significant and is not preserved across a
    publish round-trip, so both sides are canonicalized (deterministically
    ordered) before comparison. Comparing the `dict` representations rather
    than the objects directly gives a readable diff on failure.
    """
    original = _parse_comps(original_xml)
    published = _parse_comps(published_xml)
    original.canonicalize()
    published.canonicalize()

    assert original.to_dict() == published.to_dict()


@pytest.fixture(scope="class")
def big_comps_repo(rpm_comps_api, rpm_repository_factory, rpm_repository_api, monitor_task):
    repo = rpm_repository_factory()
    with NamedTemporaryFile("w+", suffix=".xml") as f:
        f.write(BIG_COMPS_XML)
        f.flush()
        response = rpm_comps_api.rpm_comps_upload(file=f.name, repository=repo.pulp_href)
        monitor_task(response.task)
    return rpm_repository_api.read(repo.pulp_href)


@pytest.fixture(scope="class")
def small_comps_repo(rpm_comps_api, rpm_repository_factory, rpm_repository_api, monitor_task):
    repo = rpm_repository_factory()
    with NamedTemporaryFile("w+", suffix=".xml") as f:
        f.write(SMALL_COMPS_XML)
        f.flush()
        response = rpm_comps_api.rpm_comps_upload(file=f.name, repository=repo.pulp_href)
        monitor_task(response.task)
    return rpm_repository_api.read(repo.pulp_href)


class TestCompsFieldVerification:
    """Verify that comps content stored via upload has correct field values."""

    @pytest.mark.parallel
    def test_group_fields(self, big_comps_repo, rpm_package_groups_api):
        expected_comps = _parse_comps(BIG_COMPS_XML)
        expected_comps.canonicalize()

        api_groups = rpm_package_groups_api.list(
            repository_version=big_comps_repo.latest_version_href
        ).results
        actual_groups = [_api_group_to_rpmmd(g) for g in api_groups]
        for group in actual_groups:
            group.canonicalize()
        actual_groups.sort(key=lambda g: g.id)

        assert len(actual_groups) == len(expected_comps.groups)
        for actual, expected in zip(actual_groups, expected_comps.groups):
            assert actual.to_dict() == expected.to_dict()

    @pytest.mark.parallel
    def test_category_fields(self, big_comps_repo, rpm_package_category_api):
        expected_comps = _parse_comps(BIG_COMPS_XML)
        expected_comps.canonicalize()

        api_categories = rpm_package_category_api.list(
            repository_version=big_comps_repo.latest_version_href
        ).results
        actual_categories = [_api_category_to_rpmmd(c) for c in api_categories]
        for cat in actual_categories:
            cat.canonicalize()
        actual_categories.sort(key=lambda c: c.id)

        assert len(actual_categories) == len(expected_comps.categories)
        for actual, expected in zip(actual_categories, expected_comps.categories):
            assert actual.to_dict() == expected.to_dict()

    @pytest.mark.parallel
    def test_environment_fields(self, big_comps_repo, rpm_package_environment_api):
        expected_comps = _parse_comps(BIG_COMPS_XML)
        expected_comps.canonicalize()

        api_envs = rpm_package_environment_api.list(
            repository_version=big_comps_repo.latest_version_href
        ).results
        actual_envs = [_api_environment_to_rpmmd(e) for e in api_envs]
        for env in actual_envs:
            env.canonicalize()
        actual_envs.sort(key=lambda e: e.id)

        assert len(actual_envs) == len(expected_comps.environments)
        for actual, expected in zip(actual_envs, expected_comps.environments):
            assert actual.to_dict() == expected.to_dict()

    @pytest.mark.parallel
    def test_langpacks_fields(self, small_comps_repo, rpm_package_lang_packs_api):
        expected_comps = _parse_comps(SMALL_COMPS_XML)
        expected_matches = {lp.name: lp.install for lp in expected_comps.langpacks}

        api_langpacks = rpm_package_lang_packs_api.list(
            repository_version=small_comps_repo.latest_version_href
        ).results

        assert len(api_langpacks) == 1
        assert api_langpacks[0].matches == expected_matches


class TestCompsPublishRoundtrip:
    """Verify that comps XML round-trips through upload/sync -> publish -> serve."""

    @pytest.mark.parallel
    @pytest.mark.parametrize(
        "comps_repo_fixture,comps_xml",
        [
            pytest.param("big_comps_repo", BIG_COMPS_XML, id="big"),
            pytest.param("small_comps_repo", SMALL_COMPS_XML, id="small"),
        ],
    )
    def test_roundtrip_comps(
        self,
        request,
        comps_repo_fixture,
        comps_xml,
        rpm_publication_api,
        rpm_distribution_factory,
        distribution_base_url,
        monitor_task,
    ):
        repo = request.getfixturevalue(comps_repo_fixture)

        publish_data = RpmRpmPublication(repository=repo.pulp_href)
        publish_response = rpm_publication_api.create(publish_data)
        publication_href = monitor_task(publish_response.task).created_resources[0]

        distribution = rpm_distribution_factory(publication=publication_href)
        dist_url = distribution_base_url(distribution.base_url)

        repomd = ElementTree.fromstring(
            requests.get(os.path.join(dist_url, "repodata/repomd.xml")).text
        )
        published_comps_xml = get_metadata_content_helper(dist_url, repomd, "group")
        assert published_comps_xml is not None, "No comps metadata in published repo"

        _assert_comps_equal(comps_xml, published_comps_xml)

    @pytest.mark.parallel
    def test_roundtrip_synced_repo(
        self,
        init_and_sync,
        rpm_publication_api,
        rpm_distribution_factory,
        distribution_base_url,
        monitor_task,
    ):
        repo, _ = init_and_sync(url=RPM_UNSIGNED_FIXTURE_URL, policy="immediate")

        original_repomd = ElementTree.fromstring(
            requests.get(os.path.join(RPM_UNSIGNED_FIXTURE_URL, "repodata/repomd.xml")).text
        )
        original_comps_xml = get_metadata_content_helper(
            RPM_UNSIGNED_FIXTURE_URL, original_repomd, "group"
        )
        assert original_comps_xml is not None, "Upstream fixture has no comps metadata"

        publish_data = RpmRpmPublication(repository=repo.pulp_href)
        publish_response = rpm_publication_api.create(publish_data)
        publication_href = monitor_task(publish_response.task).created_resources[0]

        distribution = rpm_distribution_factory(publication=publication_href)
        dist_url = distribution_base_url(distribution.base_url)

        published_repomd = ElementTree.fromstring(
            requests.get(os.path.join(dist_url, "repodata/repomd.xml")).text
        )
        published_comps_xml = get_metadata_content_helper(dist_url, published_repomd, "group")
        assert published_comps_xml is not None, "No comps metadata in published repo"

        _assert_comps_equal(original_comps_xml, published_comps_xml)


class TestCompsReupload:
    """Verify re-uploading modified comps into a repo that already has comps."""

    @pytest.mark.parallel
    def test_reupload_modified_comps_replaces(
        self,
        rpm_comps_api,
        rpm_repository_factory,
        rpm_repository_api,
        rpm_package_groups_api,
        rpm_publication_api,
        rpm_distribution_factory,
        distribution_base_url,
        monitor_task,
    ):
        repo = rpm_repository_factory()

        # Initial upload.
        _upload_comps(rpm_comps_api, repo.pulp_href, SMALL_COMPS_XML, monitor_task)

        # Re-upload a modified variant (same group id, changed name) with
        # replace=True so the original comps content is swapped out.
        modified_xml = _modify_comps_group_name(SMALL_COMPS_XML, "birds", "Modified Birds")
        _upload_comps(rpm_comps_api, repo.pulp_href, modified_xml, monitor_task, replace=True)

        repo = rpm_repository_api.read(repo.pulp_href)

        # Exactly one 'birds' group must remain, carrying the modified name.
        # (Without replace, the same-id original would linger alongside it.)
        api_groups = rpm_package_groups_api.list(
            repository_version=repo.latest_version_href
        ).results
        birds = [g for g in api_groups if g.id == "birds"]
        assert len(birds) == 1, "replace should leave exactly one 'birds' group"
        assert birds[0].name == "Modified Birds"

        # Publish and verify the served comps.xml reflects the modification and
        # no longer matches the original upload.
        publish_data = RpmRpmPublication(repository=repo.pulp_href)
        publication_href = monitor_task(
            rpm_publication_api.create(publish_data).task
        ).created_resources[0]

        distribution = rpm_distribution_factory(publication=publication_href)
        dist_url = distribution_base_url(distribution.base_url)

        repomd = ElementTree.fromstring(
            requests.get(os.path.join(dist_url, "repodata/repomd.xml")).text
        )
        published_comps_xml = get_metadata_content_helper(dist_url, repomd, "group")
        assert published_comps_xml is not None, "No comps metadata in published repo"

        _assert_comps_equal(modified_xml, published_comps_xml)
        with pytest.raises(AssertionError):
            _assert_comps_equal(SMALL_COMPS_XML, published_comps_xml)
