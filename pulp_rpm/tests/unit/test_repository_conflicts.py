import uuid

import pytest

from pulpcore.plugin.models import Content

from pulp_rpm.app.models import Modulemd, Package, RpmRepository


def make_package(pkg_id, *, location="Packages/g/galera-1-1.x86_64.rpm", epoch="0", build=100):
    return Package.objects.create(
        name="galera",
        epoch=epoch,
        version="1",
        release="1",
        arch="x86_64",
        location_href=location,
        checksum_type="sha256",
        pkgId=pkg_id,
        time_build=build,
    )


def package_ids(version):
    return set(Package.objects.filter(pk__in=version.content).values_list("pk", flat=True))


@pytest.mark.django_db
def test_packages_with_same_repo_key_added_in_one_version():
    older = make_package("aaa", build=100)
    newer = make_package("bbb", build=200)
    other_location = make_package("ccc", location="other/galera-1-1.x86_64.rpm")
    other_epoch = make_package("ddd", epoch="1")
    repo = RpmRepository.objects.create(name="resigned-packages")

    with repo.new_version() as version:
        version.add_content(
            Content.objects.filter(pk__in=[older.pk, newer.pk, other_location.pk, other_epoch.pk])
        )

    assert package_ids(repo.latest_version()) == {newer.pk, other_location.pk, other_epoch.pk}


@pytest.mark.django_db
def test_package_with_same_repo_key_replaces_existing_version():
    older = make_package("aaa", build=200)
    newer = make_package("bbb", build=100)
    repo = RpmRepository.objects.create(name="resigned-package-update")

    with repo.new_version() as version:
        version.add_content(Content.objects.filter(pk=older.pk))
    with repo.new_version() as version:
        version.add_content(Content.objects.filter(pk=newer.pk))

    assert package_ids(repo.latest_version()) == {newer.pk}


@pytest.mark.django_db
def test_packages_with_same_build_time_use_checksum_tiebreaker():
    lower = make_package("aaa")
    higher = make_package("zzz")
    repo = RpmRepository.objects.create(name="resigned-package-tie")

    with repo.new_version() as version:
        version.add_content(Content.objects.filter(pk__in=[lower.pk, higher.pk]))

    assert package_ids(repo.latest_version()) == {higher.pk}


@pytest.mark.django_db
def test_package_with_build_time_wins_over_missing_build_time():
    missing = make_package("zzz", build=None)
    built = make_package("aaa", build=100)
    repo = RpmRepository.objects.create(name="package-build-time")

    with repo.new_version() as version:
        version.add_content(Content.objects.filter(pk__in=[missing.pk, built.pk]))

    assert package_ids(repo.latest_version()) == {built.pk}


@pytest.mark.django_db
def test_resigned_modular_package_survives_removing_another_stream():
    """Keep the selected RPM when a remaining module links to its re-signed twin.

    Deduplication keeps one content ID for the shared NEVRA. Removing the module
    linked to that ID must not remove the RPM needed by the other module.
    """
    older = make_package("aaa")
    winner = make_package("fff")
    modules = []
    for stream, package in (("one", winner), ("two", older)):
        module = Modulemd.objects.create(
            name="galera",
            stream=stream,
            version="1",
            context="context",
            arch="x86_64",
            artifacts=["galera-0:1-1.x86_64"],
            description="",
            digest=uuid.uuid4().hex,
            snippet="",
        )
        module.packages.add(package)
        modules.append(module)

    repo = RpmRepository.objects.create(name="modular-package-repo")
    with repo.new_version() as version:
        version.add_content(
            Content.objects.filter(pk__in=[older.pk, winner.pk, *[m.pk for m in modules]])
        )
    assert package_ids(repo.latest_version()) == {winner.pk}

    with repo.new_version() as version:
        version.remove_content(Content.objects.filter(pk=modules[0].pk))

    assert set(
        Modulemd.objects.filter(pk__in=repo.latest_version().content).values_list("pk", flat=True)
    ) == {modules[1].pk}
    assert package_ids(repo.latest_version()) == {winner.pk}
