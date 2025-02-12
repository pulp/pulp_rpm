"""Tests that publish rpm plugin repositories."""

import os
import pytest

import collections
from lxml import etree
from django.conf import settings
from xml.etree import ElementTree
import requests

import xmltodict
import dictdiffer

from pulp_rpm.tests.functional.constants import (
    RPM_ALT_LAYOUT_FIXTURE_URL,
    RPM_COMPLEX_FIXTURE_URL,
    RPM_KICKSTART_FIXTURE_URL,
    RPM_KICKSTART_REPOSITORY_ROOT_CONTENT,
    RPM_REPO_METADATA_FIXTURE_URL,
    RPM_LONG_UPDATEINFO_FIXTURE_URL,
    RPM_MODULAR_FIXTURE_URL,
    RPM_NAMESPACES,
    RPM_REFERENCES_UPDATEINFO_URL,
    RPM_RICH_WEAK_FIXTURE_URL,
    RPM_SHA512_FIXTURE_URL,
    RPM_UNSIGNED_FIXTURE_URL,
    SRPM_UNSIGNED_FIXTURE_URL,
)
from pulp_rpm.tests.functional.utils import download_and_decompress_file

from pulpcore.client.pulp_rpm import RpmRepositorySyncURL, RpmRpmPublication
from pulpcore.client.pulp_rpm.exceptions import ApiException


class TestPublishWithUnsignedRepoSyncedImmediate:
    @pytest.mark.parallel
    def test_publish_any_repo_version(
        self,
        rpm_unsigned_repo_immediate,
        rpm_publication_api,
        monitor_task,
    ):
        """Test whether a particular repository version can be published."""
        publish_data = RpmRpmPublication(repository=rpm_unsigned_repo_immediate.pulp_href)
        publish_response = rpm_publication_api.create(publish_data)
        created_resources = monitor_task(publish_response.task).created_resources
        publication_href = created_resources[0]

        assert (
            rpm_publication_api.read(publication_href).repository_version
            == rpm_unsigned_repo_immediate.latest_version_href
        )

        non_latest = f"{rpm_unsigned_repo_immediate.pulp_href}versions/0/"

        publish_data.repository_version = non_latest
        publish_data.repository = None
        publish_response = rpm_publication_api.create(publish_data)
        created_resources = monitor_task(publish_response.task).created_resources
        publication_href = created_resources[0]
        publication = rpm_publication_api.read(publication_href)

        assert publication.repository_version == non_latest

        with pytest.raises(ApiException):
            body = {
                "repository": rpm_unsigned_repo_immediate.pulp_href,
                "repository_version": non_latest,
            }
            rpm_publication_api.create(body)

    @pytest.mark.parametrize("compression_type,compression_ext", (("gz", ".gz"), ("zstd", ".zst")))
    @pytest.mark.parallel
    def test_publish_with_compression_types(
        self,
        distribution_base_url,
        compression_type,
        compression_ext,
        rpm_unsigned_repo_immediate,
        rpm_publication_api,
        rpm_distribution_api,
        monitor_task,
        rpm_distribution_factory,
    ):
        """Sync and publish an RPM repository w/ zstd compression and verify it exists."""
        # 1. Publish and distribute
        publish_data = RpmRpmPublication(
            repository=rpm_unsigned_repo_immediate.pulp_href, compression_type=compression_type
        )
        publish_response = rpm_publication_api.create(publish_data)
        created_resources = monitor_task(publish_response.task).created_resources
        publication_href = created_resources[0]

        distribution = rpm_distribution_factory(publication=publication_href)

        # 2. Check "primary", "filelists", "other", "updateinfo" have correct compression ext
        for md_type, md_href in self.get_repomd_metadata_urls(
            distribution_base_url(distribution.base_url)
        ).items():
            if md_type in ("primary", "filelists", "other", "updateinfo"):
                assert md_href.endswith(compression_ext)

    @pytest.mark.parallel
    def test_validate_no_checksum_tag(
        self,
        distribution_base_url,
        rpm_unsigned_repo_immediate,
        rpm_publication_api,
        rpm_distribution_api,
        monitor_task,
        rpm_distribution_factory,
    ):
        """Sync and publish an RPM repository and verify the checksum.

        TODO: replace with https://github.com/pulp/pulp_rpm/issues/2957
        """
        # 1. Publish and distribute
        publish_data = RpmRpmPublication(repository=rpm_unsigned_repo_immediate.pulp_href)
        publish_response = rpm_publication_api.create(publish_data)
        created_resources = monitor_task(publish_response.task).created_resources
        publication_href = created_resources[0]

        distribution = rpm_distribution_factory(publication=publication_href)

        # 2. check the tag 'sum' is not present in updateinfo.xml
        update_xml_url = self.get_repomd_metadata_urls(
            distribution_base_url(distribution.base_url)
        )["updateinfo"]
        update_xml = download_and_decompress_file(
            os.path.join(distribution_base_url(distribution.base_url), update_xml_url)
        )
        update_info_content = ElementTree.fromstring(update_xml)

        tags = {elem.tag for elem in update_info_content.iter()}
        assert "sum" not in tags, update_info_content

    @staticmethod
    def get_repomd_metadata_urls(repomd_url: str):
        """
        Helper function to get hrefs of repomd types.

        Example:
            ```
            >>> get_repomd_metadata_urls(distribution_base_url(distribution.base_url))
            {
                "primary": "repodata/.../primary.xml.gz",
                "filelists": "repodata/.../filelists.xml.gz",
                ...
            }
            ```
        """
        # XML Reference:
        # <ns0:repomd xmlns:ns0="http://linux.duke.edu/metadata/repo">
        #     <ns0:data type="primary">
        #         <ns0:checksum type="sha256">[…]</ns0:checksum>
        #         <ns0:location href="repodata/[…]-primary.xml.gz" />
        #         …
        #     </ns0:data>
        #     …
        repomd_xml = requests.get(os.path.join(repomd_url, "repodata/repomd.xml")).text
        repomd = ElementTree.fromstring(repomd_xml)
        xpath_data = "{{{}}}data".format(RPM_NAMESPACES["metadata/repo"])
        xpath_location = "{{{}}}location".format(RPM_NAMESPACES["metadata/repo"])
        hrefs = {}
        for elem in repomd.findall(xpath_data):
            md_type = elem.get("type")
            hrefs[md_type] = elem.find(xpath_location).get("href")
        return hrefs


