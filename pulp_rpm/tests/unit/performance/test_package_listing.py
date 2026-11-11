import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from pulpcore.plugin.models import VulnerabilityReport

from pulp_rpm.app.models import Package
from pulp_rpm.app.serializers.package import PackageSerializer
from pulp_rpm.app.viewsets.package import PackageViewSet


def _create_package(index):
    return Package.objects.create(
        name=f"package-{index}",
        epoch="0",
        version="1.0",
        release="1",
        arch="noarch",
        pkgId=f"digest-{index}",
        checksum_type="sha256",
    )


def _list_packages(packages):
    request = Request(APIRequestFactory().get("/pulp/api/v3/content/rpm/packages/"))
    ids = [package.pk for package in packages]
    with CaptureQueriesContext(connection) as queries:
        queryset = PackageViewSet.queryset.filter(pk__in=ids).order_by("pk")
        data = PackageSerializer(queryset, many=True, context={"request": request}).data
    return data, queries


@pytest.mark.django_db
def test_package_listing_query_count_does_not_grow_with_page_size():
    packages = [_create_package(i) for i in range(10)]
    small_data, small_queries = _list_packages(packages[:2])
    large_data, large_queries = _list_packages(packages)

    assert len(small_data) == 2
    assert len(large_data) == 10

    assert len(small_queries) == len(large_queries), [query["sql"] for query in large_queries]


@pytest.mark.django_db
def test_package_listing_domain_lookups_do_not_grow_with_page_size():
    packages = [_create_package(i) for i in range(10)]
    VulnerabilityReport.objects.create(
        content_id=packages[0].pk,
        pulp_domain_id=packages[0].pulp_domain_id,
        vulns=[],
    )

    def domain_queries(selected_packages):
        ids = [package.pk for package in selected_packages]
        with CaptureQueriesContext(connection) as queries:
            queryset = PackageViewSet.queryset.filter(pk__in=ids)
            for package in queryset:
                package.pulp_domain.name
                try:
                    package.core_vulnerabilityreport.pulp_domain.name
                except VulnerabilityReport.DoesNotExist:
                    pass
        return queries

    small_queries = domain_queries(packages[:2])
    large_queries = domain_queries(packages)
    assert len(small_queries) == len(large_queries), [query["sql"] for query in large_queries]


@pytest.mark.django_db
def test_package_listing_prefetches_report_identifier_only():
    packages = [_create_package(i) for i in range(2)]
    report = VulnerabilityReport.objects.create(
        content_id=packages[0].pk,
        pulp_domain_id=packages[0].pulp_domain_id,
        vulns=[],
    )

    data, queries = _list_packages(packages)
    report_hrefs = [item["vuln_report"] for item in data]
    assert sum(href is not None for href in report_hrefs) == 1
    assert str(report.pk) in next(href for href in report_hrefs if href)

    report_queries = [
        query["sql"] for query in queries if 'FROM "core_vulnerabilityreport"' in query["sql"]
    ]
    assert len(report_queries) == 1
    assert '"vulns"' not in report_queries[0]
