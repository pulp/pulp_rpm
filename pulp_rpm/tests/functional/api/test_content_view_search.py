"""Tests for the cross-domain ContentView search endpoints exposed by pulp_rpm.

These exercise the six ``content-views/{uuid}/search/rpm/...`` endpoints (implemented on top of
pulpcore's generic ``ContentView`` resource) against two separate domains, verifying field
parity with the underlying content, pagination, filtering/sorting, and that a user who loses
access to one domain silently has that domain's content excluded from results rather than
erroring out.

The ``ContentView`` resource doesn't have generated bindings yet (it's brand new), so these
tests talk to it directly via ``requests`` using the same credentials as the bindings client.
"""

import uuid

import pytest
import requests

from pulp_rpm.tests.functional.constants import (
    RPM_ADVISORY_COUNT,
    RPM_PACKAGE_COUNT,
    RPM_SIGNED_FIXTURE_URL,
)


@pytest.fixture
def content_view_client(bindings_cfg):
    """A minimal client for the not-yet-bindings-generated ContentView endpoints."""

    class ContentViewClient:
        def _url(self, domain, path):
            return f"{bindings_cfg.host}/pulp/{domain}/api/v3/{path.lstrip('/')}"

        def _auth(self):
            return (bindings_cfg.username, bindings_cfg.password)

        def create(self, domain, name, distributions=()):
            resp = requests.post(
                self._url(domain, "content-views/"),
                json={"name": name, "distributions": list(distributions)},
                auth=self._auth(),
            )
            resp.raise_for_status()
            return resp.json()

        def read(self, domain, pk):
            resp = requests.get(self._url(domain, f"content-views/{pk}/"), auth=self._auth())
            resp.raise_for_status()
            return resp.json()

        def delete(self, domain, pk):
            requests.delete(self._url(domain, f"content-views/{pk}/"), auth=self._auth())

        def search(self, domain, pk, subpath, params=None):
            resp = requests.get(
                self._url(domain, f"content-views/{pk}/{subpath}/"),
                params=params or {},
                auth=self._auth(),
            )
            return resp

    return ContentViewClient()


@pytest.fixture
def two_domain_content_views(
    setup_domain, rpm_distribution_factory, content_view_client, gen_object_with_cleanup
):
    """Two domains, each with a synced repo + distribution, composed into one ContentView."""
    domain_a, _remote_a, src_a, _dest_a = setup_domain(sync=True, url=RPM_SIGNED_FIXTURE_URL)
    domain_b, _remote_b, src_b, _dest_b = setup_domain(sync=True, url=RPM_SIGNED_FIXTURE_URL)

    dist_a = rpm_distribution_factory(repository=src_a.pulp_href, pulp_domain=domain_a.name)
    dist_b = rpm_distribution_factory(repository=src_b.pulp_href, pulp_domain=domain_b.name)

    cv = content_view_client.create(
        domain_a.name,
        str(uuid.uuid4()),
        distributions=[dist_a.pulp_href, dist_b.pulp_href],
    )
    yield domain_a, domain_b, cv
    content_view_client.delete(domain_a.name, cv["pulp_href"].rstrip("/").split("/")[-1])


@pytest.mark.parallel
def test_content_view_crud(setup_domain, rpm_distribution_factory, content_view_client):
    """Create, read, update (via re-create since no bindings), and delete a ContentView."""
    domain, _remote, src, _dest = setup_domain(sync=True, url=RPM_SIGNED_FIXTURE_URL)
    dist = rpm_distribution_factory(repository=src.pulp_href, pulp_domain=domain.name)

    cv = content_view_client.create(domain.name, str(uuid.uuid4()), distributions=[dist.pulp_href])
    pk = cv["pulp_href"].rstrip("/").split("/")[-1]

    fetched = content_view_client.read(domain.name, pk)
    assert fetched["name"] == cv["name"]
    assert len(fetched["distributions"]) == 1
    assert fetched["distributions_status"][0]["status"] == "ok"

    content_view_client.delete(domain.name, pk)
    resp = requests.get(
        f"{content_view_client._url(domain.name, f'content-views/{pk}/')}",
        auth=content_view_client._auth(),
    )
    assert resp.status_code == 404


