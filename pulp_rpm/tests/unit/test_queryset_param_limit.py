"""Reproduce PostgreSQL's 65535 parameter limit when unioning large pk__in querysets."""

import uuid

import pytest

from pulp_rpm.app.models import Package

PG_PARAM_LIMIT = 65535


@pytest.mark.django_db(transaction=True)
def test_union_iterator_exceeds_param_limit(server_side_binding):
    """Two querysets each with ~35k pk__in params blow up on .iterator() after .union()."""
    fake_pks = [uuid.uuid4() for _ in range(PG_PARAM_LIMIT // 2 + 1)]
    fake_pks_2 = [uuid.uuid4() for _ in range(PG_PARAM_LIMIT // 2 + 1)]

    qs_a = Package.objects.filter(pk__in=fake_pks)
    qs_b = Package.objects.filter(pk__in=fake_pks_2)
    combined = qs_a.union(qs_b)

    _, params = combined.query.sql_with_params()
    assert len(params) > PG_PARAM_LIMIT

    with pytest.raises(Exception, match=str(PG_PARAM_LIMIT)):
        list(combined.iterator())
