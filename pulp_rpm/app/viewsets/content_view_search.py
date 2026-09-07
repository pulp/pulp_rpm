"""
Nested, read-only search endpoints exposed under a ContentView, e.g.
``content-views/{content_view_pk}/search/rpm/packages/``.

Each viewset here resolves the parent ContentView's Distributions (across whatever domains they
live in) to their current RepositoryVersions via ``pulpcore.plugin.util.resolve_content_view_distributions``
/``group_versions_by_domain``, then queries RPM content across those versions -- either with the
generic ``scatter_gather`` helper (for the two paginated, offset/limit endpoints) or a lighter
Python-side merge (for the three typeahead-style endpoints, which never compute a total count,
matching tang's existing behavior).
"""

from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response

from pulpcore.plugin.util import (
    group_versions_by_domain,
    resolve_content_view_distributions,
    scatter_gather,
    with_domain,
)
from pulpcore.plugin.viewsets import ContentViewViewSet, NamedModelViewSet

from pulp_rpm.app.models import Modulemd, Package, PackageEnvironment, PackageGroup, UpdateRecord
from pulp_rpm.app.models.advisory import UpdateReference
from pulp_rpm.app.serializers import (
    ContentViewErrataSerializer,
    ContentViewModuleStreamSerializer,
    ContentViewPackageEnvironmentSerializer,
    ContentViewPackageGroupSerializer,
    ContentViewPackageSerializer,
)

KNOWN_ERRATA_TYPES = {"security", "bugfix", "enhancement", "newpackage"}
KNOWN_ERRATA_SEVERITIES = {"critical", "important", "moderate", "low", "none"}
ERRATA_SORT_FIELDS = {"id", "updated_date", "issued_date", "severity", "type", "title"}
MODULE_STREAM_SORT_FIELDS = {"name", "stream", "version", "context", "arch"}
MODULE_STREAMS_HARD_CAP = 5000


def content_for_versions(model, versions):
    """Combine the content of one or more RepositoryVersions (all in the same domain)."""
    if not versions:
        return model.objects.none()
    if len(versions) == 1:
        return versions[0].get_content(model.objects)
    pks = set()
    for version in versions:
        pks.update(version.content_ids)
    return model.objects.filter(pk__in=pks)


def _int_param(request, name, default, minimum=0, maximum=None):
    try:
        value = int(request.query_params[name])
    except (KeyError, ValueError, TypeError):
        return default
    value = max(value, minimum)
    if maximum is not None:
        value = min(value, maximum)
    return value


def _list_param(request, name):
    value = request.query_params.get(name)
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def _catch_all_filter(field, requested, known):
    """Build a ``Q`` for a type/severity-style filter with an "other" catch-all bucket."""
    known_requested = [v for v in requested if v in known]
    other_requested = any(v not in known for v in requested)
    condition = Q(**{f"{field}__in": known_requested}) if known_requested else Q(pk__in=[])
    if other_requested:
        condition = condition | ~Q(**{f"{field}__in": known})
    return condition


def paginated_response(request, results, count, limit, offset):
    paginator = LimitOffsetPagination()
    paginator.request = request
    paginator.limit = limit
    paginator.offset = offset
    paginator.count = count
    return paginator.get_paginated_response(results)


def _union_package_lists(existing, new):
    seen = {pkg.get("name") for pkg in existing}
    merged = list(existing)
    for pkg in new:
        if pkg.get("name") not in seen:
            seen.add(pkg.get("name"))
            merged.append(pkg)
    return merged


class ContentViewSearchViewSet(NamedModelViewSet):
    """Shared plumbing for all ``content-views/{content_view_pk}/search/rpm/...`` viewsets."""

    parent_viewset = ContentViewViewSet
    parent_lookup_kwargs = {"content_view_pk": "content_view__pk"}

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {"action": ["list"], "principal": "authenticated", "effect": "allow"},
        ],
    }

    def _get_content_view(self):
        """
        Re-resolve the parent ContentView through ContentViewViewSet's own RBAC-scoped queryset.

        The base ``initial()``/``get_parent_field_and_object()`` machinery only checks that a
        ContentView with this pk exists at all (unfiltered), so we deliberately re-check here
        against the permission-scoped queryset instead of trusting that ambient check.
        """
        parent_viewset = ContentViewViewSet()
        parent_viewset.request = self.request
        parent_viewset.kwargs = {}
        parent_viewset.format_kwarg = None
        scoped_queryset = parent_viewset.get_queryset()
        return get_object_or_404(scoped_queryset, pk=self.kwargs["content_view_pk"])

    def _versions_by_domain(self):
        content_view = self._get_content_view()
        resolutions = resolve_content_view_distributions(content_view, self.request.user)
        return group_versions_by_domain(resolutions)