@pytest.fixture(scope="class")
def assert_created_publication(init_and_sync, rpm_publication_api, monitor_task):
    def _assert_created_publication(url):
        """Sync and publish an RPM repository given a feed URL."""
        repo, _ = init_and_sync(url=url)
        publish_data = RpmRpmPublication(repository=repo.pulp_href)
        publish_response = rpm_publication_api.create(publish_data)
        assert monitor_task(publish_response.task).created_resources != []

    return _assert_created_publication


@pytest.mark.parallel
def test_publish_rpm_rich_weak(assert_created_publication):
    """Sync and publish an RPM rich weak repository."""
    assert_created_publication(RPM_RICH_WEAK_FIXTURE_URL)


@pytest.mark.parallel
def test_publish_rpm_long_updateinfo(assert_created_publication):
    """Sync and publish an RPM long updateinfo repository."""
    assert_created_publication(RPM_LONG_UPDATEINFO_FIXTURE_URL)


@pytest.mark.parallel
def test_publish_rpm_custom_metadata(assert_created_publication):
    """Sync and publish an RPM with custom metadata files."""
    assert_created_publication(RPM_REPO_METADATA_FIXTURE_URL)


@pytest.mark.parallel
def test_publish_rpm_alt_layout(assert_created_publication):
    """Sync and publish an RPM alternate layout repository."""
    assert_created_publication(RPM_ALT_LAYOUT_FIXTURE_URL)


@pytest.mark.parallel
def test_publish_rpm_sha512(assert_created_publication):
    """Sync and publish an RPM SHA256 repository."""
    assert_created_publication(RPM_SHA512_FIXTURE_URL)


@pytest.mark.parallel
def test_publish_srpm(assert_created_publication):
    """Sync and publish an SRPM repository."""
    assert_created_publication(SRPM_UNSIGNED_FIXTURE_URL)


@pytest.mark.parallel
def test_publish_references_update(assert_created_publication):
    """Sync/publish a repo where ``updateinfo.xml`` contains references."""
    # TODO: check the updateinfo metadata to confirm the references are there.
    assert_created_publication(RPM_REFERENCES_UPDATEINFO_URL)


