import uuid

import pytest
from urllib.parse import urlparse, urljoin
import requests

from pulpcore.client.pulp_rpm import (
    ApiClient as RpmApiClient,
    ContentRepoMetadataFilesApi,
    DistributionsRpmApi,
    PublicationsRpmApi,
    RemotesRpmApi,
    RepositoriesRpmApi,
    RepositoriesRpmVersionsApi,
    RpmPruneApi,
    RpmRepositorySyncURL,
)

from pulp_rpm.tests.functional.constants import (
    RPM_UNSIGNED_FIXTURE_URL,
)


@pytest.fixture(scope="session")
def rpm_publication_api(rpm_client):
    """Fixture for RPM publication API."""
    return PublicationsRpmApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_repository_version_api(rpm_client):
    """Fixture for the RPM repository versions API."""
    return RepositoriesRpmVersionsApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_distribution_api(rpm_client):
    """Fixture for RPM distribution API."""
    return DistributionsRpmApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_prune_api(rpm_client):
    """Fixture for RPM Prune API."""
    return RpmPruneApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_client(bindings_cfg):
    """Fixture for RPM client."""
    return RpmApiClient(bindings_cfg)


@pytest.fixture(scope="session")
def rpm_content_repometadata_files_api(rpm_client):
    return ContentRepoMetadataFilesApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_rpmremote_api(rpm_client):
    """Fixture for RPM remote API."""
    return RemotesRpmApi(rpm_client)


@pytest.fixture(scope="session")
def rpm_repository_api(rpm_client):
    """Fixture for RPM repositories API."""
    return RepositoriesRpmApi(rpm_client)


@pytest.fixture(scope="class")
def rpm_repository_factory(rpm_repository_api, gen_object_with_cleanup):
    """A factory to generate an RPM Repository with auto-deletion after the test run."""

    def _rpm_repository_factory(pulp_domain=None, **body):
        data = {"name": str(uuid.uuid4())}
        data.update(body)
        kwargs = {}
        if pulp_domain:
            kwargs["pulp_domain"] = pulp_domain
        return gen_object_with_cleanup(rpm_repository_api, data, **kwargs)

    return _rpm_repository_factory


@pytest.fixture(scope="class")
def rpm_rpmremote_factory(rpm_rpmremote_api, gen_object_with_cleanup):
    """A factory to generate an RPM Remote with auto-deletion after the test run."""

    def _rpm_rpmremote_factory(
        *, url=RPM_UNSIGNED_FIXTURE_URL, policy="immediate", pulp_domain=None, **body
    ):
        data = {"url": url, "policy": policy, "name": str(uuid.uuid4())}
        data.update(body)
        kwargs = {}
        if pulp_domain:
            kwargs["pulp_domain"] = pulp_domain
        return gen_object_with_cleanup(rpm_rpmremote_api, data, **kwargs)

    return _rpm_rpmremote_factory


@pytest.fixture(scope="class")
def rpm_distribution_factory(rpm_distribution_api, gen_object_with_cleanup):
    """A factory to generate an RPM Distribution with auto-deletion after the test run."""

    def _rpm_distribution_factory(pulp_domain=None, **body):
        data = {"base_path": str(uuid.uuid4()), "name": str(uuid.uuid4())}
        data.update(body)
        kwargs = {}
        if pulp_domain:
            kwargs["pulp_domain"] = pulp_domain
        return gen_object_with_cleanup(rpm_distribution_api, data, **kwargs)

    return _rpm_distribution_factory


@pytest.fixture(scope="class")
def rpm_publication_factory(rpm_publication_api, gen_object_with_cleanup):
    """A factory to generate an RPM Publication with auto-deletion after the test run."""

    def _rpm_publication_factory(pulp_domain=None, **body):
        # XOR check on repository and repository_version
        assert bool("repository" in body) ^ bool("repository_version" in body)
        kwargs = {}
        if pulp_domain:
            kwargs["pulp_domain"] = pulp_domain
        return gen_object_with_cleanup(rpm_publication_api, body, **kwargs)

    return _rpm_publication_factory


@pytest.fixture(scope="class")
def init_and_sync(rpm_repository_factory, rpm_repository_api, rpm_rpmremote_factory, monitor_task):
    """Initialize a new repository and remote and sync the content from the passed URL."""

    def _init_and_sync(
        repository=None,
        remote=None,
        url=RPM_UNSIGNED_FIXTURE_URL,
        policy="immediate",
        sync_policy="additive",
        skip_types=None,
        optimize=True,
        return_task=False,
    ):
        if repository is None:
            repository = rpm_repository_factory()
        if remote is None:
            remote = rpm_rpmremote_factory(url=url, policy=policy)

        repository_sync_data = RpmRepositorySyncURL(
            remote=remote.pulp_href,
            sync_policy=sync_policy,
            skip_types=skip_types,
            optimize=optimize,
        )
        sync_response = rpm_repository_api.sync(repository.pulp_href, repository_sync_data)
        task = monitor_task(sync_response.task)

        repository = rpm_repository_api.read(repository.pulp_href)
        return (repository, remote) if not return_task else (repository, remote, task)

    return _init_and_sync


