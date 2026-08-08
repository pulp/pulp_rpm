"""Tests for comps content management: field verification and publish round-trip."""

import os
from tempfile import NamedTemporaryFile
from xml.etree import ElementTree

import libcomps
import pytest
import requests

from pulpcore.client.pulp_rpm import RpmRpmPublication

from pulp_rpm.tests.functional.constants import (
    BIG_COMPS_XML,
    RPM_UNSIGNED_FIXTURE_URL,
    SMALL_COMPS_XML,
)
from pulp_rpm.tests.functional.utils import get_metadata_content_helper


def _parse_comps(xml):
    """Parse a comps XML string or bytes into a libcomps.Comps object."""
    if isinstance(xml, bytes):
        xml = xml.decode("utf-8")
    comps = libcomps.Comps()
    comps.fromxml_str(xml)
    return comps


def _strdict_to_dict(sd):
    """Convert a libcomps StrDict to a plain Python dict, returning {} for None."""
    if sd is None:
        return {}
    return {k: sd[k] for k in sd}


def _grplist_to_list(gl):
    """Convert a libcomps group/option list to a sorted list of {name, default} dicts."""
    return sorted(
        [{"name": g.name, "default": bool(g.default)} for g in gl],
        key=lambda d: d["name"],
    )


def _pkglist_to_list(pl):
    """Convert a libcomps package list to a sorted, deduplicated list of package dicts."""
    seen = []
    for p in pl:
        d = {
            "name": p.name,
            "type": p.type,
            "basearchonly": bool(p.basearchonly),
            "requires": p.requires,
        }
        if d not in seen:
            seen.append(d)
    return sorted(seen, key=lambda d: d["name"])


def _group_to_dict(g):
    """Normalize a libcomps Group into a comparable dict."""
    return {
        "id": g.id,
        "name": g.name,
        "description": g.desc or "",
        "default": bool(g.default),
        "user_visible": bool(g.uservisible),
        "display_order": g.display_order,
        "biarch_only": bool(g.biarchonly),
        "packages": _pkglist_to_list(g.packages),
        "name_by_lang": _strdict_to_dict(g.name_by_lang),
        "desc_by_lang": _strdict_to_dict(g.desc_by_lang),
    }


def _category_to_dict(c):
    """Normalize a libcomps Category into a comparable dict."""
    return {
        "id": c.id,
        "name": c.name,
        "description": c.desc or "",
        "display_order": c.display_order,
        "group_ids": _grplist_to_list(c.group_ids),
        "name_by_lang": _strdict_to_dict(c.name_by_lang),
        "desc_by_lang": _strdict_to_dict(c.desc_by_lang),
    }


def _environment_to_dict(e):
    """Normalize an environment object into a comparable dict."""
    return {
        "id": e.id,
        "name": e.name,
        "description": e.desc or "",
        "display_order": e.display_order,
        "group_ids": _grplist_to_list(e.group_ids),
        "option_ids": _grplist_to_list(e.option_ids),
        "name_by_lang": _strdict_to_dict(e.name_by_lang),
        "desc_by_lang": _strdict_to_dict(e.desc_by_lang),
    }


def _comps_to_dicts(comps):
    """Convert a parsed Comps object into a dict of sorted, comparable lists."""
    return {
        "groups": sorted([_group_to_dict(g) for g in comps.groups], key=lambda d: d["id"]),
        "categories": sorted(
            [_category_to_dict(c) for c in comps.categories], key=lambda d: d["id"]
        ),
        "environments": sorted(
            [_environment_to_dict(e) for e in comps.environments], key=lambda d: d["id"]
        ),
        "langpacks": _strdict_to_dict(comps.langpacks),
    }


def _normalize_api_packages(packages):
    """Normalize package dicts from the API response for comparison against parsed XML."""
    return sorted(
        [
            {
                "name": p["name"],
                "type": p["type"],
                "basearchonly": bool(p["basearchonly"]),
                "requires": p["requires"],
            }
            for p in packages
        ],
        key=lambda d: d["name"],
    )


def _normalize_api_group_ids(group_ids):
    """Normalize group_ids dicts from the API response for comparison against parsed XML."""
    return sorted(
        [{"name": g["name"], "default": bool(g["default"])} for g in group_ids],
        key=lambda d: d["name"],
    )


