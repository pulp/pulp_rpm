"""Tests that CRUD rpm remotes."""

from random import choice
from uuid import uuid4

import pytest
from pulpcore.client.pulp_rpm.exceptions import ApiException
from pydantic import ValidationError

from pulp_rpm.tests.functional.constants import DOWNLOAD_POLICIES, RPM_UNSIGNED_FIXTURE_URL


@pytest.mark.parallel
def test_basic_crud_remote(rpm_rpmremote_api, rpm_rpmremote_factory, monitor_task):
    """Test CRUD operations for remotes."""
    # Create a remote
    body = gen_verbose_remote_data()
    remote = rpm_rpmremote_factory(**body)
    for key in ("username", "password"):
        del body[key]

    for key, val in body.items():
        assert remote.to_dict()[key] == val, key

    # Try to create a second remote with an identical name
    with pytest.raises(ApiException):
        rpm_rpmremote_factory(name=remote.name)

    # Read a remote by its href
    remote = rpm_rpmremote_api.read(remote.pulp_href)
    for key, val in remote.to_dict().items():
        assert remote.to_dict()[key] == val, key

    # Read a remote by its name
    results = rpm_rpmremote_api.list(name=remote.name).results
    assert len(results) == 1
    for key, val in remote.to_dict().items():
        assert results[0].to_dict()[key] == val, key

    # Update a remote using HTTP PATCH
    body = gen_verbose_remote_data()
    response = rpm_rpmremote_api.partial_update(remote.pulp_href, body)
    monitor_task(response.task)
    for key in ("username", "password"):
        del body[key]
    remote = rpm_rpmremote_api.read(remote.pulp_href)
    for key, val in body.items():
        assert remote.to_dict()[key] == val, key

    # Update a remote using HTTP PUT
    body = gen_verbose_remote_data()
    response = rpm_rpmremote_api.update(remote.pulp_href, body)
    monitor_task(response.task)
    for key in ("username", "password"):
        del body[key]
    remote = rpm_rpmremote_api.read(remote.pulp_href)
    for key, val in body.items():
        assert remote.to_dict()[key] == val, key

    # Delete a remote
    response = rpm_rpmremote_api.delete(remote.pulp_href)
    monitor_task(response.task)
    with pytest.raises(ApiException):
        rpm_rpmremote_api.read(remote.pulp_href)


@pytest.mark.parallel
def test_missing_url(rpm_rpmremote_api, rpm_rpmremote_factory):
    """Verify whether is possible to create a remote without a URL.

    This test targets the following issues:

    * `Pulp #3395 <https://pulp.plan.io/issues/3395>`_
    * `Pulp Smash #984 <https://github.com/pulp/pulp-smash/issues/984>`_
    """
    body = gen_remote_data()
    del body["url"]
    with pytest.raises(ValidationError):
        rpm_rpmremote_api.create(body)


@pytest.mark.parallel
def test_policy_update_changes(rpm_rpmremote_api, rpm_rpmremote_factory, monitor_task):
    """Verify download policy behavior for valid and invalid values.

    In Pulp 3, there are different download policies.

    This test targets the following testing scenarios:

    1. Creating a remote without a download policy.
       Verify the creation is successful and immediate it is policy applied.
    2. Change the remote policy from default.
       Verify the change is successful.
    3. Attempt to change the remote policy to an invalid string.
       Verify an ApiException is given for the invalid policy as well
       as the policy remaining unchanged.

    For more information on the remote policies, see the Pulp3
    API on an installed server:

    * /pulp/api/v3/docs/#operation`

    This test targets the following issues:

    * `Pulp #4420 <https://pulp.plan.io/issues/4420>`_
    * `Pulp #3763 <https://pulp.plan.io/issues/3763>`_
    """
    # Verify the default policy `immediate`
    body = gen_verbose_remote_data()
    del body["policy"]
    remote = rpm_rpmremote_factory(**body)
    assert remote.policy == "immediate", remote

    # Verify ability to change policy to value other than the default
    changed_policy = choice([item for item in DOWNLOAD_POLICIES if item != "immediate"])
    response = rpm_rpmremote_api.partial_update(remote.pulp_href, {"policy": changed_policy})
    monitor_task(response.task)

    remote = rpm_rpmremote_api.read(remote.pulp_href)
    assert remote.policy == changed_policy, remote

    # Verify an invalid policy does not update the remote policy
    with pytest.raises(ValidationError):
        rpm_rpmremote_api.partial_update(remote.pulp_href, {"policy": str(uuid4())})


def test_raise_on_invalid_remote_url(
    rpm_rpmremote_api, rpm_ulnremote_api, gen_object_with_cleanup, monitor_task
):
    # Cant create invalid RpmRemote
    for protocol in ("uln", "sftp", "grpc"):
        with pytest.raises(ApiException, match=" is not valid. It must start with: "):
            body = gen_verbose_remote_data()
            body["url"] = f"{protocol}://some/rpm/remote"
            gen_object_with_cleanup(rpm_rpmremote_api, body)

    # Cant create invalid UlnRemote
    for protocol in ("http", "https", "file"):
        with pytest.raises(ApiException, match=" is not valid. It must start with: "):
            body = gen_verbose_remote_data()
            body["url"] = f"{protocol}://some/uln/remote"
            gen_object_with_cleanup(rpm_ulnremote_api, body)


def gen_remote_data():
    """Return a minimum semi-random dict for use in defining a remote."""
    return {
        "name": str(uuid4()),
        "url": RPM_UNSIGNED_FIXTURE_URL,
        "policy": "immediate",
    }


def gen_verbose_remote_data():
    """Return a semi-random dict for use in defining a remote.

    For most tests, it"s desirable to create remotes with as few attributes
    as possible, so that the tests can specifically target and attempt to break
    specific features. This module specifically targets remotes, so it makes
    sense to provide as many attributes as possible.

    Note that 'username' and 'password' are write-only attributes.
    """
    data = gen_remote_data()
    data.update(
        {"password": str(uuid4()), "username": str(uuid4()), "policy": choice(DOWNLOAD_POLICIES)}
    )
    return data
