"""Tests that create/sync/distribute/publish MANY rpm plugin repositories."""

import os
import re

import pytest
import requests


@pytest.fixture
def cdn_certs_and_keys():
    cdn_client_cert = os.getenv("CDN_CLIENT_CERT", "").replace("\\n", "\n")
    cdn_client_key = os.getenv("CDN_CLIENT_KEY", "").replace("\\n", "\n")
    cdn_ca_cert = os.getenv("CDN_CA_CERT", "").replace("\\n", "\n")

    return cdn_client_cert, cdn_client_key, cdn_ca_cert


def _name_from_url(url):
    """Converts a remote-url into a string suitable for name-fields."""
    # https://cdn.redhat.com/content/dist/rhel/server/6/6Server/x86_64/extras/os
    # cdn_redhat_com_content_dist_rhel_server_6_6Server_x86_64_extras_os

    # drop trailing slash
    rstr = url.rstrip("/")

    # drop protocol
    if rstr.startswith("https://"):
        rstr = rstr[8:]
    elif rstr.startswith("http://"):
        rstr = rstr[7:]

    # convert ./- into underscore
    rstr = re.sub("[.\-/]", "_", rstr)  # noqa
    return rstr


# 'export FIPS_WORKFLOW="anything"' to run this suite
@pytest.mark.skipif(
    not os.environ.get("FIPS_WORKFLOW", None),
    reason="This is a SIX HOUR test suit - run only when you're sure it's what you need",
)
@pytest.mark.parallel
@pytest.mark.parametrize(
    "url",
    [
        "https://cdn.redhat.com/content/dist/rhel/server/6/6Server/x86_64/extras/os",
        "https://cdn.redhat.com/content/dist/rhel/server/6/6Server/x86_64/optional/os",
        "https://cdn.redhat.com/content/dist/rhel/server/6/6Server/x86_64/supplementary/os",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/os",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/extras/os",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/optional/os",
        "https://cdn.redhat.com/content/dist/rhel/server/6/6Server/x86_64/rhscl/1/os",
        "http://mirror.centos.org/centos-7/7/extras/x86_64/",
        "http://mirror.centos.org/centos-7/7/sclo/x86_64/sclo/",
        "https://cdn.redhat.com/content/eus/rhel/server/6/6.6/x86_64/optional/os",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7.7/x86_64/kickstart",
        "https://cdn.redhat.com/content/dist/rhel8/8.0/x86_64/baseos/kickstart",
        "https://mirrors.kernel.org/fedora-epel/7/x86_64/",
        "https://cdn.redhat.com/content/dist/rhel/server/6/6.7/x86_64/kickstart",
        "https://cdn.redhat.com/content/eus/rhel/server/6/6.6/x86_64/rhscl/1/os",
        "https://cdn.redhat.com/content/eus/rhel/server/6/6.6/x86_64/os",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7.3/x86_64/kickstart",
        "https://cdn.redhat.com/content/dist/rhel8/8.0/x86_64/appstream/kickstart",
        "https://cdn.redhat.com/content/eus/rhel/server/7/7.3/x86_64/optional/os",
        "https://cdn.redhat.com/content/eus/rhel/server/7/7.3/x86_64/supplementary/os",
        "https://cdn.redhat.com/content/eus/rhel/server/7/7.3/x86_64/rhscl/1/os",
        "http://vault.centos.org/6.10/os/x86_64/",
        "https://cdn.redhat.com/content/dist/rhel/server/6/6Server/x86_64/os",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/ansible/2.5/os",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/rhgs-server-nfs/3.1/os",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7.6/x86_64/kickstart",
        "https://cdn.redhat.com/content/dist/rhel/workstation/7/7.5/x86_64/kickstart",
        "https://mirrors.kernel.org/fedora-epel/8/Everything/x86_64/",
        "https://cdn.redhat.com/content/dist/rhel/workstation/7/7Workstation/x86_64/insights/3/os",
        "https://cdn.redhat.com/content/dist/rhel/workstation/7/7Workstation/x86_64/rh-common/os",
        "https://cdn.redhat.com/content/dist/rhel/workstation/7/7Workstation/x86_64/os",
        "https://cdn.redhat.com/content/dist/rhel/workstation/7/7Workstation/x86_64/extras/os",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/rh-gluster-samba/3.1/os",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/rhgs-server/3.1/os",
        "https://cdn.redhat.com/content/dist/rhel/server/6/6.10/x86_64/kickstart",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/rhgs-nagios/3.1/os",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/rhscon-agent/2/os",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/rhscon-main/2/os",
        "http://vault.centos.org/6.10/updates/x86_64/",
        "https://cdn.redhat.com/content/dist/rhel/server/6/6Server/x86_64/rhs-client/os",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/rhs-client/os",
        "http://mirror.centos.org/centos-7/7/sclo/x86_64/rh/",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/supplementary/os",
        "https://cdn.redhat.com/content/dist/rhel/workstation/7/7.6/x86_64/kickstart",
        "http://mirror.centos.org/centos-7/7/updates/x86_64/",
        "https://cdn.redhat.com/content/dist/rhel/server/6/6.8/x86_64/kickstart",
        "https://cdn.redhat.com/content/dist/rhel/server/6/6.9/x86_64/kickstart",
        "https://cdn.redhat.com/content/eus/rhel/server/6/6.6/x86_64/sat-tools/6.2/os",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/rhscl/1/os",
        "http://mirror.centos.org/centos-7/7/os/x86_64/",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/ansible/2.7/os",
        "https://cdn.redhat.com/content/eus/rhel/server/7/7.3/x86_64/os",
        "https://cdn.redhat.com/content/eus/rhel/server/7/7.6/x86_64/os",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7.4/x86_64/kickstart",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7.5/x86_64/kickstart",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/rhgs-server-bigdata/3.1/os",  # noqa E501
        "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/rhgs-server-splunk/3.1/os",  # noqa E501
        "https://cdn.redhat.com/content/dist/rhel/workstation/7/7Workstation/x86_64/supplementary/os",  # noqa E501
        "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/ansible/2.6/os",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/dotnet/1/os",
        "https://cdn.redhat.com/content/dist/rhel/server/6/6.10/x86_64/optional/os",
        "https://cdn.redhat.com/content/eus/rhel/server/7/7Server/x86_64/sat-tools/6.5/os",
        "https://cdn.redhat.com/content/eus/rhel/server/7/7.5/x86_64/sat-tools/6.5/os",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7.7/x86_64/optional/os",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7.4/x86_64/optional/os",
        "https://cdn.redhat.com/content/eus/rhel/server/6/6.7/x86_64/supplementary/os",
        "https://cdn.redhat.com/content/eus/rhel/server/6/6.7/x86_64/optional/os",
        "https://cdn.redhat.com/content/eus/rhel/server/6/6.7/x86_64/rhscl/1/os",
        "https://cdn.redhat.com/content/eus/rhel/server/7/7.5/x86_64/rhscl/1/os",
        "https://cdn.redhat.com/content/eus/rhel/server/7/7.5/x86_64/os",
        "https://cdn.redhat.com/content/dist/rhel/server/6/6.7/x86_64/optional/os",
        "https://cdn.redhat.com/content/dist/rhel/server/6/6.10/x86_64/os",
        "https://cdn.redhat.com/content/dist/rhel/server/6/6.8/x86_64/os",
        "https://cdn.redhat.com/content/dist/rhel/server/6/6.6/x86_64/os",
        "https://cdn.redhat.com/content/eus/rhel/server/6/6.7/x86_64/os",
        "https://cdn.redhat.com/content/eus/rhel/server/7/7.5/x86_64/supplementary/os",
        "https://cdn.redhat.com/content/eus/rhel/server/7/7.5/x86_64/sat-tools/6.4/os",
        "https://cdn.redhat.com/content/eus/rhel/server/7/7.5/x86_64/optional/os",
        "https://cdn.redhat.com/content/eus/rhel/server/7/7.3/x86_64/sat-tools/6.4/os",
        "https://cdn.redhat.com/content/dist/rhel8/8/x86_64/appstream/os",
        "https://cdn.redhat.com/content/dist/rhel8/8/x86_64/baseos/os",
        "https://cdn.redhat.com/content/dist/rhel8/8/x86_64/supplementary/os",
        "https://cdn.redhat.com/content/dist/rhel8/8/x86_64/baseos/kickstart",
        "https://cdn.redhat.com/content/dist/rhel8/8/x86_64/appstream/kickstart",
        "https://archives.fedoraproject.org/pub/archive/epel/6/x86_64/",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7.6/x86_64/optional/os",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7.3/x86_64/optional/os",
        "https://cdn.redhat.com/content/dist/rhel/server/6/6.9/x86_64/os",
        "https://cdn.redhat.com/content/dist/rhel/server/6/6.8/x86_64/optional/os",
        "https://cdn.redhat.com/content/dist/rhel/server/6/6.7/x86_64/os",
        "https://cdn.redhat.com/content/dist/rhel/server/6/6.9/x86_64/optional/os",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7.5/x86_64/optional/os",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7.2/x86_64/optional/os",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7.6/x86_64/os",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7.5/x86_64/os",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7.3/x86_64/os",
        "https://cdn.redhat.com/content/eus/rhel/server/7/7.6/x86_64/sat-tools/6.5/os",
        "https://cdn.redhat.com/content/eus/rhel/server/7/7.6/x86_64/optional/os",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/sat-capsule/6.6/os",
        "https://cdn.redhat.com/content/dist/rhel/server/6/6Server/x86_64/sat-tools/6.6/os",
        "https://cdn.redhat.com/content/dist/layered/rhel8/x86_64/sat-tools/6.6/os",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/ansible/2.8/os",
        "https://cdn.redhat.com/content/eus/rhel/server/7/7.6/x86_64/sat-tools/6.6/os",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7.7/x86_64/os",
        "https://cdn.redhat.com/content/dist/rhel8/8.1/x86_64/appstream/kickstart",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7.4/x86_64/os",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7.2/x86_64/os",
        "https://cdn.redhat.com/content/eus/rhel/server/7/7.6/x86_64/supplementary/os",
        "https://cdn.redhat.com/content/eus/rhel/server/7/7.6/x86_64/rhscl/1/os",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/sat-tools/6.6/os",
        "https://cdn.redhat.com/content/eus/rhel/server/7/7.5/x86_64/sat-tools/6.6/os",
        "https://cdn.redhat.com/content/dist/rhel8/8.1/x86_64/baseos/kickstart",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/highavailability/os",
        "https://packages.vmware.com/tools/releases/10.3.5/rhel6/x86_64/",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7.8/x86_64/kickstart",
        "https://cdn.redhat.com/content/eus/rhel/server/7/7.7/x86_64/os",
        "https://cdn.redhat.com/content/eus/rhel/server/7/7.7/x86_64/supplementary/os",
        "https://cdn.redhat.com/content/eus/rhel/server/7/7.7/x86_64/rhscl/1/os",
        "https://cdn.redhat.com/content/eus/rhel/server/7/7.7/x86_64/optional/os",
        "https://cdn.redhat.com/content/eus/rhel/server/7/7.7/x86_64/sat-tools/6.6/os",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/sat-capsule/6.7/os",
        "https://cdn.redhat.com/content/dist/rhel/server/6/6Server/x86_64/sat-tools/6.7/os",
        "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/sat-tools/6.7/os",
        "https://cdn.redhat.com/content/dist/layered/rhel8/x86_64/sat-tools/6.7/os",
        "https://cdn.redhat.com/content/dist/rhel8/8.2/x86_64/appstream/kickstart",
        "https://cdn.redhat.com/content/dist/rhel8/8.2/x86_64/baseos/kickstart",
        "http://mirror.centos.org/centos-8/8/BaseOS/x86_64/os/",
        "http://mirror.centos.org/centos-8/8/AppStream/x86_64/os/",
    ],
)
def test_fips_workflow(
    url,
    distribution_base_url,
    init_and_sync,
    rpm_rpmremote_factory,
    rpm_publication_factory,
    rpm_distribution_factory,
    cdn_certs_and_keys,
):
    # Convert a url into a name-string
    name = _name_from_url(url)

    # Create a remote
    body = {"url": url, "policy": "on_demand"}
    if name.startswith("cdn_"):
        if not all(cdn_certs_and_keys):
            pytest.skip("Can't test CDN repositories, missing certs")
        # need cert-access
        client_cert, client_key, ca_cert = cdn_certs_and_keys
        body["ca_cert"] = ca_cert
        body["client_cert"] = client_cert
        body["client_key"] = client_key
    remote = rpm_rpmremote_factory(**body)
    assert remote is not None

    # Create a repo & sync w/ remote
    repo, _ = init_and_sync(remote=remote)

    # Publish the result
    publication = rpm_publication_factory(repository=repo.pulp_href)
    assert publication is not None

    # Distribute the published version
    distribution = rpm_distribution_factory(publication=publication.pulp_href)
    assert distribution is not None

    # Test we can access the index of the distribution
    response = requests.get(distribution_base_url(distribution.base_url))
    assert response is not None