def get_metadata_content_helper(base_url, repomd_elem, meta_type):
    """Return the text contents of metadata file.

    Provided a url, a repomd root element, and a metadata type, locate the metadata
    file's location href, download it from the provided url, un-gzip it, parse it, and
    return the root element node.

    Don't use this with large repos because it will blow up.
    """
    # <ns0:repomd xmlns:ns0="http://linux.duke.edu/metadata/repo">
    #     <ns0:data type="primary">
    #         <ns0:checksum type="sha256">[…]</ns0:checksum>
    #         <ns0:location href="repodata/[…]-primary.xml.gz" />
    #         …
    #     </ns0:data>
    #     …
    xpath = "{{{}}}data".format(RPM_NAMESPACES["metadata/repo"])
    data_elems = [elem for elem in repomd_elem.findall(xpath) if elem.get("type") == meta_type]
    if not data_elems:
        return None

    xpath = "{{{}}}location".format(RPM_NAMESPACES["metadata/repo"])
    location_href = data_elems[0].find(xpath).get("href")

    return download_and_decompress_file(os.path.join(base_url, location_href))


@pytest.mark.parametrize("layout", ["flat", "nested_alphabetically"])
def test_repo_layout(
    layout,
    init_and_sync,
    rpm_publication_api,
    gen_object_with_cleanup,
    rpm_distribution_api,
    rpm_distribution_factory,
    monitor_task,
    delete_orphans_pre,
    tmpdir,
    wget_recursive_download_on_host,
):
    """Test that using the "layout" option for publication produces the correct package layouts"""

    # create repo and remote
    repo, _ = init_and_sync(url=RPM_UNSIGNED_FIXTURE_URL, policy="on_demand")

    # publish
    publish_data = RpmRpmPublication(repository=repo.pulp_href, layout=layout)
    publish_response = rpm_publication_api.create(publish_data)
    created_resources = monitor_task(publish_response.task).created_resources
    publication_href = created_resources[0]

    # distribute
    distribution = rpm_distribution_factory(publication=publication_href)

    # Download and parse the metadata.
    repomd = ElementTree.fromstring(
        requests.get(os.path.join(distribution.base_url, "repodata/repomd.xml")).text
    )

    # Convert the metadata into a more workable form and then compare.
    primary = get_metadata_content_helper(distribution.base_url, repomd, "primary")

    packages = xmltodict.parse(primary, dict_constructor=collections.OrderedDict)["metadata"][
        "package"
    ]

    for package in packages:
        if layout == "flat":
            assert package["location"]["@href"].startswith("Packages/{}".format(package["name"][0]))
        elif layout == "nested_alphabetically":
            assert package["location"]["@href"].startswith(
                "Packages/{}/".format(package["name"][0])
            )


@pytest.mark.parametrize("repo_url", [RPM_COMPLEX_FIXTURE_URL, RPM_MODULAR_FIXTURE_URL])
def test_complex_repo_core_metadata(
    distribution_base_url,
    repo_url,
    init_and_sync,
    rpm_publication_api,
    rpm_distribution_api,
    monitor_task,
    delete_orphans_pre,
    rpm_distribution_factory,
):
    """Test the "complex" fixture that covers more of the metadata cases.

    The standard fixtures have no changelogs and don't cover "ghost" files. The repo
    with the "complex-package" does, and also does a better job of covering rich deps
    and other atypical metadata.
    """

    # create repo and remote
    repo, _ = init_and_sync(url=repo_url, policy="on_demand")

    # publish
    publish_data = RpmRpmPublication(repository=repo.pulp_href)
    publish_response = rpm_publication_api.create(publish_data)
    created_resources = monitor_task(publish_response.task).created_resources
    publication_href = created_resources[0]

    # distribute
    distribution = rpm_distribution_factory(publication=publication_href)

    # Download and parse the metadata.
    original_repomd = ElementTree.fromstring(
        requests.get(os.path.join(repo_url, "repodata/repomd.xml")).text
    )

    reproduced_repomd = ElementTree.fromstring(
        requests.get(
            os.path.join(distribution_base_url(distribution.base_url), "repodata/repomd.xml")
        ).text
    )

    # Convert the metadata into a more workable form and then compare.
    for metadata_file in ["primary", "filelists", "other"]:
        original_metadata = get_metadata_content_helper(repo_url, original_repomd, metadata_file)
        generated_metadata = get_metadata_content_helper(
            distribution_base_url(distribution.base_url), reproduced_repomd, metadata_file
        )

        _compare_xml_metadata_file(original_metadata, generated_metadata, metadata_file)

    # =================

    original_modulemds = get_metadata_content_helper(repo_url, original_repomd, "modules")
    generated_modulemds = get_metadata_content_helper(
        distribution_base_url(distribution.base_url), reproduced_repomd, "modules"
    )

    assert bool(original_modulemds) == bool(generated_modulemds)

    if original_modulemds:
        # compare list of modulemd, modulemd-defaults, and modulemd-obsoletes after sorting them
        original_modulemds = sorted(original_modulemds.decode().split("---")[1:])
        generated_modulemds = sorted(generated_modulemds.decode().split("---")[1:])

        assert original_modulemds == generated_modulemds

    # ===================

    # TODO: make this deeper
    original_updateinfo = get_metadata_content_helper(repo_url, original_repomd, "updateinfo")
    generated_updateinfo = get_metadata_content_helper(
        distribution_base_url(distribution.base_url), reproduced_repomd, "updateinfo"
    )
    assert bool(original_updateinfo) == bool(generated_updateinfo)


