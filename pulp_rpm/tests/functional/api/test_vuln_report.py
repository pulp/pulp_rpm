"""Functional tests for the scan action on RpmRepositoryVersionViewSet."""

import uuid

import pytest
import requests

from pulpcore.client.pulp_rpm.exceptions import ApiException

from pulp_rpm.tests.functional.utils import Nevra


def convert_osv_config(osv_config):
    return [c.model_dump() for c in osv_config]


_INVALID_OSV_CONFIG_PARAMS = [
    # unsupported ecosystem
    pytest.param([{"name": "NotAnEcosystem"}], "not a valid choice", id="unsupported_ecosystem"),
    # releases required
    pytest.param([{"name": "AlmaLinux"}], "releases", id="almalinux_missing_releases"),
    pytest.param(
        [{"name": "AlmaLinux", "releases": []}], "releases", id="almalinux_empty_releases"
    ),
    pytest.param([{"name": "Red Hat"}], "releases", id="redhat_missing_releases"),
    pytest.param([{"name": "Red Hat", "releases": []}], "releases", id="redhat_empty_releases"),
    # Red Hat releases: cpe:/<part>:redhat:...
    pytest.param(
        [{"name": "Red Hat", "releases": ["not-a-cpe"]}],
        "valid CPE URI",
        id="redhat_invalid_cpe_format",
    ),
    pytest.param(
        [{"name": "Red Hat", "releases": ["cpe:/o:canonical:ubuntu:22.04"]}],
        "valid CPE URI",
        id="redhat_cpe_wrong_vendor",
    ),
    # numeric releases (e.g. 9 or 3.0)
    pytest.param(
        [{"name": "AlmaLinux", "releases": ["el9"]}],
        "version number",
        id="almalinux_invalid_release_format",
    ),
    pytest.param(
        [{"name": "Azure Linux", "releases": ["azure3"]}],
        "version number",
        id="azure_linux_invalid_release_format",
    ),
    pytest.param(
        [{"name": "Mageia", "releases": ["latest"]}],
        "version number",
        id="mageia_invalid_release_format",
    ),
    pytest.param(
        [{"name": "Photon OS", "releases": ["photon4"]}],
        "version number",
        id="photon_invalid_release_format",
    ),
    pytest.param(
        [{"name": "Rocky Linux", "releases": ["nine"]}],
        "version number",
        id="rocky_invalid_release_format",
    ),
    # YY.MM format (e.g. 22.03)
    pytest.param(
        [{"name": "openEuler", "releases": ["2022.03"]}],
        "YY.MM",
        id="openeuler_invalid_release_year",
    ),
    pytest.param(
        [{"name": "openEuler", "releases": ["22.3"]}],
        "YY.MM",
        id="openeuler_invalid_release_month",
    ),
]


class TestOsvConfig:
    ALMA_CONFIG = [{"name": "AlmaLinux", "releases": ["9"]}]
    REDHAT_CONFIG = [{"name": "Red Hat", "releases": ["cpe:/o:redhat:enterprise_linux:9"]}]

    @pytest.mark.parallel
    @pytest.mark.parametrize("osv_config,expected", _INVALID_OSV_CONFIG_PARAMS)
    def test_invalid_config(self, osv_config, expected, pulp_api_v3_url, bindings_cfg):
        """Invalid osv_config is rejected at repository creation."""
        resp = requests.post(
            f"{pulp_api_v3_url}repositories/rpm/rpm/",
            json={"name": str(uuid.uuid4()), "osv_config": osv_config},
            auth=(bindings_cfg.username, bindings_cfg.password),
            verify=False,
        )
        assert resp.status_code == 400
        assert expected in resp.text

    @pytest.mark.parallel
    def test_missing_config(self, rpm_repository_factory, rpm_repository_versions_api):
        """Repository without osv_config returns 400 when scan is called."""
        repo = rpm_repository_factory()
        with pytest.raises(ApiException) as exc:
            rpm_repository_versions_api.scan(repo.latest_version_href)
        assert exc.value.status == 400
        assert "Required label" in exc.value.body

    @pytest.mark.parallel
    def test_field_read(self, rpm_repository_factory, rpm_repository_api):
        """osv_config field in repository response reflects the stored config."""
        repo = rpm_repository_factory(osv_config=self.ALMA_CONFIG)
        cfg = rpm_repository_api.read(repo.pulp_href).osv_config
        assert convert_osv_config(cfg) == self.ALMA_CONFIG

    @pytest.mark.parallel
    def test_field_update(self, rpm_repository_factory, rpm_repository_api, monitor_task):
        """osv_config field updates when changed via partial_update."""
        repo = rpm_repository_factory()
        assert rpm_repository_api.read(repo.pulp_href).osv_config is None

        monitor_task(
            rpm_repository_api.partial_update(
                repo.pulp_href, {"osv_config": self.REDHAT_CONFIG}
            ).task
        )
        cfg = rpm_repository_api.read(repo.pulp_href).osv_config
        assert convert_osv_config(cfg) == self.REDHAT_CONFIG

    @pytest.mark.parallel
    def test_field_delete(self, rpm_repository_factory, rpm_repository_api, monitor_task):
        """Setting osv_config to null removes it from the repository."""
        repo = rpm_repository_factory(osv_config=self.ALMA_CONFIG)
        cfg = rpm_repository_api.read(repo.pulp_href).osv_config
        assert convert_osv_config(cfg) == self.ALMA_CONFIG

        monitor_task(rpm_repository_api.partial_update(repo.pulp_href, {"osv_config": None}).task)
        assert rpm_repository_api.read(repo.pulp_href).osv_config is None


class TestVulnReportIntegration:
    EXPECTED_RHSA_IDS = [
        "RHSA-2014:0678",
        "RHSA-2014:0786",
        "RHSA-2014:0923",
        "RHSA-2014:1023",
        "RHSA-2014:1281",
        "RHSA-2014:1724",
        "RHSA-2014:1971",
        "RHSA-2014:2010",
    ]
    REDHAT_CPE_CONFIG = [
        {"name": "Red Hat", "releases": ["cpe:/o:redhat:enterprise_linux:7::workstation"]}
    ]

    @pytest.mark.parallel
    def test_vuln_report_redhat(
        self,
        rpm_repository_factory,
        rpm_create_package,
        monitor_task,
        rpm_repository_versions_api,
        pulpcore_bindings,
    ):
        """Known RHSA IDs appear in the report for a Red Hat config with CPEs."""
        kernel_nevra = Nevra(
            name="kernel", epoch=0, version="3.10.0", release="123.el7", arch="x86_64"
        )
        repo = rpm_repository_factory(
            osv_config=self.REDHAT_CPE_CONFIG,
            upload_packages=[rpm_create_package(kernel_nevra)],
            monitor_task=monitor_task,
        )

        resp = rpm_repository_versions_api.scan(repo.latest_version_href)
        monitor_task(resp.task)

        vulns_list = pulpcore_bindings.VulnReportApi.list()
        assert len(vulns_list.results) > 0
        ids = {vuln["id"] for report in vulns_list.results for vuln in report.vulns}
        assert set(self.EXPECTED_RHSA_IDS).issubset(ids)

        repo_version = rpm_repository_versions_api.read(repo.latest_version_href)
        assert repo_version.vuln_report is not None
