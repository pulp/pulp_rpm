import dataclasses
import uuid

import pytest

from pulpcore.plugin.models import Content, Domain

from pulp_rpm.app.models import Modulemd, Package
from pulp_rpm.app.models.repository import RpmRepository
from pulp_rpm.tests.shared_utils import MetaPackage, Nevra


def _model_from_metapackage(domain, pkg: MetaPackage) -> Package:
    """Create a MetaPackage from a pulp model Package."""
    BLANK_FIELDS = {
        "checksum_type": "sha256",
        "summary": "",
        "description": "",
        "url": "",
        "location_base": "",
        "rpm_buildhost": "",
        "rpm_group": "",
        "rpm_license": "",
        "rpm_packager": "",
        "rpm_sourcerpm": "",
        "rpm_vendor": "",
    }
    nevra = pkg.nevra
    return Package.objects.create(
        name=nevra.name,
        epoch=str(nevra.epoch),
        version=nevra.version,
        release=nevra.release,
        arch=nevra.arch,
        location_href=f"{nevra.to_nvra()}.rpm",
        time_build=pkg.time_build or None,
        pkgId=pkg.digest or str(uuid.uuid4()),
        pulp_type="rpm.package",
        _pulp_domain=domain,
        **BLANK_FIELDS,
    )


def _metapackages_from_version(version) -> list[MetaPackage]:
    """Build a list of MetaPackages representing content in a RepositoryVersion."""
    return [
        MetaPackage(
            Nevra(p.name, int(p.epoch), p.version, p.release, p.arch),
            time_build=p.time_build or 0,
            digest=p.pkgId,
        )
        for p in Package.objects.filter(pk__in=version.content).order_by("name")
    ]


WALRUS = MetaPackage(Nevra("walrus", 0, "5.21", "1.fc25", "x86_64"))
PENGUIN = MetaPackage(Nevra("penguin", 0, "1.0", "1.fc25", "x86_64"))


@dataclasses.dataclass
class DedupCase:
    id: str
    description: str
    add_packages1: list[MetaPackage]
    expected1: list[MetaPackage]
    add_packages2: list[MetaPackage] | None = None
    expected2: list[MetaPackage] | None = None
    compare_digest: bool = False


CASES = [
    DedupCase(
        id="keeps-highest-epoch",
        description="If two packages with different epochs are added, the one with higher epoch wins.",
        add_packages1=[WALRUS.replace(epoch=1), WALRUS.replace(epoch=5)],
        expected1=[WALRUS.replace(epoch=5)],
    ),
    DedupCase(
        id="no-duplicates-unchanged",
        description="Packages with different names are not duplicates and remain unchanged.",
        add_packages1=[WALRUS.replace(epoch=1), PENGUIN.replace(epoch=1)],
        expected1=[PENGUIN.replace(epoch=1), WALRUS.replace(epoch=1)],
    ),
    DedupCase(
        id="multiple-groups-deduped-independently",
        description="Multiple packages with duplicates are deduped independently by NEVRA.",
        add_packages1=[
            WALRUS.replace(epoch=1),
            WALRUS.replace(epoch=3),
            PENGUIN.replace(epoch=0),
            PENGUIN.replace(epoch=2),
        ],
        expected1=[PENGUIN.replace(epoch=2), WALRUS.replace(epoch=3)],
    ),
    DedupCase(
        id="incoming-higher-replaces-existing",
        description="Incoming package with higher epoch replaces existing package with same NVRA.",
        add_packages1=[WALRUS.replace(epoch=1)],
        expected1=[WALRUS.replace(epoch=1)],
        add_packages2=[WALRUS.replace(epoch=5)],
        expected2=[WALRUS.replace(epoch=5)],
    ),
    DedupCase(
        id="incoming-lower-keeps-existing",
        description="Incoming package with lower epoch is ignored, existing package is retained.",
        add_packages1=[WALRUS.replace(epoch=5)],
        expected1=[WALRUS.replace(epoch=5)],
        add_packages2=[WALRUS.replace(epoch=1)],
        expected2=[WALRUS.replace(epoch=5)],
    ),
    DedupCase(
        id="incoming-into-multiple-groups",
        description="When adding multiple packages, each competes independently with existing packages.",
        add_packages1=[WALRUS.replace(epoch=3), PENGUIN.replace(epoch=2)],
        expected1=[PENGUIN.replace(epoch=2), WALRUS.replace(epoch=3)],
        add_packages2=[WALRUS.replace(epoch=1), PENGUIN.replace(epoch=4)],
        expected2=[PENGUIN.replace(epoch=4), WALRUS.replace(epoch=3)],
    ),
    DedupCase(
        id="incoming-same-epoch-higher-build-time-wins",
        description="When epochs are equal, the package with the higher build time wins.",
        add_packages1=[
            WALRUS.replace(epoch=1, time_build=1000),
            WALRUS.replace(epoch=1, time_build=2000),
        ],
        expected1=[WALRUS.replace(epoch=1, time_build=2000)],
    ),
    DedupCase(
        id="incoming-same-epoch-higher-build-time-wins-reversed",
        description="Build time tiebreaker is order-independent.",
        add_packages1=[
            WALRUS.replace(epoch=1, time_build=2000),
            WALRUS.replace(epoch=1, time_build=1000),
        ],
        expected1=[WALRUS.replace(epoch=1, time_build=2000)],
    ),
    DedupCase(
        id="known-build-time-wins-over-missing",
        description="A package with a known build time wins over one without a build time.",
        add_packages1=[
            WALRUS.replace(epoch=1, time_build=0, digest="zzz"),
            WALRUS.replace(epoch=1, time_build=1000, digest="aaa"),
        ],
        expected1=[WALRUS.replace(epoch=1, time_build=1000, digest="aaa")],
        compare_digest=True,
    ),
    DedupCase(
        id="all-tied-highest-pkgid-wins",
        description="When epoch and build time are equal, the package with highest pkgId wins.",
        add_packages1=[
            WALRUS.replace(epoch=1, time_build=1000, digest="aaa"),
            WALRUS.replace(epoch=1, time_build=1000, digest="zzz"),
        ],
        expected1=[WALRUS.replace(epoch=1, time_build=1000, digest="zzz")],
        compare_digest=True,
    ),
    DedupCase(
        id="incoming-same-epoch-keeps-incoming",
        description=(
            "On epoch conflict, incoming package takes precedence over existing regardless of build_time. "
            "Here the incoming package has higher build_time."
        ),
        add_packages1=[
            WALRUS.replace(epoch=1, time_build=1000),
        ],
        expected1=[WALRUS.replace(epoch=1, time_build=1000)],
        add_packages2=[
            WALRUS.replace(epoch=1, time_build=2000),
        ],
        expected2=[WALRUS.replace(epoch=1, time_build=2000)],
    ),
    DedupCase(
        id="incoming-same-epoch-keeps-incoming-reversed",
        description=(
            "On epoch conflict, incoming package takes precedence over existing regardless of build_time. "
            "Here the incoming package has lower build_time."
        ),
        add_packages1=[
            WALRUS.replace(epoch=1, time_build=2000),
        ],
        expected1=[WALRUS.replace(epoch=1, time_build=2000)],
        add_packages2=[
            WALRUS.replace(epoch=1, time_build=1000),
        ],
        expected2=[WALRUS.replace(epoch=1, time_build=1000)],
    ),
]


