import pytest
import uuid

from django.conf import settings

from pulpcore.client.pulp_rpm import RpmRepositorySyncURL

from pulp_smash.pulp3.utils import gen_repo
from pulp_smash.pulp3.bindings import monitor_task

from pulp_rpm.tests.functional.utils import gen_rpm_remote
from pulp_rpm.tests.functional.constants import (
    RPM_SIGNED_FIXTURE_URL,
)


if not settings.DOMAIN_ENABLED:
    pytest.skip("Domains not enabled.", allow_module_level=True)


def test_doamin_create(
    delete_orphans_pre,
    domains_api_client,
    gen_object_with_cleanup,
    rpm_repository_api,
    rpm_rpmremote_api,
):
    """Test domain creation."""
    new_domain = str(uuid.uuid4())
    body = {
        "name": new_domain,
        "storage_class": "pulpcore.app.models.storage.FileSystem",
        "storage_settings": {"MEDIA_ROOT": "/var/lib/pulp/media/"},
    }
    domain = gen_object_with_cleanup(domains_api_client, body)
    domain_name = domain.name
    assert domain_name == new_domain

    # sync remote in default domain (not specified)
    remote_data = gen_rpm_remote(RPM_SIGNED_FIXTURE_URL)
    remote = gen_object_with_cleanup(rpm_rpmremote_api, remote_data)
    repo_data = gen_repo(remote=remote.pulp_href)
    repo = gen_object_with_cleanup(rpm_repository_api, repo_data)
    sync_url = RpmRepositorySyncURL(remote=remote.pulp_href)
    sync_response = rpm_repository_api.sync(repo.pulp_href, sync_url)
    monitor_task(sync_response.task)

    assert rpm_repository_api.list(pulp_domain="default").count == 1
    # check that newly created domain doesn't have any repo
    assert rpm_repository_api.list(pulp_domain=new_domain).count == 0