class RpmContentViewPackageSearchViewSet(ContentViewSearchViewSet):
    """Typeahead package search: prefix match, deduplicated by name."""

    endpoint_name = "search/rpm/packages"
    queryset = Package.objects.none()
    serializer_class = ContentViewPackageSerializer

    def list(self, request, *args, **kwargs):
        versions_by_domain = self._versions_by_domain()
        search = request.query_params.get("search", "")
        limit = _int_param(request, "limit", default=25, minimum=1, maximum=100)

        def build_queryset(versions):
            qs = content_for_versions(Package, versions)
            if search:
                qs = qs.filter(name__istartswith=search)
            return qs.order_by("name").distinct("name")

        rows = []
        seen_names = set()
        for domain, versions in versions_by_domain.items():
            with with_domain(domain):
                for package in build_queryset(versions)[: limit * 5]:
                    if package.name in seen_names:
                        continue
                    seen_names.add(package.name)
                    rows.append(package)
        rows.sort(key=lambda p: p.name)
        page = rows[:limit]
        serializer = self.get_serializer(page, many=True)
        return Response({"results": serializer.data})


class RpmContentViewPackageGroupSearchViewSet(ContentViewSearchViewSet):
    """
    Typeahead package-group search: substring match, with the ``packages`` list of same-keyed
    groups found in multiple domains/repository versions unioned together.
    """

    endpoint_name = "search/rpm/package-groups"
    queryset = PackageGroup.objects.none()
    serializer_class = ContentViewPackageGroupSerializer

    def list(self, request, *args, **kwargs):
        versions_by_domain = self._versions_by_domain()
        search = request.query_params.get("search", "")
        limit = _int_param(request, "limit", default=25, minimum=1, maximum=100)

        def build_queryset(versions):
            qs = content_for_versions(PackageGroup, versions)
            if search:
                qs = qs.filter(name__icontains=search)
            return qs.order_by("name", "id")

        merged = {}
        order = []
        for domain, versions in versions_by_domain.items():
            with with_domain(domain):
                for group in build_queryset(versions)[: limit * 5]:
                    key = (group.name, group.id)
                    if key not in merged:
                        merged[key] = group
                        order.append(key)
                    else:
                        merged[key].packages = _union_package_lists(
                            merged[key].packages, group.packages
                        )
        order.sort(key=lambda key: key[0])
        page = [merged[key] for key in order[:limit]]
        serializer = self.get_serializer(page, many=True)
        return Response({"results": serializer.data})


class RpmContentViewEnvironmentSearchViewSet(ContentViewSearchViewSet):
    """Typeahead package-environment search: substring match, deduplicated by (name, id)."""

    endpoint_name = "search/rpm/environments"
    queryset = PackageEnvironment.objects.none()
    serializer_class = ContentViewPackageEnvironmentSerializer

    def list(self, request, *args, **kwargs):
        versions_by_domain = self._versions_by_domain()
        search = request.query_params.get("search", "")
        limit = _int_param(request, "limit", default=25, minimum=1, maximum=100)

        def build_queryset(versions):
            qs = content_for_versions(PackageEnvironment, versions)
            if search:
                qs = qs.filter(name__icontains=search)
            return qs.order_by("name", "id").distinct("name", "id")

        merged = {}
        order = []
        for domain, versions in versions_by_domain.items():
            with with_domain(domain):
                for environment in build_queryset(versions)[: limit * 5]:
                    key = (environment.name, environment.id)
                    if key not in merged:
                        merged[key] = environment
                        order.append(key)
        order.sort(key=lambda key: key[0])
        page = [merged[key] for key in order[:limit]]
        serializer = self.get_serializer(page, many=True)
        return Response({"results": serializer.data})


