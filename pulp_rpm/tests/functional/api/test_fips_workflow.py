"""Tests that create/sync/distribute/publish MANY rpm plugin repositories."""
import os
import re
import unittest

from pulp_smash import config
from pulp_smash.pulp3.bindings import PulpTestCase, monitor_task

from pulp_rpm.tests.functional.utils import (
    gen_rpm_client,
    skip_if,
)

from pulpcore.client.pulp_rpm import (
    DistributionsRpmApi,
    PublicationsRpmApi,
    RemotesRpmApi,
    RepositoriesRpmApi,
    RpmRepositorySyncURL,
    RpmRpmPublication,
)


# 'export FIPS_WORKFLOW=anything"' to run this suite
@unittest.skipIf(
    not os.environ.get("FIPS_WORKFLOW", None),
    "This is a SIX HOUR test suit - run only when you're sure it's what you need",
)
class FipsRemotesTestCase(PulpTestCase):
    """
    Tests a large number of repositories for the full RPM workflow (create/sync/distribute/publish).

    Primarily useful for testing a wide range of 'real' repositories in the face of global
    issues like FIPS-enabled systems. The list of repositories of interest is taken from
    https://pulp.plan.io/issues/7537

    Because it is a long-running intensive set of tests, the entire test-class is skipped
    unless an environment-variable FIPS_WORKFLOW is set.

    For Red Hat CDN repositories, assumes that appropriate certificates are stored in the
    environment variables CDN_CA_CERT, CDN_CLIENT_CERT, and CDN_CLIENT_KEY.

    Tests as implemented use on_demand syncing. Running the entire test suit takes ~6 hours.
    Switching to immediate would take much longer, and require A LOT of disk space.

    NOTE: We check only for successful-completion of the various steps. It is 'assumed' that,
    when these tests run, we're already confident that the create/sync/distribute/publish
    path is reliable; any failures here would be due to specific data-issues, or configuration
    (e.g., FIPS realities and repository-checksum-realities interfering with each other).
    """

    @staticmethod
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

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = gen_rpm_client()
        cls.repo_api = RepositoriesRpmApi(cls.client)
        cls.remote_api = RemotesRpmApi(gen_rpm_client())
        cls.publications = PublicationsRpmApi(cls.client)
        cls.distributions = DistributionsRpmApi(cls.client)

        if (
            os.environ.get("CDN_CLIENT_CERT", None)
            and os.environ.get("CDN_CLIENT_KEY", None)
            and os.environ.get("CDN_CA_CERT", None)
        ):
            # strings have escaped newlines from environmental variable
            cls.cdn_client_cert = os.environ["CDN_CLIENT_CERT"].replace("\\n", "\n")
            cls.cdn_client_key = os.environ["CDN_CLIENT_KEY"].replace("\\n", "\n")
            cls.cdn_ca_cert = os.environ["CDN_CA_CERT"].replace("\\n", "\n")
        else:
            cls.cdn_client_cert = None

    def _create_remote_for(self, url):
        name = self._name_from_url(url)
        body = {"name": name, "url": url, "policy": "on_demand"}
        # Red Hat repos are at cdn.redhat.com, and require cert-auth for access
        if name.startswith("cdn_"):
            self.assertIsNotNone(self.cdn_client_cert, "Can't test CDN repositories, missing certs")
            # need cert-access
            body["ca_cert"] = self.cdn_ca_cert
            body["client_cert"] = self.cdn_client_cert
            body["client_key"] = self.cdn_client_key
        remote = self.remote_api.create(body)
        return remote

    def _create_repo_for(self, url):
        name = self._name_from_url(url)
        body = {"name": name}
        repo = self.repo_api.create(body)
        return repo

    def _create_publication_for(self, repo):
        publish_data = RpmRpmPublication(repository=repo.pulp_href)
        publish_response = self.publications.create(publish_data)
        created_resources = monitor_task(publish_response.task).created_resources
        self.assertIsNotNone(created_resources)
        self.assertTrue(len(created_resources) > 0)
        publication_href = created_resources[0]
        return publication_href

    def _create_distribution_for(self, name, pub):
        body = {"base_path": name, "name": name, "publication": pub}
        distribution_response = self.distributions.create(body)
        created_resources = monitor_task(distribution_response.task).created_resources
        self.assertIsNotNone(created_resources)
        self.assertTrue(len(created_resources) > 0)
        distribution = self.distributions.read(created_resources[0])
        return distribution

    def _do_test(self, url):
        # Convert a url into a name-string
        name = self._name_from_url(url)

        # Create a repo
        repo = self._create_repo_for(url)
        self.assertIsNotNone(repo)
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        # Create a remote
        remote = self._create_remote_for(url)
        self.assertIsNotNone(remote)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        # Sync the repo using the remote
        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)

        # Publish the result
        publication_href = self._create_publication_for(repo)
        self.assertIsNotNone(publication_href)
        self.addCleanup(self.publications.delete, publication_href)

        # Distribute the published version
        distribution = self._create_distribution_for(name, publication_href)
        self.assertIsNotNone(distribution)
        self.addCleanup(self.distributions.delete, distribution.pulp_href)

    @skip_if(bool, "cdn_client_cert", False)
    def test_000_cdn_redhat_com_content_dist_rhel_server_6_6Server_x86_64_extras_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/6/6Server/x86_64/extras/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_001_cdn_redhat_com_content_dist_rhel_server_6_6Server_x86_64_optional_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/6/6Server/x86_64/optional/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_002_cdn_redhat_com_content_dist_rhel_server_6_6Server_x86_64_supplementary_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/6/6Server/x86_64/supplementary/os"
        self._do_test(url)

    @unittest.skip("fails with 'NoneType' object is not subscriptable?")
    @skip_if(bool, "cdn_client_cert", False)
    def test_003_cdn_redhat_com_content_dist_rhel_server_7_7Server_x86_64_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_004_cdn_redhat_com_content_dist_rhel_server_7_7Server_x86_64_extras_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/extras/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_005_cdn_redhat_com_content_dist_rhel_server_7_7Server_x86_64_optional_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/optional/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_006_cdn_redhat_com_content_dist_rhel_server_6_6Server_x86_64_rhscl_1_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/6/6Server/x86_64/rhscl/1/os"
        self._do_test(url)

    def test_007_mirror_centos_org_centos_7_7_extras_x86_64(self):  # noqa D102
        url = "http://mirror.centos.org/centos-7/7/extras/x86_64/"
        self._do_test(url)

    def test_008_mirror_centos_org_centos_7_7_sclo_x86_64_sclo(self):  # noqa D102
        url = "http://mirror.centos.org/centos-7/7/sclo/x86_64/sclo/"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_009_cdn_redhat_com_content_eus_rhel_server_6_6_6_x86_64_optional_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/eus/rhel/server/6/6.6/x86_64/optional/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_010_cdn_redhat_com_content_dist_rhel_server_7_7_7_x86_64_kickstart(self):  # noqa D102
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7.7/x86_64/kickstart"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_011_cdn_redhat_com_content_dist_rhel8_8_0_x86_64_baseos_kickstart(self):  # noqa D102
        url = "https://cdn.redhat.com/content/dist/rhel8/8.0/x86_64/baseos/kickstart"
        self._do_test(url)

    def test_012_mirrors_kernel_org_fedora_epel_7_x86_64(self):  # noqa D102
        url = "https://mirrors.kernel.org/fedora-epel/7/x86_64/"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_013_cdn_redhat_com_content_dist_rhel_server_6_6_7_x86_64_kickstart(self):  # noqa D102
        url = "https://cdn.redhat.com/content/dist/rhel/server/6/6.7/x86_64/kickstart"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_014_cdn_redhat_com_content_eus_rhel_server_6_6_6_x86_64_rhscl_1_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/eus/rhel/server/6/6.6/x86_64/rhscl/1/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_015_cdn_redhat_com_content_eus_rhel_server_6_6_6_x86_64_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/eus/rhel/server/6/6.6/x86_64/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_016_cdn_redhat_com_content_dist_rhel_server_7_7_3_x86_64_kickstart(self):  # noqa D102
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7.3/x86_64/kickstart"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_017_cdn_redhat_com_content_dist_rhel8_8_0_x86_64_appstream_kickstart(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel8/8.0/x86_64/appstream/kickstart"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_018_cdn_redhat_com_content_eus_rhel_server_7_7_3_x86_64_optional_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/eus/rhel/server/7/7.3/x86_64/optional/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_019_cdn_redhat_com_content_eus_rhel_server_7_7_3_x86_64_supplementary_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/eus/rhel/server/7/7.3/x86_64/supplementary/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_020_cdn_redhat_com_content_eus_rhel_server_7_7_3_x86_64_rhscl_1_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/eus/rhel/server/7/7.3/x86_64/rhscl/1/os"
        self._do_test(url)

    def test_021_mirror_centos_org_centos_6_6_os_x86_64(self):  # noqa D102
        # centos-6 has been archived, 6.10 is the last one
        url = "http://vault.centos.org/6.10/os/x86_64/"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_022_cdn_redhat_com_content_dist_rhel_server_6_6Server_x86_64_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/dist/rhel/server/6/6Server/x86_64/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_023_cdn_redhat_com_content_dist_rhel_server_7_7Server_x86_64_ansible_2_5_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/ansible/2.5/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_024_cdn_redhat_com_content_dist_rhel_server_7_7Server_x86_64_rhgs_server_nfs_3_1_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/rhgs-server-nfs/3.1/os"  # noqa E501
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_025_cdn_redhat_com_content_dist_rhel_server_7_7_6_x86_64_kickstart(self):  # noqa D102
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7.6/x86_64/kickstart"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_026_cdn_redhat_com_content_dist_rhel_workstation_7_7_5_x86_64_kickstart(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/workstation/7/7.5/x86_64/kickstart"
        self._do_test(url)

    def test_027_mirrors_kernel_org_fedora_epel_8_Everything_x86_64(self):  # noqa D102
        url = "https://mirrors.kernel.org/fedora-epel/8/Everything/x86_64/"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_028_cdn_redhat_com_content_dist_rhel_workstation_7_7Workstation_x86_64_insights_3_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/workstation/7/7Workstation/x86_64/insights/3/os"  # noqa E501
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_029_cdn_redhat_com_content_dist_rhel_workstation_7_7Workstation_x86_64_optional_os(  # noqa D102
        self,
    ):
        url = (
            "https://cdn.redhat.com/content/dist/rhel/workstation/7/7Workstation/x86_64/optional/os"
        )
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_030_cdn_redhat_com_content_dist_rhel_workstation_7_7Workstation_x86_64_rh_common_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/workstation/7/7Workstation/x86_64/rh-common/os"  # noqa E501
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_031_cdn_redhat_com_content_dist_rhel_workstation_7_7Workstation_x86_64_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/workstation/7/7Workstation/x86_64/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_032_cdn_redhat_com_content_dist_rhel_workstation_7_7Workstation_x86_64_extras_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/workstation/7/7Workstation/x86_64/extras/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_033_cdn_redhat_com_content_dist_rhel_server_7_7Server_x86_64_rh_gluster_samba_3_1_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/rh-gluster-samba/3.1/os"  # noqa E501
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_034_cdn_redhat_com_content_dist_rhel_server_7_7Server_x86_64_rhgs_server_3_1_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/rhgs-server/3.1/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_035_cdn_redhat_com_content_dist_rhel_server_6_6_10_x86_64_kickstart(self):  # noqa D102
        url = "https://cdn.redhat.com/content/dist/rhel/server/6/6.10/x86_64/kickstart"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_036_cdn_redhat_com_content_dist_rhel_server_7_7Server_x86_64_rhgs_nagios_3_1_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/rhgs-nagios/3.1/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_037_cdn_redhat_com_content_dist_rhel_server_7_7Server_x86_64_rhscon_agent_2_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/rhscon-agent/2/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_038_cdn_redhat_com_content_dist_rhel_server_7_7Server_x86_64_rhscon_installer_2_os(  # noqa D102
        self,
    ):
        url = (
            "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/rhscon-installer/2/os"
        )
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_039_cdn_redhat_com_content_dist_rhel_server_7_7Server_x86_64_rhscon_main_2_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/rhscon-main/2/os"
        self._do_test(url)

    def test_040_mirror_centos_org_centos_6_6_updates_x86_64(self):  # noqa D102
        # centos-6 has been archived, 6.10 is the last one
        url = "http://vault.centos.org/6.10/updates/x86_64/"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_041_cdn_redhat_com_content_dist_rhel_server_6_6Server_x86_64_rhs_client_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/6/6Server/x86_64/rhs-client/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_042_cdn_redhat_com_content_dist_rhel_server_7_7Server_x86_64_rhs_client_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/rhs-client/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_043_mirror_centos_org_centos_7_7_sclo_x86_64_rh(self):  # noqa D102
        url = "http://mirror.centos.org/centos-7/7/sclo/x86_64/rh/"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_044_cdn_redhat_com_content_dist_rhel_server_7_7Server_x86_64_supplementary_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/supplementary/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_045_cdn_redhat_com_content_dist_rhel_workstation_7_7Workstation_x86_64_rhscl_1_os(  # noqa D102
        self,
    ):
        url = (
            "https://cdn.redhat.com/content/dist/rhel/workstation/7/7Workstation/x86_64/rhscl/1/os"
        )
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_046_cdn_redhat_com_content_dist_rhel_workstation_7_7_6_x86_64_kickstart(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/workstation/7/7.6/x86_64/kickstart"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_047_mirror_centos_org_centos_7_7_updates_x86_64(self):  # noqa D102
        url = "http://mirror.centos.org/centos-7/7/updates/x86_64/"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_048_cdn_redhat_com_content_dist_rhel_server_6_6_8_x86_64_kickstart(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/6/6.8/x86_64/kickstart"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_049_cdn_redhat_com_content_dist_rhel_server_6_6_9_x86_64_kickstart(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/6/6.9/x86_64/kickstart"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_050_cdn_redhat_com_content_eus_rhel_server_6_6_6_x86_64_sat_tools_6_2_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/eus/rhel/server/6/6.6/x86_64/sat-tools/6.2/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_051_cdn_redhat_com_content_dist_rhel_server_7_7Server_x86_64_rhscl_1_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/rhscl/1/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_052_mirror_centos_org_centos_7_7_os_x86_64(self):  # noqa D102
        url = "http://mirror.centos.org/centos-7/7/os/x86_64/"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_053_cdn_redhat_com_content_dist_rhel_server_7_7Server_x86_64_ansible_2_7_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/ansible/2.7/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_054_cdn_redhat_com_content_eus_rhel_server_7_7_3_x86_64_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/eus/rhel/server/7/7.3/x86_64/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_055_cdn_redhat_com_content_eus_rhel_server_7_7_6_x86_64_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/eus/rhel/server/7/7.6/x86_64/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_056_cdn_redhat_com_content_dist_rhel_server_7_7_4_x86_64_kickstart(self):  # noqa D102
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7.4/x86_64/kickstart"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_057_cdn_redhat_com_content_dist_rhel_server_7_7Server_x86_64_sat_maintenance_6_os(  # noqa D102
        self,
    ):
        url = (
            "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/sat-maintenance/6/os"
        )
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_058_cdn_redhat_com_content_dist_rhel_server_7_7_5_x86_64_kickstart(self):  # noqa D102
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7.5/x86_64/kickstart"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_059_cdn_redhat_com_content_dist_rhel_server_7_7Server_x86_64_rhgs_server_bigdata_3_1_os(  # noqa E501
        self,
    ):  # noqa D102
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/rhgs-server-bigdata/3.1/os"  # noqa E501
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_060_cdn_redhat_com_content_dist_rhel_server_7_7Server_x86_64_rhgs_server_splunk_3_1_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/rhgs-server-splunk/3.1/os"  # noqa E501
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_061_cdn_redhat_com_content_dist_rhel_workstation_7_7Workstation_x86_64_supplementary_os(  # noqa E501
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/workstation/7/7Workstation/x86_64/supplementary/os"  # noqa E501
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_062_cdn_redhat_com_content_dist_rhel_server_7_7Server_x86_64_ansible_2_6_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/ansible/2.6/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_063_cdn_redhat_com_content_dist_rhel_server_7_7Server_x86_64_dotnet_1_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/dotnet/1/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_064_cdn_redhat_com_content_dist_rhel_server_6_6_10_x86_64_optional_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/6/6.10/x86_64/optional/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_065_cdn_redhat_com_content_eus_rhel_server_7_7Server_x86_64_sat_tools_6_5_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/eus/rhel/server/7/7Server/x86_64/sat-tools/6.5/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_066_cdn_redhat_com_content_eus_rhel_server_7_7_5_x86_64_sat_tools_6_5_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/eus/rhel/server/7/7.5/x86_64/sat-tools/6.5/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_067_cdn_redhat_com_content_dist_rhel_server_7_7_7_x86_64_optional_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7.7/x86_64/optional/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_068_cdn_redhat_com_content_dist_rhel_server_7_7_4_x86_64_optional_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7.4/x86_64/optional/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_069_cdn_redhat_com_content_eus_rhel_server_6_6_7_x86_64_supplementary_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/eus/rhel/server/6/6.7/x86_64/supplementary/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_070_cdn_redhat_com_content_eus_rhel_server_6_6_7_x86_64_optional_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/eus/rhel/server/6/6.7/x86_64/optional/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_071_cdn_redhat_com_content_eus_rhel_server_6_6_7_x86_64_rhscl_1_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/eus/rhel/server/6/6.7/x86_64/rhscl/1/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_072_cdn_redhat_com_content_eus_rhel_server_7_7_5_x86_64_rhscl_1_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/eus/rhel/server/7/7.5/x86_64/rhscl/1/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_073_cdn_redhat_com_content_eus_rhel_server_7_7_5_x86_64_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/eus/rhel/server/7/7.5/x86_64/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_074_cdn_redhat_com_content_dist_rhel_server_6_6_7_x86_64_optional_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/6/6.7/x86_64/optional/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_075_cdn_redhat_com_content_dist_rhel_server_6_6_10_x86_64_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/dist/rhel/server/6/6.10/x86_64/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_076_cdn_redhat_com_content_dist_rhel_server_6_6_8_x86_64_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/dist/rhel/server/6/6.8/x86_64/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_077_cdn_redhat_com_content_dist_rhel_server_6_6_6_x86_64_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/dist/rhel/server/6/6.6/x86_64/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_078_cdn_redhat_com_content_eus_rhel_server_6_6_7_x86_64_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/eus/rhel/server/6/6.7/x86_64/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_079_cdn_redhat_com_content_eus_rhel_server_7_7_5_x86_64_supplementary_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/eus/rhel/server/7/7.5/x86_64/supplementary/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_080_cdn_redhat_com_content_eus_rhel_server_7_7_5_x86_64_sat_tools_6_4_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/eus/rhel/server/7/7.5/x86_64/sat-tools/6.4/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_081_cdn_redhat_com_content_eus_rhel_server_7_7_5_x86_64_optional_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/eus/rhel/server/7/7.5/x86_64/optional/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_082_cdn_redhat_com_content_eus_rhel_server_7_7_3_x86_64_sat_tools_6_4_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/eus/rhel/server/7/7.3/x86_64/sat-tools/6.4/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_083_cdn_redhat_com_content_dist_rhel8_8_x86_64_appstream_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/dist/rhel8/8/x86_64/appstream/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_084_cdn_redhat_com_content_dist_rhel8_8_x86_64_baseos_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/dist/rhel8/8/x86_64/baseos/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_085_cdn_redhat_com_content_dist_rhel8_8_x86_64_supplementary_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/dist/rhel8/8/x86_64/supplementary/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_086_cdn_redhat_com_content_dist_rhel8_8_x86_64_baseos_kickstart(self):  # noqa D102
        url = "https://cdn.redhat.com/content/dist/rhel8/8/x86_64/baseos/kickstart"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_087_cdn_redhat_com_content_dist_rhel8_8_x86_64_appstream_kickstart(self):  # noqa D102
        url = "https://cdn.redhat.com/content/dist/rhel8/8/x86_64/appstream/kickstart"
        self._do_test(url)

    def test_088_mirrors_kernel_org_fedora_epel_6Server_x86_64(self):  # noqa D102
        # epel 6 has been archived
        url = "https://archives.fedoraproject.org/pub/archive/epel/6/x86_64/"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_089_cdn_redhat_com_content_dist_rhel_server_7_7_6_x86_64_optional_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7.6/x86_64/optional/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_090_cdn_redhat_com_content_dist_rhel_server_7_7_3_x86_64_optional_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7.3/x86_64/optional/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_091_cdn_redhat_com_content_dist_rhel_server_6_6_9_x86_64_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/dist/rhel/server/6/6.9/x86_64/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_092_cdn_redhat_com_content_dist_rhel_server_6_6_8_x86_64_optional_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/6/6.8/x86_64/optional/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_093_cdn_redhat_com_content_dist_rhel_server_6_6_7_x86_64_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/dist/rhel/server/6/6.7/x86_64/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_094_cdn_redhat_com_content_dist_rhel_server_6_6_9_x86_64_optional_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/6/6.9/x86_64/optional/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_095_cdn_redhat_com_content_dist_rhel_server_7_7_5_x86_64_optional_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7.5/x86_64/optional/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_096_cdn_redhat_com_content_dist_rhel_server_7_7_2_x86_64_optional_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7.2/x86_64/optional/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_097_cdn_redhat_com_content_dist_rhel_server_7_7_6_x86_64_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7.6/x86_64/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_098_cdn_redhat_com_content_dist_rhel_server_7_7_5_x86_64_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7.5/x86_64/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_099_cdn_redhat_com_content_dist_rhel_server_7_7_3_x86_64_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7.3/x86_64/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_100_cdn_redhat_com_content_eus_rhel_server_7_7_6_x86_64_sat_tools_6_5_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/eus/rhel/server/7/7.6/x86_64/sat-tools/6.5/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_101_cdn_redhat_com_content_eus_rhel_server_7_7_6_x86_64_optional_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/eus/rhel/server/7/7.6/x86_64/optional/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_102_cdn_redhat_com_content_dist_rhel_server_7_7Server_x86_64_sat_capsule_6_6_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/sat-capsule/6.6/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_103_cdn_redhat_com_content_dist_rhel_server_6_6Server_x86_64_sat_tools_6_6_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/6/6Server/x86_64/sat-tools/6.6/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_104_cdn_redhat_com_content_dist_layered_rhel8_x86_64_sat_tools_6_6_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/layered/rhel8/x86_64/sat-tools/6.6/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_105_cdn_redhat_com_content_dist_rhel_server_7_7Server_x86_64_ansible_2_8_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/ansible/2.8/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_106_cdn_redhat_com_content_eus_rhel_server_7_7_6_x86_64_sat_tools_6_6_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/eus/rhel/server/7/7.6/x86_64/sat-tools/6.6/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_107_cdn_redhat_com_content_dist_rhel_server_7_7_7_x86_64_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7.7/x86_64/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_108_cdn_redhat_com_content_dist_rhel8_8_1_x86_64_appstream_kickstart(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel8/8.1/x86_64/appstream/kickstart"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_109_cdn_redhat_com_content_dist_rhel_server_7_7_4_x86_64_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7.4/x86_64/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_110_cdn_redhat_com_content_dist_rhel_server_7_7_2_x86_64_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7.2/x86_64/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_111_cdn_redhat_com_content_eus_rhel_server_7_7_6_x86_64_supplementary_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/eus/rhel/server/7/7.6/x86_64/supplementary/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_112_cdn_redhat_com_content_eus_rhel_server_7_7_6_x86_64_rhscl_1_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/eus/rhel/server/7/7.6/x86_64/rhscl/1/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_113_cdn_redhat_com_content_dist_rhel_server_7_7Server_x86_64_sat_tools_6_6_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/sat-tools/6.6/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_114_cdn_redhat_com_content_eus_rhel_server_7_7_5_x86_64_sat_tools_6_6_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/eus/rhel/server/7/7.5/x86_64/sat-tools/6.6/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_115_cdn_redhat_com_content_dist_rhel8_8_1_x86_64_baseos_kickstart(self):  # noqa D102
        url = "https://cdn.redhat.com/content/dist/rhel8/8.1/x86_64/baseos/kickstart"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_116_cdn_redhat_com_content_dist_rhel_server_7_7Server_x86_64_highavailability_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/highavailability/os"
        self._do_test(url)

    def test_117_packages_vmware_com_tools_releases_10_3_5_rhel6_x86_64(self):  # noqa D102
        url = "https://packages.vmware.com/tools/releases/10.3.5/rhel6/x86_64/"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_118_cdn_redhat_com_content_dist_rhel_server_7_7_8_x86_64_kickstart(self):  # noqa D102
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7.8/x86_64/kickstart"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_119_cdn_redhat_com_content_eus_rhel_server_7_7_7_x86_64_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/eus/rhel/server/7/7.7/x86_64/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_120_cdn_redhat_com_content_eus_rhel_server_7_7_7_x86_64_supplementary_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/eus/rhel/server/7/7.7/x86_64/supplementary/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_121_cdn_redhat_com_content_eus_rhel_server_7_7_7_x86_64_rhscl_1_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/eus/rhel/server/7/7.7/x86_64/rhscl/1/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_122_cdn_redhat_com_content_eus_rhel_server_7_7_7_x86_64_optional_os(self):  # noqa D102
        url = "https://cdn.redhat.com/content/eus/rhel/server/7/7.7/x86_64/optional/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_123_cdn_redhat_com_content_eus_rhel_server_7_7_7_x86_64_sat_tools_6_6_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/eus/rhel/server/7/7.7/x86_64/sat-tools/6.6/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_124_cdn_redhat_com_content_dist_rhel_server_7_7Server_x86_64_sat_capsule_6_7_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/sat-capsule/6.7/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_125_cdn_redhat_com_content_dist_rhel_server_6_6Server_x86_64_sat_tools_6_7_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/6/6Server/x86_64/sat-tools/6.7/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_126_cdn_redhat_com_content_dist_rhel_server_7_7Server_x86_64_sat_tools_6_7_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/sat-tools/6.7/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_127_cdn_redhat_com_content_dist_layered_rhel8_x86_64_sat_tools_6_7_os(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/layered/rhel8/x86_64/sat-tools/6.7/os"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_128_cdn_redhat_com_content_dist_rhel8_8_2_x86_64_appstream_kickstart(  # noqa D102
        self,
    ):
        url = "https://cdn.redhat.com/content/dist/rhel8/8.2/x86_64/appstream/kickstart"
        self._do_test(url)

    @skip_if(bool, "cdn_client_cert", False)
    def test_129_cdn_redhat_com_content_dist_rhel8_8_2_x86_64_baseos_kickstart(self):  # noqa D102
        url = "https://cdn.redhat.com/content/dist/rhel8/8.2/x86_64/baseos/kickstart"
        self._do_test(url)

    def test_130_mirror_centos_org_centos_8_8_BaseOS_x86_64_os(self):  # noqa D102
        url = "http://mirror.centos.org/centos-8/8/BaseOS/x86_64/os/"
        self._do_test(url)

    def test_131_mirror_centos_org_centos_8_8_AppStream_x86_64_os(self):  # noqa D102
        url = "http://mirror.centos.org/centos-8/8/AppStream/x86_64/os/"
        self._do_test(url)