def _assert_comps_equal(original_xml, published_xml):
    """Assert that two comps XML documents are semantically equivalent."""
    original = _comps_to_dicts(_parse_comps(original_xml))
    published = _comps_to_dicts(_parse_comps(published_xml))

    assert len(original["groups"]) == len(published["groups"]), "Group count mismatch"
    for orig, pub in zip(original["groups"], published["groups"]):
        assert orig == pub, f"Group mismatch for id={orig['id']}"

    assert len(original["categories"]) == len(published["categories"]), "Category count mismatch"
    for orig, pub in zip(original["categories"], published["categories"]):
        assert orig == pub, f"Category mismatch for id={orig['id']}"

    assert len(original["environments"]) == len(published["environments"]), (
        "Environment count mismatch"
    )
    for orig, pub in zip(original["environments"], published["environments"]):
        assert orig == pub, f"Environment mismatch for id={orig['id']}"

    assert original["langpacks"] == published["langpacks"], "Langpacks mismatch"


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
        expected_groups = sorted(
            [_group_to_dict(g) for g in expected_comps.groups], key=lambda d: d["id"]
        )

        api_groups = rpm_package_groups_api.list(
            repository_version=big_comps_repo.latest_version_href
        ).results
        api_groups = sorted(api_groups, key=lambda g: g.id)

        assert len(api_groups) == len(expected_groups)
        for api_grp, expected in zip(api_groups, expected_groups):
            assert api_grp.id == expected["id"]
            assert api_grp.name == expected["name"]
            assert api_grp.description == expected["description"]
            assert api_grp.default == expected["default"]
            assert api_grp.user_visible == expected["user_visible"]
            assert api_grp.display_order == expected["display_order"]
            assert api_grp.biarch_only == expected["biarch_only"]
            assert _normalize_api_packages(api_grp.packages) == expected["packages"]
            assert api_grp.name_by_lang == expected["name_by_lang"]
            assert api_grp.desc_by_lang == expected["desc_by_lang"]

    @pytest.mark.parallel
    def test_category_fields(self, big_comps_repo, rpm_package_category_api):
        expected_comps = _parse_comps(BIG_COMPS_XML)
        expected_categories = sorted(
            [_category_to_dict(c) for c in expected_comps.categories], key=lambda d: d["id"]
        )

        api_categories = rpm_package_category_api.list(
            repository_version=big_comps_repo.latest_version_href
        ).results
        api_categories = sorted(api_categories, key=lambda c: c.id)

        assert len(api_categories) == len(expected_categories)
        for api_cat, expected in zip(api_categories, expected_categories):
            assert api_cat.id == expected["id"]
            assert api_cat.name == expected["name"]
            assert api_cat.description == expected["description"]
            assert api_cat.display_order == expected["display_order"]
            assert _normalize_api_group_ids(api_cat.group_ids) == expected["group_ids"]
            assert api_cat.name_by_lang == expected["name_by_lang"]
            assert api_cat.desc_by_lang == expected["desc_by_lang"]

    @pytest.mark.parallel
    def test_environment_fields(self, big_comps_repo, rpm_package_environment_api):
        expected_comps = _parse_comps(BIG_COMPS_XML)
        expected_envs = sorted(
            [_environment_to_dict(e) for e in expected_comps.environments],
            key=lambda d: d["id"],
        )

        api_envs = rpm_package_environment_api.list(
            repository_version=big_comps_repo.latest_version_href
        ).results
        api_envs = sorted(api_envs, key=lambda e: e.id)

        assert len(api_envs) == len(expected_envs)
        for api_env, expected in zip(api_envs, expected_envs):
            assert api_env.id == expected["id"]
            assert api_env.name == expected["name"]
            assert api_env.description == expected["description"]
            assert api_env.display_order == expected["display_order"]
            assert _normalize_api_group_ids(api_env.group_ids) == expected["group_ids"]
            assert _normalize_api_group_ids(api_env.option_ids) == expected["option_ids"]
            assert api_env.name_by_lang == expected["name_by_lang"]
            assert api_env.desc_by_lang == expected["desc_by_lang"]

    @pytest.mark.parallel
    def test_langpacks_fields(self, small_comps_repo, rpm_package_lang_packs_api):
        expected_comps = _parse_comps(SMALL_COMPS_XML)
        expected_matches = _strdict_to_dict(expected_comps.langpacks)

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
        if original_comps_xml is None:
            pytest.skip("Upstream fixture has no comps metadata")

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