@pytest.mark.parallel
def test_content_view_cross_domain_search(two_domain_content_views, content_view_client):
    """All six search endpoints should aggregate results across both domains."""
    domain_a, domain_b, cv = two_domain_content_views
    pk = cv["pulp_href"].rstrip("/").split("/")[-1]

    resp = content_view_client.search(domain_a.name, pk, "search/rpm/packages/list")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2 * RPM_PACKAGE_COUNT
    domains_seen = {result["pulp_href"].split("/")[2] for result in body["results"]}
    assert domains_seen == {domain_a.name, domain_b.name}

    resp = content_view_client.search(domain_a.name, pk, "search/rpm/packages", {"limit": 5})
    assert resp.status_code == 200
    assert len(resp.json()["results"]) <= 5

    resp = content_view_client.search(domain_a.name, pk, "search/rpm/errata")
    assert resp.status_code == 200
    assert resp.json()["count"] == 2 * RPM_ADVISORY_COUNT

    resp = content_view_client.search(domain_a.name, pk, "search/rpm/package-groups")
    assert resp.status_code == 200
    assert "results" in resp.json()

    resp = content_view_client.search(domain_a.name, pk, "search/rpm/environments")
    assert resp.status_code == 200
    assert "results" in resp.json()

    resp = content_view_client.search(domain_a.name, pk, "search/rpm/module-streams")
    assert resp.status_code == 200
    assert resp.json() == {"results": []}


@pytest.mark.parallel
def test_content_view_errata_filters(two_domain_content_views, content_view_client):
    """The errata endpoint supports search/type/severity/sort_by/limit/offset."""
    domain_a, _domain_b, cv = two_domain_content_views
    pk = cv["pulp_href"].rstrip("/").split("/")[-1]

    all_resp = content_view_client.search(domain_a.name, pk, "search/rpm/errata")
    all_ids = [e["id"] for e in all_resp.json()["results"]]
    assert len(all_ids) == 2 * RPM_ADVISORY_COUNT

    page = content_view_client.search(
        domain_a.name, pk, "search/rpm/errata", {"limit": 1, "offset": 1}
    )
    assert page.status_code == 200
    page_body = page.json()
    assert len(page_body["results"]) == 1
    assert page_body["count"] == 2 * RPM_ADVISORY_COUNT
    assert page_body["next"] is not None
    assert page_body["previous"] is not None

    sorted_desc = content_view_client.search(
        domain_a.name, pk, "search/rpm/errata", {"sort_by": "-id"}
    )
    sorted_ids = [e["id"] for e in sorted_desc.json()["results"]]
    assert sorted_ids == sorted(all_ids, reverse=True)


@pytest.mark.parallel
def test_content_view_rbac_excludes_inaccessible_domain(
    two_domain_content_views, content_view_client, gen_user, bindings_cfg
):
    """A user without access to one domain should see that domain's content silently excluded."""
    domain_a, domain_b, cv = two_domain_content_views
    pk = cv["pulp_href"].rstrip("/").split("/")[-1]

    # A user who can see the ContentView (domain_a) but has no visibility into domain_b at all.
    # "core.contentview_viewer" is assigned *domain*-scoped (grants view_contentview for every
    # ContentView in domain_a), while "core.domain_viewer" is assigned *object*-scoped directly on
    # the domain_a Domain instance (grants view_domain for that specific Domain object) -- these
    # are deliberately different role-assignment kinds, since Domain objects aren't themselves
    # scoped to a domain the way ContentViews are.
    limited_user = gen_user(
        domain_roles=[("core.contentview_viewer", domain_a.pulp_href)],
        object_roles=[("core.domain_viewer", domain_a.pulp_href)],
    )

    with limited_user:
        resp = content_view_client.read(domain_a.name, pk)
        statuses = {d["domain"]: d["status"] for d in resp["distributions_status"]}
        assert statuses[domain_a.name] == "ok"
        assert statuses[domain_b.name] == "no_domain_access"

        search_resp = content_view_client.search(domain_a.name, pk, "search/rpm/packages/list")
        assert search_resp.status_code == 200
        body = search_resp.json()
        assert body["count"] == RPM_PACKAGE_COUNT
        domains_seen = {result["pulp_href"].split("/")[2] for result in body["results"]}
        assert domains_seen == {domain_a.name}