def _compare_xml_metadata_file(original_metadata_text, generated_metadata_text, meta_type):
    """Compare two metadata files.

    First convert the metadata into a canonical form. We convert from XML to JSON, and then to
    a dict, and then apply transformations to the dict to standardize the ordering. Then, we
    perform comparisons and observe any differences.
    """
    metadata_block_names = {
        "primary": "metadata",
        "filelists": "filelists",
        "other": "otherdata",
    }
    subsection = metadata_block_names[meta_type]

    # First extract the package entries
    original_metadata = xmltodict.parse(
        original_metadata_text, dict_constructor=collections.OrderedDict
    )[subsection]["package"]
    generated_metadata = xmltodict.parse(
        generated_metadata_text, dict_constructor=collections.OrderedDict
    )[subsection]["package"]

    if not isinstance(original_metadata, list):
        original_metadata = [original_metadata]
    if not isinstance(generated_metadata, list):
        generated_metadata = [generated_metadata]

    # The other transformations are inside the package nodes - they differ by type of metadata
    if meta_type == "primary":
        # location_href gets rewritten by Pulp so we should ignore these differences
        ignore = {"location.@href", "format.file", "time.@file"}
        # we need to make sure all of the requirements are in the same order
        requirement_types = [
            "rpm:suggests",
            "rpm:recommends",
            "rpm:enhances",
            "rpm:provides",
            "rpm:requires",
            "rpm:obsoletes",
            "rpm:conflicts",
            "rpm:supplements",
        ]

        original_metadata = sorted(original_metadata, key=lambda x: x["checksum"]["#text"])
        generated_metadata = sorted(generated_metadata, key=lambda x: x["checksum"]["#text"])
        for md_file in [original_metadata, generated_metadata]:
            for pkg in md_file:
                for req in requirement_types:
                    if pkg["format"].get(req):
                        pkg["format"][req] = sorted(pkg["format"][req])
    elif meta_type == "filelists":
        ignore = {}
        original_metadata = sorted(original_metadata, key=lambda x: x["@pkgid"])
        generated_metadata = sorted(generated_metadata, key=lambda x: x["@pkgid"])
        # make sure the files are all in the same order and type and sort them
        # nodes with a "type" attribute in the XML become OrderedDicts, so we have to convert
        # them to a string representation.
        for md_file in [original_metadata, generated_metadata]:
            for pkg in md_file:
                if pkg.get("file"):
                    files = []
                    for f in pkg["file"]:
                        if isinstance(f, collections.OrderedDict):
                            files.append(
                                "{path} type={type}".format(path=f["@type"], type=f["#text"])
                            )
                        else:
                            files.append(f)

                    pkg["file"] = sorted(files)
    elif meta_type == "other":
        ignore = {}
        original_metadata = sorted(original_metadata, key=lambda x: x["@pkgid"])
        generated_metadata = sorted(generated_metadata, key=lambda x: x["@pkgid"])

        for md_file in [original_metadata, generated_metadata]:
            for pkg in md_file:
                # make sure the changelogs are in the same order
                if pkg.get("changelog"):
                    pkg["changelog"] = sorted(pkg["changelog"], key=lambda x: x["@author"])

    # The metadata dicts should now be consistently ordered. Check for differences.
    for original, generated in zip(original_metadata, generated_metadata):
        diff = dictdiffer.diff(original, generated, ignore=ignore)
        assert list(diff) == [], list(diff)