@pytest.fixture
def pulp_requests(bindings_cfg):
    """Uses requests lib to issue an http request to pulp server using pulp_href.

    Example:
        >>> response = pulp_requests("get", "/pulp/api/v3/.../?repository_version=...")
        >>> type(response)
        requests.Response
    """
    ALLOWED_METHODS=("get", "update", "delete", "post")
    auth = (bindings_cfg.username, bindings_cfg.password)
    host = bindings_cfg.host

    def _pulp_requests(method: str, pulp_href: str, body = None):
        if method not in ALLOWED_METHODS:
            raise ValueError(f"Method should be in: {ALLOWED_METHODS}")
        url = urljoin(host, pulp_href)
        request_fn = getattr(requests, method)
        return request_fn(url, auth=auth)

    return _pulp_requests
        

@pytest.fixture
def get_content_summary(rpm_repository_version_api):
    """A fixture that fetches the content summary from a repository."""

    def _get_content_summary(repo, version_href=None, dump=True):
        """Fetches the content summary from a given repository.

        Args:
            repo: The repository where the content is fetched from.
            version_href: The repository version from where the content should be fetched from.
                Default: latest repository version.
            dump: If true, return a dumped dictionary with convenient filters (default).
                Otherwise, return the response object.

        Returns:
            The content summary of the repository.
        """
        version_href = version_href or repo.latest_version_href
        if version_href is None:
            return {}
        content_summary = rpm_repository_version_api.read(version_href).content_summary
        if not dump:
            return content_summary
        else:
            # removes the hrefs, which is may get in the way of data comparision
            # https://docs.pydantic.dev/latest/concepts/serialization/#pickledumpsmodel
            exclude_fields = {"__all__": {"__all__": {"href"}}}
            return content_summary.model_dump(exclude=exclude_fields)

    return _get_content_summary


@pytest.fixture
def get_content(
    rpm_repository_version_api,
    pulpcore_bindings,
    rpm_package_api,
    rpm_package_category_api,
    rpm_package_groups_api,
    rpm_advisory_api,
    rpm_package_lang_packs_api,
    rpm_content_repometadata_files_api,
    rpm_modulemd_api,
    rpm_modulemd_defaults_api,
    rpm_modulemd_obsoletes_api,
    rpm_content_distribution_trees_api,
    pulp_requests,
):
    """A fixture that fetches the content from a repository."""

    def _get_content(repo, version_href=None):
        """Fetches the content from a given repository.

        Args:
            repo: The repository where the content is fetched from.
            version_href: The repository version from where the content should be fetched from.
                Default: latest repository version.

        Returns:
            A dictionary with lists of packages by content_type (package, modulemd, etc)
            for 'present', 'added' and 'removed' content. E.g:

            ```python
            >>> get_content(repository)
            {
                'present': {
                    'rpm.package': [{'arch', 'noarch', 'artifact': ...}],
                    'rpm.packagegroup': [{'arch', 'noarch', 'artifact': ...}],
                    ...
                },
                'added': { ... },
                'removed': { ... },
            }
            ```
        """
        version_href = version_href or repo.latest_version_href
        if version_href is None:
            return {}
        content_summary = rpm_repository_version_api.read(version_href).content_summary
        BINDINGS_MAP = {
            "rpm.package": rpm_package_api,
            "rpm.packagecategory": rpm_package_category_api,
            "rpm.packagegroup": rpm_package_groups_api,
            "rpm.packagelangpacks": rpm_package_lang_packs_api,
            "rpm.advisory": rpm_advisory_api,
            "rpm.repo_metadata_file": rpm_content_repometadata_files_api,
            "rpm.modulemd": rpm_modulemd_api,
            "rpm.modulemd_defaults": rpm_modulemd_defaults_api,
            "rpm.modulemd_obsolete": rpm_modulemd_obsoletes_api,
            "rpm.distribution_tree": rpm_content_distribution_trees_api,
            "rpm.packageenvironment": rpm_content_distribution_trees_api,
        }

        def _fetch_content(content_type, href) -> list:
            attrs = {}
            bindings = BINDINGS_MAP[content_type]
            query_items = urlparse(href).query.split(";")
            for query in query_items:
                query_k, query_v = query.split("=")
                attrs[query_k] = query_v
            typed_content = bindings.list(**attrs)
            return typed_content.model_dump()["results"]

        def fetch_content(pulp_href) -> list:
            result = pulp_requests("get", pulp_href)
            result.raise_for_status()
            return result.json()["results"]

        result = {}
        for key in ("present", "added", "removed"):
            content = {}
            # ensure every content type returns at least an empty list
            for k in BINDINGS_MAP:
                content[k] = []
            # fetch content details for each content type
            summary_entry = getattr(content_summary, key)
            for content_type, content_dict in summary_entry.items():
                content[content_type] = fetch_content(content_dict["href"])
            result[key] = content
        return result

    return _get_content