@pytest.mark.django_db
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_finalize_new_version_dedup(case: DedupCase):
    domain, _ = Domain.objects.get_or_create(name="default")

    pkgs1 = [_model_from_metapackage(domain, pkg) for pkg in case.add_packages1]
    repo = RpmRepository.objects.create(name="test-repo", pulp_domain=domain)
    with repo.new_version() as version:
        version.add_content(Content.objects.filter(pk__in=[p.pk for p in pkgs1]))

    version.refresh_from_db()
    ign = () if case.compare_digest else ("digest",)
    assert [p.ignore(*ign) for p in _metapackages_from_version(version)] == [
        p.ignore(*ign) for p in case.expected1
    ]

    if case.add_packages2 is None:
        return

    pkgs2 = [_model_from_metapackage(domain, pkg) for pkg in case.add_packages2]
    with repo.new_version() as version:
        version.add_content(Content.objects.filter(pk__in=[p.pk for p in pkgs2]))

    latest = repo.latest_version()
    assert [p.ignore(*ign) for p in _metapackages_from_version(latest)] == [
        p.ignore(*ign) for p in case.expected2
    ]


@pytest.mark.django_db
def test_resigned_modular_package_survives_removing_another_stream():
    """Keep the selected RPM when a remaining module links to its re-signed twin.

    Deduplication keeps one content ID for the shared NEVRA. Removing the module
    linked to that ID must not remove the RPM needed by the other module.
    """
    domain, _ = Domain.objects.get_or_create(name="default")
    older = _model_from_metapackage(domain, WALRUS.replace(digest="aaa"))
    winner = _model_from_metapackage(domain, WALRUS.replace(digest="fff"))
    modules = []
    for stream, package in (("one", winner), ("two", older)):
        module = Modulemd.objects.create(
            name="walrus",
            stream=stream,
            version="1",
            context="context",
            arch="x86_64",
            artifacts=["walrus-0:5.21-1.fc25.x86_64"],
            description="",
            digest=uuid.uuid4().hex,
            snippet="",
            _pulp_domain=domain,
        )
        module.packages.add(package)
        modules.append(module)

    repo = RpmRepository.objects.create(name="modular-package-repo", pulp_domain=domain)
    with repo.new_version() as version:
        version.add_content(
            Content.objects.filter(pk__in=[older.pk, winner.pk, *[m.pk for m in modules]])
        )
    assert set(
        Package.objects.filter(pk__in=repo.latest_version().content).values_list("pk", flat=True)
    ) == {winner.pk}

    with repo.new_version() as version:
        version.remove_content(Content.objects.filter(pk=modules[0].pk))

    assert set(
        Modulemd.objects.filter(pk__in=repo.latest_version().content).values_list("pk", flat=True)
    ) == {modules[1].pk}
    assert set(
        Package.objects.filter(pk__in=repo.latest_version().content).values_list("pk", flat=True)
    ) == {winner.pk}