@pytest.mark.parallel
@pytest.mark.parametrize("mirror", [True, False], ids=["mirror", "standard"])
def test_distribution_tree_metadata_publish(
    distribution_base_url,
    mirror,
    rpm_repository_api,
    rpm_rpmremote_api,
    rpm_distribution_api,
    monitor_task,
    rpm_rpmremote_factory,
    rpm_repository_factory,
    rpm_distribution_factory,
):
    """Test the "complex" fixture that covers more of the metadata cases.

    The standard fixtures have no changelogs and don't cover "ghost" files. The repo
    with the "complex-package" does, and also does a better job of covering rich deps
    and other atypical metadata.
    """
    from configparser import ConfigParser

    # 1. create repo and remote
    repo = rpm_repository_factory(autopublish=not mirror)
    remote = rpm_rpmremote_factory(url=RPM_KICKSTART_FIXTURE_URL, policy="on_demand")

    # 2, 3. Sync and publish
    repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href, mirror=mirror)

    sync_response = rpm_repository_api.sync(repo.pulp_href, repository_sync_data)
    created_resources = monitor_task(sync_response.task).created_resources

    publication_href = [r for r in created_resources if "publication" in r][0]

    distribution = rpm_distribution_factory(publication=publication_href)

    # 4. Download and parse the metadata.
    original_treeinfo = requests.get(os.path.join(RPM_KICKSTART_FIXTURE_URL, ".treeinfo")).text
    generated_treeinfo = requests.get(
        os.path.join(distribution_base_url(distribution.base_url), ".treeinfo")
    ).text

    config = ConfigParser()
    config.optionxform = str  # by default it will cast keys to lower case
    config.read_string(original_treeinfo)
    original_treeinfo = config._sections

    config = ConfigParser()
    config.optionxform = str  # by default it will cast keys to lower case
    config.read_string(generated_treeinfo)
    generated_treeinfo = config._sections

    # 5, 6. Re-arrange the metadata so that it can be compared, and do the comparison.
    # TODO: These really should be in the same order they were in originally.
    # https://pulp.plan.io/issues/9208
    for metadata_dict in [original_treeinfo, generated_treeinfo]:
        metadata_dict["general"]["variants"] = ",".join(
            sorted(metadata_dict["general"]["variants"].split(","))
        )
        metadata_dict["tree"]["variants"] = ",".join(
            sorted(metadata_dict["tree"]["variants"].split(","))
        )

    diff = dictdiffer.diff(original_treeinfo, generated_treeinfo)
    differences = []

    # skip any differences that are "correct" i.e. rewritten "repository" and "packages" paths
    for d in diff:
        (diff_type, diff_name, _, new_value) = (d[0], d[1], d[2][0], d[2][1])
        # ('change', 'variant-Land.packages', ('Packages', 'Land/Packages'))
        if diff_type == "change":
            if diff_name.endswith(".packages") or diff_name.endswith(".repository"):
                # TODO: this is ignoring problems with the generated metadata
                # https://pulp.plan.io/issues/9208
                if "../" not in new_value:
                    continue

        differences.append(d)

    assert differences == [], differences

    # 7. Try downloading the files listed in the .treeinfo metadata, make sure they're
    # actually there.
    for path, checksum in original_treeinfo["checksums"].items():
        if path.startswith("fixtures"):
            # TODO: the .treeinfo metadata is actually wrong for these files, so we can't
            # check them because they won't be there.
            continue

        checksum_type, checksum = checksum.split(":")
        assert (
            requests.get(
                os.path.join(distribution_base_url(distribution.base_url), path)
            ).status_code
            == 200
        )