class RpmContentViewErrataViewSet(ContentViewSearchViewSet):
    """Full errata (advisory) search: filter/sort/paginate, with CVE references included."""

    endpoint_name = "search/rpm/errata"
    queryset = UpdateRecord.objects.none()
    serializer_class = ContentViewErrataSerializer

    def list(self, request, *args, **kwargs):
        versions_by_domain = self._versions_by_domain()
        search = request.query_params.get("search", "")
        types = _list_param(request, "type")
        severities = _list_param(request, "severity")
        limit = _int_param(request, "limit", default=100, minimum=1, maximum=1000)
        offset = _int_param(request, "offset", default=0, minimum=0)

        sort_by = request.query_params.get("sort_by", "id")
        descending = sort_by.startswith("-")
        sort_field = sort_by[1:] if descending else sort_by
        if sort_field not in ERRATA_SORT_FIELDS:
            sort_field = "id"

        def build_queryset(versions):
            qs = content_for_versions(UpdateRecord, versions).prefetch_related(
                Prefetch("references", queryset=UpdateReference.objects.filter(ref_type="cve"))
            )
            if search:
                qs = qs.filter(Q(id__icontains=search) | Q(title__icontains=search))
            if types:
                qs = qs.filter(_catch_all_filter("type", types, KNOWN_ERRATA_TYPES))
            if severities:
                qs = qs.filter(_catch_all_filter("severity", severities, KNOWN_ERRATA_SEVERITIES))
            return qs.order_by(sort_field)

        page, total = scatter_gather(
            versions_by_domain,
            build_queryset,
            order_by=(sort_field,),
            limit=limit,
            offset=offset,
            descending=descending,
        )
        serializer = self.get_serializer(page, many=True)
        return paginated_response(request, serializer.data, total, limit, offset)


class RpmContentViewModuleStreamsViewSet(ContentViewSearchViewSet):
    """Module stream search: name/stream substring match, optional RPM name filter, capped."""

    endpoint_name = "search/rpm/module-streams"
    queryset = Modulemd.objects.none()
    serializer_class = ContentViewModuleStreamSerializer

    def list(self, request, *args, **kwargs):
        versions_by_domain = self._versions_by_domain()
        search = request.query_params.get("search", "")
        rpm_names = _list_param(request, "rpm_names")
        limit = _int_param(
            request, "limit", default=100, minimum=1, maximum=MODULE_STREAMS_HARD_CAP
        )

        sort_by = request.query_params.get("sort_by", "name")
        descending = sort_by.startswith("-")
        sort_field = sort_by[1:] if descending else sort_by
        if sort_field not in MODULE_STREAM_SORT_FIELDS:
            sort_field = "name"

        def build_queryset(versions):
            qs = content_for_versions(Modulemd, versions)
            if search:
                qs = qs.filter(Q(name__icontains=search) | Q(stream__icontains=search))
            if rpm_names:
                qs = qs.filter(packages__name__in=rpm_names).distinct()
            return qs.order_by(sort_field)

        rows = []
        for domain, versions in versions_by_domain.items():
            with with_domain(domain):
                rows.extend(build_queryset(versions)[:limit])
        rows.sort(key=lambda m: getattr(m, sort_field), reverse=descending)
        page = rows[:limit]
        serializer = self.get_serializer(page, many=True)
        return Response({"results": serializer.data})


class RpmContentViewPackageListViewSet(ContentViewSearchViewSet):
    """Full package listing: exact name filter, fixed NEVRA sort, paginated."""

    endpoint_name = "search/rpm/packages/list"
    queryset = Package.objects.none()
    serializer_class = ContentViewPackageSerializer

    def list(self, request, *args, **kwargs):
        versions_by_domain = self._versions_by_domain()
        name = request.query_params.get("name", "")
        limit = _int_param(request, "limit", default=100, minimum=1, maximum=1000)
        offset = _int_param(request, "offset", default=0, minimum=0)

        def build_queryset(versions):
            qs = content_for_versions(Package, versions)
            if name:
                qs = qs.filter(name=name)
            return qs.order_by("name", "version", "release", "arch")

        page, total = scatter_gather(
            versions_by_domain,
            build_queryset,
            order_by=("name", "version", "release", "arch"),
            limit=limit,
            offset=offset,
        )
        serializer = self.get_serializer(page, many=True)
        return paginated_response(request, serializer.data, total, limit, offset)
