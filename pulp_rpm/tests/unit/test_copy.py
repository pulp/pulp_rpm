"""Unit tests for find_children_of_content in the copy task."""

import hashlib
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import connections
from django.db.models import Q

from pulpcore.app.models import Content, RepositoryVersion

from pulp_rpm.app.models import (
    Package,
    PackageCategory,
    PackageGroup,
    RpmRepository,
)
from pulp_rpm.app.tasks.copy import find_children_of_content

PG_PARAM_LIMIT = 65535


class Stopwatch:
    def __init__(self):
        self._last = time.perf_counter()

    def lap(self, label):
        now = time.perf_counter()
        print(f"[timing] {label}: {now - self._last:.1f}s")
        self._last = now


def _ensure_packages(count, workers=8):
    """Return a queryset of `count` packages, creating only the missing ones."""
    existing = set(
        Package.objects.filter(pkgId__startswith="fakedigest-").values_list("pkgId", flat=True)
    )
    needed = [i for i in range(count) if f"fakedigest-{i}" not in existing]

    if needed:

        def _create_chunk(chunk):
            try:
                for i in chunk:
                    Package.objects.create(
                        name=f"pkg-{i}",
                        epoch="0",
                        version="1.0",
                        release="1",
                        arch="noarch",
                        pkgId=f"fakedigest-{i}",
                        checksum_type="sha256",
                    )
            finally:
                connections.close_all()

        chunk_size = max(1, len(needed) // workers)
        chunks = [needed[i : i + chunk_size] for i in range(0, len(needed), chunk_size)]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(_create_chunk, chunks))

    return Package.objects.filter(pkgId__startswith="fakedigest-")


def _make_repo_version(content_pks, repo_name=None):
    """Create a minimal RpmRepository + RepositoryVersion with the given content PKs."""
    repo_name = repo_name or str(uuid.uuid4())
    repo, _ = RpmRepository.objects.get_or_create(name=repo_name)
    version = repo.versions.filter(number=1).first()
    if not version:
        version = RepositoryVersion(repository=repo, number=1, complete=True)
        version.save()
    version.content_ids = list(content_pks)
    version.save(update_fields=["content_ids"])
    return version


def _make_package(name, version="1.0", release="1", arch="noarch", suffix=""):
    return Package.objects.create(
        name=name,
        epoch="0",
        version=version,
        release=release,
        arch=arch,
        pkgId=hashlib.sha256(f"{name}-{version}-{release}-{suffix}".encode()).hexdigest(),
        checksum_type="sha256",
    )


@pytest.mark.django_db
def test_find_children_category_to_group_to_package():
    """Category -> Group -> Package chain resolves correctly."""
    pkg_a = _make_package("pkg-a", suffix="a")
    pkg_b = _make_package("pkg-b", suffix="b")
    pkg_unrelated = _make_package("pkg-unrelated", suffix="u")

    group = PackageGroup.objects.create(
        id="my-group",
        name="my-group",
        digest=uuid.uuid4().hex,
        packages=[{"name": "pkg-a"}, {"name": "pkg-b"}],
    )

    category = PackageCategory.objects.create(
        id="my-category",
        name="my-category",
        digest=uuid.uuid4().hex,
        group_ids=[{"name": "my-group"}],
    )

    all_pks = [pkg_a.pk, pkg_b.pk, pkg_unrelated.pk, group.pk, category.pk]
    repo_version = _make_repo_version(all_pks)

    content_filter = Q(pk__in=[category.pk])
    children = find_children_of_content(content_filter, repo_version)

    children_pks = set(children.values_list("pk", flat=True))
    assert group.pk in children_pks
    assert pkg_a.pk in children_pks
    assert pkg_b.pk in children_pks
    assert pkg_unrelated.pk not in children_pks


@pytest.mark.django_db
def test_server_side_binding_active():
    """Sanity check: the fixture actually enables server-side binding."""
    from django.db import connection

    connection.ensure_connection()
    cursor = connection.create_cursor()
    assert type(cursor).__name__ == "ServerBindingCursor"


@pytest.mark.django_db
def test_find_children_exceeds_param_limit():
    """find_children_of_content with a group referencing >65k packages."""
    from django.db import connection

    connection.ensure_connection()
    cursor = connection.create_cursor()
    assert type(cursor).__name__ == "ServerBindingCursor"
    sw = Stopwatch()

    packages = _ensure_packages(PG_PARAM_LIMIT + 1)
    sw.lap(f"ensure packages")

    package_names = list(packages.values_list("name", flat=True))
    group, _ = PackageGroup.objects.get_or_create(
        id="big-group",
        defaults={
            "name": "big-group",
            "digest": "fakedigest-big-group",
            "packages": [{"name": n} for n in package_names],
        },
    )
    sw.lap("ensure group")

    all_pks = list(packages.values_list("pk", flat=True)) + [group.pk]
    src_version = _make_repo_version(all_pks, repo_name="big-group-repo")
    sw.lap("ensure repo version")

    content_filter = Q(pk__in=[group.pk])
    children = find_children_of_content(content_filter, src_version)
    result = list(children)
    sw.lap("find_children_of_content")

    assert len(result) > 0