@pytest.fixture
def get_checksum_types(
    distribution_base_url,
    init_and_sync,
    rpm_publication_api,
    rpm_distribution_api,
    monitor_task,
    rpm_distribution_factory,
):
    """Sync and publish an RPM repository."""

    def _get_checksum_types(**kwargs):
        fixture_url = kwargs.get("fixture_url", RPM_UNSIGNED_FIXTURE_URL)
        configured_checksum_type = kwargs.get("checksum_type")
        policy = kwargs.get("policy", "immediate")

        # 1. create repo and remote
        repo, _ = init_and_sync(policy=policy, url=fixture_url, sync_policy="additive")

        # 2. Publish and distribute
        publish_data = RpmRpmPublication(
            repository=repo.pulp_href,
            checksum_type=configured_checksum_type,
        )
        publish_response = rpm_publication_api.create(publish_data)
        created_resources = monitor_task(publish_response.task).created_resources
        publication_href = created_resources[0]

        distribution = rpm_distribution_factory(publication=publication_href)

        repomd = ElementTree.fromstring(
            requests.get(
                os.path.join(distribution_base_url(distribution.base_url), "repodata/repomd.xml")
            ).text
        )

        data_xpath = "{{{}}}data".format(RPM_NAMESPACES["metadata/repo"])
        data_elems = [elem for elem in repomd.findall(data_xpath)]

        repomd_checksum_types = {}
        primary_checksum_types = {}
        checksum_xpath = "{{{}}}checksum".format(RPM_NAMESPACES["metadata/repo"])
        for data_elem in data_elems:
            checksum_type = data_elem.find(checksum_xpath).get("type")
            repomd_checksum_types[data_elem.get("type")] = checksum_type
            if data_elem.get("type") == "primary":
                location_xpath = "{{{}}}location".format(RPM_NAMESPACES["metadata/repo"])
                primary_href = data_elem.find(location_xpath).get("href")
                primary = ElementTree.fromstring(
                    download_and_decompress_file(
                        os.path.join(distribution_base_url(distribution.base_url), primary_href)
                    )
                )
                package_checksum_xpath = "{{{}}}checksum".format(RPM_NAMESPACES["metadata/common"])
                package_xpath = "{{{}}}package".format(RPM_NAMESPACES["metadata/common"])
                package_elems = [elem for elem in primary.findall(package_xpath)]
                pkg_checksum_type = package_elems[0].find(package_checksum_xpath).get("type")
                primary_checksum_types[package_elems[0].get("type")] = pkg_checksum_type

        return repomd_checksum_types, primary_checksum_types

    return _get_checksum_types


@pytest.mark.parallel
def test_publish_with_disallowed_checksum_type(rpm_unsigned_repo_on_demand, rpm_publication_api):
    """
    Sync and try to publish an RPM repository.

    - Sync repository with on_demand policy
    - Try to publish with 'sha384' checksum type
    - Publish should fail because 'sha384' is not allowed

    This test require disallowed 'sha384' checksum type from ALLOWED_CONTENT_CHECKSUMS settings.
    """
    if "sha384" in settings.ALLOWED_CONTENT_CHECKSUMS:
        pytest.skip(
            reason="Cannot check for the expected error if the 'sha384' checksum is allowed."
        )

    publish_data = RpmRpmPublication(
        repository=rpm_unsigned_repo_on_demand.pulp_href, checksum_type="sha384"
    )
    with pytest.raises(ApiException) as ctx:
        rpm_publication_api.create(publish_data)

    assert "Checksum must be one of the allowed checksum types" in ctx.value.body


@pytest.mark.parallel
def test_publish_with_unsupported_checksum_type(rpm_unsigned_repo_on_demand, rpm_publication_api):
    """
    Sync and try to publish an RPM repository.

    - Sync repository with on_demand policy
    - Try to publish with 'sha1' checksum type
    - Publish should fail because 'sha1' is not allowed
      (even though it is in ALLOWED_CONTENT_CHECKSUMS)
    """
    publish_data = RpmRpmPublication(
        repository=rpm_unsigned_repo_on_demand.pulp_href, checksum_type="sha1"
    )
    with pytest.raises(ApiException) as ctx:
        rpm_publication_api.create(publish_data)

    assert "Checksum must be one of the allowed checksum types" in ctx.value.body


@pytest.mark.parallel
def test_immediate_unspecified_checksum_type(get_checksum_types):
    """Sync and publish an RPM repository and verify the checksum types."""
    repomd_checksum_types, primary_checksum_types = get_checksum_types(
        fixture_url=RPM_SHA512_FIXTURE_URL, policy="immediate"
    )

    for repomd_type, repomd_checksum_type in repomd_checksum_types.items():
        assert repomd_checksum_type == "sha256"

    for package, package_checksum_type in primary_checksum_types.items():
        assert package_checksum_type == "sha256"


def test_on_demand_unspecified_checksum_type(get_checksum_types, delete_orphans_pre):
    """Sync and publish an RPM repository and verify the checksum types."""
    repomd_checksum_types, primary_checksum_types = get_checksum_types(
        fixture_url=RPM_SHA512_FIXTURE_URL, policy="on_demand"
    )

    for repomd_type, repomd_checksum_type in repomd_checksum_types.items():
        assert repomd_checksum_type == "sha256"

    for package, package_checksum_type in primary_checksum_types.items():
        # since none of the packages in question have sha512 checksums, the
        # checksums they do have will be used instead. In this case, sha512.
        assert package_checksum_type == "sha512"


