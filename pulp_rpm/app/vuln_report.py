from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from typing import Any, TypedDict

from pulpcore.plugin.models import RepositoryVersion  # type: ignore[import-untyped]

from pulp_rpm.app.constants import REDHAT_CPE_RE
from pulp_rpm.app.models import Package
from pulp_rpm.app.serializers.repository import OsvConfigSerializer


class OsvPackage(TypedDict):
    name: str
    ecosystem: str


class OsvQuery(TypedDict):
    version: str
    package: OsvPackage


class VulnReportPayload(OsvQuery):
    """Format required by pulpcore's Vulnerability Report feature."""

    content: Any
    repo_version: RepositoryVersion


# --- Helpers ---


def build_osv_queries(
    name: str, version: str, ecosystems: list[dict]
) -> Generator[OsvQuery, None, None]:
    """Yield OSV query dicts for the given package and ecosystems.

    For Red Hat entries with CPEs, each CPE is converted to an ecosystem string.
    For all other entries, the ecosystem name is used directly.
    """
    for ecosystem in ecosystems:
        eco_name = ecosystem["name"]
        for release in ecosystem.get("releases", []):
            if eco_name == "Red Hat":
                ecosystem_str = REDHAT_CPE_RE.sub(eco_name, release)
            else:
                ecosystem_str = f"{eco_name}:{release}"
            yield OsvQuery(
                version=version,
                package=OsvPackage(name=name, ecosystem=ecosystem_str),
            )


async def generate_vuln_report_payloads(
    repository_version_pk: str,
) -> AsyncGenerator[VulnReportPayload, None]:
    """Generator of OSV query dicts for rpm.packages in a repository version."""
    repo_version: RepositoryVersion = await RepositoryVersion.objects.select_related(
        "repository"
    ).aget(pk=repository_version_pk)
    repo: Any = repo_version.repository
    labels: dict[str, str] = dict(repo.pulp_labels)

    ecosystems: list[dict] = OsvConfigSerializer.from_labels(labels).validated_data["config"]

    pkg_pks = repo_version.content.filter(pulp_type=Package.get_pulp_type()).values("pk")
    async for pkg in (
        Package.objects.only("pk", "name", "version").filter(pk__in=pkg_pks).aiterator()
    ):
        for osv_data in build_osv_queries(str(pkg.name), str(pkg.version), ecosystems):
            yield VulnReportPayload(
                version=osv_data["version"],
                package=osv_data["package"],
                content=pkg,
                repo_version=repo_version,
            )
