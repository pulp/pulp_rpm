"""Unit tests for ChildContentResolver in the copy task."""

import time
import uuid
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from django.db import connection
from django.db.models import Q
from django.utils import timezone

from pulpcore.plugin.models import Content
from pulpcore.plugin.util import get_domain_pk

from pulp_rpm.app.models import (
    Package,
    PackageGroup,
    RpmRepository,
)
from pulp_rpm.app.tasks.copy import ChildContentResolver

PG_PARAM_LIMIT = 65535
RPM_PACKAGE_COLS = 31
BATCH_SIZE = PG_PARAM_LIMIT // RPM_PACKAGE_COLS


def _bulk_create_packages(names):
    """Bulk-create packages via two-step MTI insert. Skips if enough already exist."""
    # This is not pretty but boy... it's FAST
    domain_pk = get_domain_pk()
    pulp_type = Package.get_pulp_type()
    now = timezone.now()
    pks = [uuid.uuid4() for _ in names]
    with connection.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO core_content "
            "(pulp_id, pulp_type, pulp_domain_id, "
            "pulp_created, pulp_last_updated, timestamp_of_interest, pulp_labels) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            [(pk, pulp_type, domain_pk, now, now, now, "") for pk in pks],
        )
        # fmt: off
        cursor.executemany(
            "INSERT INTO rpm_package "
            "(content_ptr_id, name, epoch, version, release, arch, "
            '"pkgId", checksum_type, '
            "summary, description, url, "
            "location_base, location_href, "
            "rpm_buildhost, rpm_group, rpm_license, rpm_packager, rpm_sourcerpm, rpm_vendor, "
            "changelogs, files, "
            "requires, provides, conflicts, obsoletes, "
            "suggests, enhances, recommends, supplements, "
            "is_modular, _pulp_domain_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, "
            "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
            "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            [
                (pk, name, "0", "1.0", "1", "noarch", f"fakedigest-{name}", "sha256",
                 "", "", "", "", "", "", "", "", "", "", "",
                 "[]", "[]", "[]", "[]", "[]", "[]", "[]", "[]", "[]", "[]",
                 False, domain_pk)
                for pk, name in zip(pks, names)
            ],
        )
        # fmt: on
    return pks


def _make_repo_version(content_pks, repo_name=None):
    """Create a minimal RpmRepository + RepositoryVersion with the given content PKs."""
    repo_name = repo_name or str(uuid.uuid4())
    repo, created = RpmRepository.objects.get_or_create(name=repo_name)
    with repo.new_version() as version:
        for start in range(0, len(content_pks), BATCH_SIZE):
            version.add_content(
                Content.objects.filter(pk__in=content_pks[start : start + BATCH_SIZE])
            )
    return repo.latest_version()


def _create_package_group(name, *, packages):
    group, _ = PackageGroup.objects.get_or_create(
        id=name,
        defaults={
            "name": name,
            "digest": uuid.uuid4().hex,
            "packages": [{"name": n} for n in packages],
        },
    )
    return group.pk


@contextmanager
def timer(label):
    start = time.perf_counter()
    yield
    print(f"[timing] {label}: {time.perf_counter() - start:.1f}s")


def get_param_count(qs):
    """Return the number of bind parameters in the compiled queryset."""
    _, params = qs.query.sql_with_params()
    return len(params)


def assert_param_limit_raises():
    """Sanity check that is does raise violation of the limit."""
    connection.ensure_connection()
    PARAMS_COUNT = PG_PARAM_LIMIT + 50
    placeholders = ", ".join(["%s"] * PARAMS_COUNT)
    with pytest.raises(Exception, match="65535"):
        connection.cursor().execute(f"SELECT 1 IN ({placeholders})", list(range(PARAMS_COUNT)))


def _safe_in_fake(field_name, values):
    """Naive __in that hits the 65k param limit. Used to prove the fix works."""
    return Q(**{f"{field_name}__in": values})


def _safe_in_raw(field_name, values):
    """WHERE x IN (SELECT unnest(%s::type[]))  -- RawSQL alternative."""
    from django.db.models.expressions import RawSQL

    if not isinstance(values, (list, set, tuple, frozenset)):
        return Q(**{f"{field_name}__in": values})
    vals = list(values)
    cast = "uuid[]" if (vals and isinstance(vals[0], uuid.UUID)) else "text[]"
    return Q(**{f"{field_name}__in": RawSQL(f"SELECT unnest(%s::{cast})", [vals])})


class TestChildContentResolver:
    @pytest.mark.django_db
    def test_resolve_handles_more_than_65k(self):
        """ChildContentResolver.resolve() with a group referencing >65k packages."""
        assert_param_limit_raises()
        package_names = [f"pkg-{i}" for i in range(int(PG_PARAM_LIMIT * 1.2))]

        with timer("create packages and group"):
            package_pks = _bulk_create_packages(package_names)
            group_pk = _create_package_group("big-group", packages=package_names)
            all_pks = package_pks + [group_pk]
            assert len(all_pks) > PG_PARAM_LIMIT

        with timer("create repo version"):
            src_version = _make_repo_version(all_pks, repo_name="big-group-repo")

        with timer("resolve"):
            content_filter = Q(pk__in=[group_pk])
            resolver = ChildContentResolver(content_filter, src_version)
            result = resolver.resolve()
            assert get_param_count(result) < 10

        with patch("pulp_rpm.app.tasks.copy.safe_in", _safe_in_fake):
            content_filter = Q(pk__in=[group_pk])
            resolver = ChildContentResolver(content_filter, src_version)
            with pytest.raises(Exception, match="65535"):
                resolver.resolve()