@pytest.mark.parallel
def test_immediate_specified_checksum_type(get_checksum_types):
    """Sync and publish an RPM repository and verify the checksum types."""
    repomd_checksum_types, primary_checksum_types = get_checksum_types(
        checksum_type="sha512", policy="immediate"
    )

    for repomd_type, repomd_checksum_type in repomd_checksum_types.items():
        assert repomd_checksum_type == "sha512"

    for package, package_checksum_type in primary_checksum_types.items():
        assert package_checksum_type == "sha512"


def test_on_demand_specified_checksum_type(get_checksum_types, delete_orphans_pre):
    """Sync and publish an RPM repository and verify the checksum types."""
    repomd_checksum_types, primary_checksum_types = get_checksum_types(
        checksum_type="sha512", policy="on_demand"
    )

    for repomd_type, repomd_checksum_type in repomd_checksum_types.items():
        assert repomd_checksum_type == "sha512"

    for package, package_checksum_type in primary_checksum_types.items():
        # since none of the packages in question have sha512 checksums, the
        # checksums they do have will be used instead. In this case, sha256.
        assert package_checksum_type == "sha256"


@pytest.mark.parallel
def test_directory_layout_distribute_with_modules(
    distribution_base_url,
    generate_distribution,
):
    """Ensure no more files or folders are present when distribute repository with modules."""
    distribution = distribution_base_url(generate_distribution(RPM_MODULAR_FIXTURE_URL))
    parser = etree.XMLParser(recover=True)
    repository = etree.fromstring(requests.get(distribution).text, parser=parser)
    # Get links from repository HTML
    # Each link is an item (file or directory) in repository root
    repository_root_items = []
    for elem in repository.iter():
        if elem.tag == "a" and not elem.text.startswith(".."):  # skip parent-dir if present
            repository_root_items.append(elem.attrib["href"])

    # Check if 'Packages' and 'repodata' are present
    # Trailing '/' is present for easier check
    assert "Packages/" in repository_root_items
    assert "repodata/" in repository_root_items
    # Only these three items should be present
    assert len(repository_root_items) == 2


@pytest.mark.parallel
def test_directory_layout_distribute_with_treeinfo(
    generate_distribution,
    distribution_base_url,
):
    """Ensure no more files or folders are present when distribute repository with treeinfo."""
    distribution = distribution_base_url(generate_distribution(RPM_KICKSTART_FIXTURE_URL))
    parser = etree.XMLParser(recover=True)
    repository = etree.fromstring(requests.get(distribution).text, parser=parser)
    # Get links from repository HTML
    # Each link is an item (file or directory) in repository root
    repository_root_items = []
    for elem in repository.iter():
        if elem.tag == "a" and not elem.text.startswith(".."):  # skip parent-dir if present
            repository_root_items.append(elem.attrib["href"])
    # Check if all treeinfo related directories are present
    # Trailing '/' is present for easier check
    for directory in RPM_KICKSTART_REPOSITORY_ROOT_CONTENT:
        assert directory in repository_root_items

    assert "repodata/" in repository_root_items
    # assert how many items are present altogether
    # here is '+1' for 'repodata'
    assert len(repository_root_items) == len(RPM_KICKSTART_REPOSITORY_ROOT_CONTENT) + 1


@pytest.fixture(scope="class")
def generate_distribution(
    init_and_sync,
    rpm_distribution_api,
    rpm_publication_api,
    monitor_task,
    rpm_distribution_factory,
):
    def _generate_distribution(url=None):
        """Sync and publish an RPM repository.

        - create repository
        - create remote
        - sync the remote
        - create publication
        - create distribution

        Args:
            url(string):
                Optional URL of repository that should be use as a remote

        Returns (string):
            RPM distribution base_url.
        """
        repo, _ = init_and_sync(url=url)

        publish_data = RpmRpmPublication(repository=repo.pulp_href)
        publish_response = rpm_publication_api.create(publish_data)
        created_resources = monitor_task(publish_response.task).created_resources
        publication_href = created_resources[0]

        distribution = rpm_distribution_factory(publication=publication_href)

        return distribution.base_url

    return _generate_distribution
