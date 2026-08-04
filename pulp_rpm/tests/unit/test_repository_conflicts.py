import dataclasses
import uuid

import pytest

from pulpcore.plugin.models import Content, Domain

from pulp_rpm.app.models import Package
from pulp_rpm.app.models.repository import RpmRepository
from pulp_rpm.tests.functional.utils import MetaPackage, Nevra

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


def _create_package(domain, pkg):
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


def _get_version_packages(version):
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
    add_packages1: list[MetaPackage]
    expected1: list[MetaPackage]
    add_packages2: list[MetaPackage] | None = None
    expected2: list[MetaPackage] | None = None
    compare_digest: bool = False


CASES = [
    DedupCase(
        id="keeps-highest-epoch",
        add_packages1=[WALRUS.replace(epoch=1), WALRUS.replace(epoch=5)],
        expected1=[WALRUS.replace(epoch=5)],
    ),
    DedupCase(
        id="no-duplicates-unchanged",
        add_packages1=[WALRUS.replace(epoch=1), PENGUIN.replace(epoch=1)],
        expected1=[PENGUIN.replace(epoch=1), WALRUS.replace(epoch=1)],
    ),
    DedupCase(
        id="multiple-groups-deduped-independently",
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
        add_packages1=[WALRUS.replace(epoch=1)],
        expected1=[WALRUS.replace(epoch=1)],
        add_packages2=[WALRUS.replace(epoch=5)],
        expected2=[WALRUS.replace(epoch=5)],
    ),
    DedupCase(
        id="incoming-lower-keeps-existing",
        add_packages1=[WALRUS.replace(epoch=5)],
        expected1=[WALRUS.replace(epoch=5)],
        add_packages2=[WALRUS.replace(epoch=1)],
        expected2=[WALRUS.replace(epoch=5)],
    ),
    DedupCase(
        id="incoming-into-multiple-groups",
        add_packages1=[WALRUS.replace(epoch=3), PENGUIN.replace(epoch=2)],
        expected1=[PENGUIN.replace(epoch=2), WALRUS.replace(epoch=3)],
        add_packages2=[WALRUS.replace(epoch=1), PENGUIN.replace(epoch=4)],
        expected2=[PENGUIN.replace(epoch=4), WALRUS.replace(epoch=3)],
    ),
    DedupCase(
        id="incoming-same-epoch-higher-build-time-wins",
        add_packages1=[
            WALRUS.replace(epoch=1, time_build=1000),
            WALRUS.replace(epoch=1, time_build=2000),
        ],
        expected1=[WALRUS.replace(epoch=1, time_build=2000)],
    ),
    DedupCase(
        id="incoming-same-epoch-higher-build-time-wins-reversed",
        add_packages1=[
            WALRUS.replace(epoch=1, time_build=2000),
            WALRUS.replace(epoch=1, time_build=1000),
        ],
        expected1=[WALRUS.replace(epoch=1, time_build=2000)],
    ),
    DedupCase(
        id="all-tied-highest-pkgid-wins",
        add_packages1=[
            WALRUS.replace(epoch=1, time_build=1000, digest="aaa"),
            WALRUS.replace(epoch=1, time_build=1000, digest="zzz"),
        ],
        expected1=[WALRUS.replace(epoch=1, time_build=1000, digest="zzz")],
        compare_digest=True,
    ),
    DedupCase(
        id="incoming-same-epoch-keeps-incoming",
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

    pkgs1 = [_create_package(domain, pkg) for pkg in case.add_packages1]
    repo = RpmRepository.objects.create(name="test-repo", pulp_domain=domain)
    with repo.new_version() as version:
        version.add_content(Content.objects.filter(pk__in=[p.pk for p in pkgs1]))

    version.refresh_from_db()
    ign = () if case.compare_digest else ("digest",)
    assert [p.ignore(*ign) for p in _get_version_packages(version)] == [
        p.ignore(*ign) for p in case.expected1
    ]

    if case.add_packages2 is None:
        return

    pkgs2 = [_create_package(domain, pkg) for pkg in case.add_packages2]
    with repo.new_version() as version:
        version.add_content(Content.objects.filter(pk__in=[p.pk for p in pkgs2]))

    latest = repo.latest_version()
    assert [p.ignore(*ign) for p in _get_version_packages(latest)] == [
        p.ignore(*ign) for p in case.expected2
    ]
