"""Tests that perform actions over advisory content unit upload."""

import pytest
import os

from pulpcore.tests.functional.utils import PulpTaskError
from pulp_rpm.tests.functional.constants import (
    BEAR_JSON,
    CAMEL_BEAR_DOG_JSON,
    CAMEL_BIRD_JSON,
    CAMEL_JSON,
    CESA_2020_5002,
    CESA_2020_4910,
    RPM_PACKAGE_FILENAME,
    RPM_UNSIGNED_FIXTURE_URL,
)


@pytest.mark.parallel
def test_upload_wrong_type(upload_wrong_file_type, monitor_task):
    """Test that a proper error is raised when wrong file content type is uploaded."""
    bad_file_to_use = os.path.join(RPM_UNSIGNED_FIXTURE_URL, RPM_PACKAGE_FILENAME)
    with pytest.raises(PulpTaskError) as e:
        monitor_task(upload_wrong_file_type(bad_file_to_use).task)
    assert "JSON" in e.value.task.error["description"]


@pytest.mark.parallel
def test_upload_json(upload_advisory_factory):
    """Test upload advisory from JSON file."""
    advisory1, _, an_id = upload_advisory_factory(set_id=True)
    assert advisory1.id == an_id


@pytest.mark.parallel
def test_merging(
    upload_advisory_factory,
    assert_uploaded_advisory,
    rpm_advisory_api,
    rpm_repository_factory,
):
    """Test the 'same' advisory, diff pkglists, into a repo, expecting a merged package-list."""
    repo = rpm_repository_factory()
    bear, vers_href, an_id = upload_advisory_factory(
        advisory=BEAR_JSON, repository=repo, set_id=True
    )
    bear = rpm_advisory_api.read(bear.pulp_href)
    assert_uploaded_advisory(an_id, vers_href)
    assert vers_href == f"{repo.pulp_href}versions/1/"
    assert 1 == len(bear.pkglist)
    assert 1 == len(bear.pkglist[0].packages)

    # Second upload, no pkg-intersection - add both collections
    # NOTE: also check that unnamed-collections are now named "collection_N", so
    # they can be uniquely identified
    _, vers_href, _ = upload_advisory_factory(advisory=CAMEL_JSON, repository=repo, use_id=an_id)
    advisory_href, vers_herf = assert_uploaded_advisory(an_id, vers_href)
    assert vers_href == f"{repo.pulp_href}versions/2/"
    cambear = rpm_advisory_api.read(advisory_href)
    assert 2 == len(cambear.pkglist)
    coll_names = [row.name for row in cambear.pkglist]
    assert "collection_0" in coll_names
    assert "collection_1" in coll_names
    assert 1 == len(cambear.pkglist[0].packages)
    assert 1 == len(cambear.pkglist[1].packages)
    names = [plist.packages[0]["name"] for plist in cambear.pkglist]
    assert "camel" in names
    assert "bear" in names

    # Third upload, two pkgs, intersects with existing, expect AdvisoryConflict failure
    with pytest.raises(PulpTaskError) as ctx:
        _, _, _ = upload_advisory_factory(advisory=CAMEL_BIRD_JSON, repository=repo, use_id=an_id)
    error_msg = ctx.value.task.error["description"]
    assert "neither package list is a proper subset of the other" in error_msg
    assert "ALLOW_AUTOMATIC_UNSAFE_ADVISORY_CONFLICT_RESOLUTION" in error_msg

    # Fourth upload, intersecting pkglists, expecting three pkgs
    cambeardog, vers_href, _ = upload_advisory_factory(
        advisory=CAMEL_BEAR_DOG_JSON, repository=repo, use_id=an_id
    )
    assert_uploaded_advisory(an_id, vers_href)
    assert vers_href == f"{repo.pulp_href}versions/3/"
    assert an_id == cambeardog.id
    assert 1 == len(cambeardog.pkglist)
    # Expect one collection, not a merge
    names = [pkg["name"] for pkg in cambeardog.pkglist[0].packages]
    assert 3 == len(names)
    assert "camel" in names
    assert "bear" in names
    assert "dog" in names


@pytest.mark.parallel
def test_8683_error_path(
    upload_advisory_factory,
    assert_uploaded_advisory,
    rpm_repository_factory,
):
    """
    Test that upload-fail doesn't break all future uploads.

    See https://pulp.plan.io/issues/8683 for details.
    """
    # Upload an advisory
    repo = rpm_repository_factory()

    _, vers_href, id1 = upload_advisory_factory(
        advisory=CESA_2020_5002, repository=repo, set_id=True
    )
    assert_uploaded_advisory(id1, vers_href)

    # Try to upload it 'again' and watch it fail
    with pytest.raises(PulpTaskError):
        _, _, _ = upload_advisory_factory(advisory=CESA_2020_5002, repository=repo, use_id=id1)

    # Upload a different advisory and Don't Fail
    advisory3, _, id2 = upload_advisory_factory(
        advisory=CESA_2020_4910, repository=repo, set_id=True
    )
    assert id2 == advisory3.id
