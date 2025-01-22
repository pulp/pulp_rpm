"""Tests that publish rpm plugin repositories."""

from datetime import datetime
from tempfile import NamedTemporaryFile
from urllib.parse import urljoin

import pytest
import requests
from html.parser import HTMLParser
from productmd.treeinfo import TreeInfo

from pulp_rpm.tests.functional.constants import (
    RPM_PACKAGE_CONTENT_NAME,
    CENTOS8_STREAM_APPSTREAM_URL,
    CENTOS8_STREAM_BASEOS_URL,
)


class PackagesHtmlParser(HTMLParser):
    """HTML parser that looks for the first link to a file.

    This parser look for the first link that doesn't have a trailing slash. It then sets the
    package_href attribute to the value of the href.
    """

    package_href = None

    def handle_starttag(self, tag, attrs):
        """Looks for a tags that don't end with a slash."""
        if not self.package_href:
            if tag == "a" and not attrs[0][1].endswith("/"):
                self.package_href = attrs[0][1]
        else:
            super().handle_starttag(tag, attrs)


def parse_date_from_string(s, parse_format="%Y-%m-%dT%H:%M:%S.%fZ"):
    """Parse string to datetime object.

    :param s: str like '2018-11-18T21:03:32.493697Z'
    :param parse_format: str defaults to %Y-%m-%dT%H:%M:%S.%fZ
    :return: datetime.datetime
    """
    if isinstance(s, datetime):
        return s
    else:
        return datetime.strptime(s, parse_format)


@pytest.fixture
def centos_8stream_baseos_extra_tests(
    rpm_distribution_factory,
    distribution_base_url,
):
    def _extra_test(publication_href):
        # Test that the .treeinfo file is available and AppStream sub-repo is published correctly
        distribution = rpm_distribution_factory(publication=publication_href)
        treeinfo_file = requests.get(
            urljoin(distribution_base_url(distribution.base_url), ".treeinfo")
        ).content
        treeinfo = TreeInfo()
        with NamedTemporaryFile("wb") as temp_file:
            temp_file.write(treeinfo_file)
            temp_file.flush()
            treeinfo.load(f=temp_file.name)
        for variant_name, variant in treeinfo.variants.variants.items():
            if variant_name == "BaseOS":
                assert variant.paths.repository == "."
                assert variant.paths.packages == "Packages"
            elif variant_name == "AppStream":
                assert variant.paths.repository == "AppStream"
                assert variant.paths.packages == "AppStream/Packages"
                # Find the first package in the 'AppStream/Packages/a/' directory and download it
                parser = PackagesHtmlParser()
                a_packages_href = urljoin(
                    distribution_base_url(distribution.base_url),
                    "{}/a/".format(variant.paths.packages),
                )
                a_packages_listing = requests.get(a_packages_href).text
                parser.feed(a_packages_listing)
                full_package_path = urljoin(a_packages_href, parser.package_href)
                assert requests.get(full_package_path).status_code == 200

    return _extra_test


@pytest.mark.parametrize(
    "url,extra_tests",
    [
        (CENTOS8_STREAM_BASEOS_URL, "centos_8stream_baseos_extra_tests"),
        (CENTOS8_STREAM_APPSTREAM_URL, None),
        (CENTOS8_STREAM_BASEOS_URL, None),
    ],
)
def test_rpm_publish(
    url,
    extra_tests,
    init_and_sync,
    rpm_repository_version_api,
    rpm_publication_api,
    monitor_task,
    delete_orphans_pre,
    request,
):
    """Publish repositories with the rpm plugin.

    Do the following:

    1. Create a repository and a remote.
    2. Assert that repository version is None.
    3. Sync the remote.
    4. Assert that repository version is not None.
    5. Assert that distribution_tree units were added and are present in the repo.
    6. Publish
    """
    repo, remote, task = init_and_sync(url=url, policy="on_demand", return_task=True)
    created_at = parse_date_from_string(task.pulp_created)
    started_at = parse_date_from_string(task.started_at)
    finished_at = parse_date_from_string(task.finished_at)
    task_duration = finished_at - started_at
    waiting_time = started_at - created_at
    print(
        "\n->     Sync => Waiting time (s): {wait} | Service time (s): {service}".format(
            wait=waiting_time.total_seconds(), service=task_duration.total_seconds()
        )
    )

    # Check that we have the correct content counts.
    repo_ver = rpm_repository_version_api.read(repo.latest_version_href)
    assert RPM_PACKAGE_CONTENT_NAME in repo_ver.content_summary.present.keys()
    assert RPM_PACKAGE_CONTENT_NAME in repo_ver.content_summary.added.keys()

    # Publishing
    response = rpm_publication_api.create({"repository": repo.pulp_href})
    task = monitor_task(response.task)
    created_at = parse_date_from_string(task.pulp_created)
    started_at = parse_date_from_string(task.started_at)
    finished_at = parse_date_from_string(task.finished_at)
    task_duration = finished_at - started_at
    waiting_time = started_at - created_at
    print(
        "\n->     Publish => Waiting time (s): {wait} | Service time (s): {service}".format(
            wait=waiting_time.total_seconds(), service=task_duration.total_seconds()
        )
    )
    if extra_tests:
        # fixtures and parameterization don't like each other - this hack gets us around that
        xtra_fn = request.getfixturevalue(extra_tests)
        xtra_fn(task.created_resources[0])
