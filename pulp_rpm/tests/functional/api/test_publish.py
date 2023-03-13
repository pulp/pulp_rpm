"""Tests that publish rpm plugin repositories."""
import os
import pytest

import collections
from lxml import etree
from django.conf import settings
from xml.etree import ElementTree

import xmltodict
import dictdiffer

from pulp_smash.pulp3.utils import gen_repo, gen_distribution

from pulp_rpm.tests.functional.constants import (
    RPM_ALT_LAYOUT_FIXTURE_URL,
    RPM_COMPLEX_FIXTURE_URL,
    RPM_KICKSTART_FIXTURE_URL,
    RPM_KICKSTART_REPOSITORY_ROOT_CONTENT,
    RPM_LONG_UPDATEINFO_FIXTURE_URL,
    RPM_MODULAR_FIXTURE_URL,
    RPM_NAMESPACES,
    RPM_REFERENCES_UPDATEINFO_URL,
    RPM_RICH_WEAK_FIXTURE_URL,
    RPM_SHA512_FIXTURE_URL,
    RPM_UNSIGNED_FIXTURE_URL,
    SRPM_UNSIGNED_FIXTURE_URL,
)
from pulp_rpm.tests.functional.utils import gen_rpm_remote, read_xml_gz
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401

from pulpcore.client.pulp_rpm import RpmRepositorySyncURL, RpmRpmPublication
from pulpcore.client.pulp_rpm.exceptions import ApiException


class TestPublishWithUnsignedRepoSyncedOnDemand:
    @pytest.mark.parallel
    @pytest.mark.parametrize("with_sqlite", [True, False], ids=["with_sqlite", "without_sqlite"])
    def test_sqlite_metadata(
        self,
        with_sqlite,
        rpm_unsigned_repo_on_demand,
        http_get,
        rpm_publication_api,
        gen_object_with_cleanup,
        rpm_distribution_api,
        monitor_task,
    ):
        """Publish repository and validate the updateinfo.

        This Test does the following:

        1. Create a rpm repo and a remote.
        2. Sync the repo with the remote.
        3. Publish with and without sqlite metadata and distribute the repo.
        4. Verify that the sqlite metadata files are/not present when expected.
        """
        publish_data = RpmRpmPublication(
            repository=rpm_unsigned_repo_on_demand.pulp_href, sqlite_metadata=with_sqlite
        )
        publish_response = rpm_publication_api.create(publish_data)
        created_resources = monitor_task(publish_response.task).created_resources
        publication_href = created_resources[0]

        body = gen_distribution(publication=publication_href)
        distribution = gen_object_with_cleanup(rpm_distribution_api, body)

        repomd = ElementTree.fromstring(
            http_get(os.path.join(distribution.base_url, "repodata/repomd.xml"))
        )

        data_xpath = "{{{}}}data".format(RPM_NAMESPACES["metadata/repo"])
        data_elems = [elem for elem in repomd.findall(data_xpath)]

        sqlite_files = [elem for elem in data_elems if elem.get("type").endswith("_db")]

        if with_sqlite:
            assert 3 == len(sqlite_files)

            for db_elem in sqlite_files:
                location_xpath = "{{{}}}location".format(RPM_NAMESPACES["metadata/repo"])
                db_href = db_elem.find(location_xpath).get("href")
                http_get(os.path.join(distribution.base_url, db_href))
        else:
            assert 0 == len(sqlite_files)

    @pytest.mark.parallel
    def test_publish_with_unsupported_checksum_type(
        self, rpm_unsigned_repo_on_demand, rpm_publication_api
    ):
        """
        Sync and try to publish an RPM repository.

        - Sync repository with on_demand policy
        - Try to publish with 'md5' checksum type
        - Publish should fail because 'md5' is not allowed

        This test require disallowed 'MD5' checksum type from ALLOWED_CONTENT_CHECKSUMS settings.
        """
        if "md5" in settings.ALLOWED_CONTENT_CHECKSUMS:
            pytest.skip(
                reason="Cannot verify the expected hasher error if the 'MD5' checksum is allowed."
            )

        publish_data = RpmRpmPublication(
            repository=rpm_unsigned_repo_on_demand.pulp_href, package_checksum_type="md5"
        )
        with pytest.raises(ApiException) as ctx:
            rpm_publication_api.create(publish_data)

        assert "Checksum must be one of the allowed checksum types." in ctx.value.body


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

    @pytest.mark.parallel
    def test_validate_no_checksum_tag(
        self,
        rpm_unsigned_repo_immediate,
        rpm_publication_api,
        gen_object_with_cleanup,
        http_get,
        rpm_distribution_api,
        monitor_task,
    ):
        """Sync and publish an RPM repository and verify the checksum.

        TODO: replace with https://github.com/pulp/pulp_rpm/issues/2957
        """
        # 1. Publish and distribute
        publish_data = RpmRpmPublication(repository=rpm_unsigned_repo_immediate.pulp_href)
        publish_response = rpm_publication_api.create(publish_data)
        created_resources = monitor_task(publish_response.task).created_resources
        publication_href = created_resources[0]

        body = gen_distribution(publication=publication_href)
        distribution = gen_object_with_cleanup(rpm_distribution_api, body)

        # 2. check the tag 'sum' is not present in updateinfo.xml
        repomd = ElementTree.fromstring(
            http_get(os.path.join(distribution.base_url, "repodata/repomd.xml"))
        )

        update_xml_url = self._get_updateinfo_xml_path(repomd)
        update_xml_content = http_get(os.path.join(distribution.base_url, update_xml_url))
        update_xml = read_xml_gz(update_xml_content)
        update_info_content = ElementTree.fromstring(update_xml)

        tags = {elem.tag for elem in update_info_content.iter()}
        assert "sum" not in tags, update_info_content

    @staticmethod
    def _get_updateinfo_xml_path(root_elem):
        """Return the path to ``updateinfo.xml.gz``, relative to repository root.

        Given a repomd.xml, this method parses the xml and returns the
        location of updateinfo.xml.gz.
        """
        # <ns0:repomd xmlns:ns0="http://linux.duke.edu/metadata/repo">
        #     <ns0:data type="primary">
        #         <ns0:checksum type="sha256">[…]</ns0:checksum>
        #         <ns0:location href="repodata/[…]-primary.xml.gz" />
        #         …
        #     </ns0:data>
        #     …
        xpath = "{{{}}}data".format(RPM_NAMESPACES["metadata/repo"])
        data_elems = [elem for elem in root_elem.findall(xpath) if elem.get("type") == "updateinfo"]
        xpath = "{{{}}}location".format(RPM_NAMESPACES["metadata/repo"])
        return data_elems[0].find(xpath).get("href")


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


@pytest.mark.parametrize("repo_url", [RPM_COMPLEX_FIXTURE_URL, RPM_MODULAR_FIXTURE_URL])
def test_complex_repo_core_metadata(
    repo_url,
    init_and_sync,
    rpm_publication_api,
    gen_object_with_cleanup,
    http_get,
    rpm_distribution_api,
    monitor_task,
    delete_orphans_pre,
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
    body = gen_distribution(publication=publication_href)
    distribution = gen_object_with_cleanup(rpm_distribution_api, body)

    # Download and parse the metadata.
    original_repomd = ElementTree.fromstring(
        http_get(os.path.join(repo_url, "repodata/repomd.xml"))
    )

    reproduced_repomd = ElementTree.fromstring(
        http_get(os.path.join(distribution.base_url, "repodata/repomd.xml"))
    )

    def get_metadata_content(base_url, repomd_elem, meta_type):
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

        return read_xml_gz(http_get(os.path.join(base_url, location_href)))

    # Convert the metadata into a more workable form and then compare.
    for metadata_file in ["primary", "filelists", "other"]:
        original_metadata = get_metadata_content(repo_url, original_repomd, metadata_file)
        generated_metadata = get_metadata_content(
            distribution.base_url, reproduced_repomd, metadata_file
        )

        _compare_xml_metadata_file(original_metadata, generated_metadata, metadata_file)

    # =================

    original_modulemds = get_metadata_content(repo_url, original_repomd, "modules")
    generated_modulemds = get_metadata_content(distribution.base_url, reproduced_repomd, "modules")

    assert bool(original_modulemds) == bool(generated_modulemds)

    if original_modulemds:
        # compare list of modulemd, modulemd-defaults, and modulemd-obsoletes after sorting them
        original_modulemds = sorted(original_modulemds.decode().split("---")[1:])
        generated_modulemds = sorted(generated_modulemds.decode().split("---")[1:])

        assert original_modulemds == generated_modulemds

    # ===================

    # TODO: make this deeper
    original_updateinfo = get_metadata_content(repo_url, original_repomd, "updateinfo")
    generated_updateinfo = get_metadata_content(
        distribution.base_url, reproduced_repomd, "updateinfo"
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
    mirror,
    gen_object_with_cleanup,
    http_get,
    rpm_repository_api,
    rpm_rpmremote_api,
    rpm_distribution_api,
    monitor_task,
):
    """Test the "complex" fixture that covers more of the metadata cases.

    The standard fixtures have no changelogs and don't cover "ghost" files. The repo
    with the "complex-package" does, and also does a better job of covering rich deps
    and other atypical metadata.
    """
    from configparser import ConfigParser

    # 1. create repo and remote
    repo = gen_object_with_cleanup(rpm_repository_api, gen_repo(autopublish=not mirror))

    body = gen_rpm_remote(RPM_KICKSTART_FIXTURE_URL, policy="on_demand")
    remote = gen_object_with_cleanup(rpm_rpmremote_api, body)

    # 2, 3. Sync and publish
    repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href, mirror=mirror)

    sync_response = rpm_repository_api.sync(repo.pulp_href, repository_sync_data)
    created_resources = monitor_task(sync_response.task).created_resources

    publication_href = [r for r in created_resources if "publication" in r][0]

    body = gen_distribution(publication=publication_href)
    distribution = gen_object_with_cleanup(rpm_distribution_api, body)

    # 4. Download and parse the metadata.
    original_treeinfo = http_get(os.path.join(RPM_KICKSTART_FIXTURE_URL, ".treeinfo"))
    generated_treeinfo = http_get(os.path.join(distribution.base_url, ".treeinfo"))

    config = ConfigParser()
    config.optionxform = str  # by default it will cast keys to lower case
    config.read_string(original_treeinfo.decode("utf-8"))
    original_treeinfo = config._sections

    config = ConfigParser()
    config.optionxform = str  # by default it will cast keys to lower case
    config.read_string(generated_treeinfo.decode("utf-8"))
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
        http_get(os.path.join(distribution.base_url, path))


@pytest.fixture
def get_checksum_types(
    init_and_sync,
    http_get,
    rpm_publication_api,
    gen_object_with_cleanup,
    rpm_distribution_api,
    monitor_task,
):
    """Sync and publish an RPM repository."""

    def _get_checksum_types(**kwargs):
        fixture_url = kwargs.get("fixture_url", RPM_UNSIGNED_FIXTURE_URL)
        package_checksum_type = kwargs.get("package_checksum_type")
        metadata_checksum_type = kwargs.get("metadata_checksum_type")
        policy = kwargs.get("policy", "immediate")

        # 1. create repo and remote
        repo, _ = init_and_sync(policy=policy, url=fixture_url, sync_policy="additive")

        # 2. Publish and distribute
        publish_data = RpmRpmPublication(
            repository=repo.pulp_href,
            package_checksum_type=package_checksum_type,
            metadata_checksum_type=metadata_checksum_type,
        )
        publish_response = rpm_publication_api.create(publish_data)
        created_resources = monitor_task(publish_response.task).created_resources
        publication_href = created_resources[0]

        body = gen_distribution(publication=publication_href)
        distribution = gen_object_with_cleanup(rpm_distribution_api, body)

        repomd = ElementTree.fromstring(
            http_get(os.path.join(distribution.base_url, "repodata/repomd.xml"))
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
                    read_xml_gz(http_get(os.path.join(distribution.base_url, primary_href)))
                )
                package_checksum_xpath = "{{{}}}checksum".format(RPM_NAMESPACES["metadata/common"])
                package_xpath = "{{{}}}package".format(RPM_NAMESPACES["metadata/common"])
                package_elems = [elem for elem in primary.findall(package_xpath)]
                pkg_checksum_type = package_elems[0].find(package_checksum_xpath).get("type")
                primary_checksum_types[package_elems[0].get("type")] = pkg_checksum_type

        return repomd_checksum_types, primary_checksum_types

    return _get_checksum_types


@pytest.mark.parallel
def test_on_demand_unspecified_checksum_types(get_checksum_types):
    """Sync and publish an RPM repository and verify the checksum types."""
    repomd_checksum_types, primary_checksum_types = get_checksum_types(
        fixture_url=RPM_SHA512_FIXTURE_URL, policy="on_demand"
    )

    for repomd_type, repomd_checksum_type in repomd_checksum_types.items():
        # hack to account for the fact that our md5 and sha512 repos use md5 and sha256
        # checksums for all metadata *except* updateinfo :(
        if not repomd_type == "updateinfo":
            assert repomd_checksum_type == "sha512"

    for package, package_checksum_type in primary_checksum_types.items():
        # since none of the packages in question have sha512 checksums, the
        # checksums they do have will be used instead. In this case, sha512.
        assert package_checksum_type == "sha512"


@pytest.mark.parallel
def test_immediate_unspecified_checksum_types(get_checksum_types):
    """Sync and publish an RPM repository and verify the checksum types."""
    repomd_checksum_types, primary_checksum_types = get_checksum_types(
        fixture_url=RPM_SHA512_FIXTURE_URL, policy="immediate"
    )

    for repomd_type, repomd_checksum_type in repomd_checksum_types.items():
        # hack to account for the fact that our md5 and sha512 repos use md5 and sha256
        # checksums for all metadata *except* updateinfo :(
        if not repomd_type == "updateinfo":
            assert repomd_checksum_type == "sha512"

    for package, package_checksum_type in primary_checksum_types.items():
        assert package_checksum_type == "sha512"


def test_on_demand_specified_package_checksum_type(get_checksum_types, delete_orphans_pre):
    """Sync and publish an RPM repository and verify the checksum types."""
    repomd_checksum_types, primary_checksum_types = get_checksum_types(
        package_checksum_type="sha384", policy="on_demand"
    )

    for repomd_type, repomd_checksum_type in repomd_checksum_types.items():
        assert repomd_checksum_type == "sha256"

    for package, package_checksum_type in primary_checksum_types.items():
        # since none of the packages in question have sha384 checksums, the
        # checksums they do have will be used instead. In this case, sha256.
        assert package_checksum_type == "sha256"


@pytest.mark.parallel
def test_on_demand_specified_metadata_checksum_type(get_checksum_types):
    """Sync and publish an RPM repository and verify the checksum types."""
    repomd_checksum_types, primary_checksum_types = get_checksum_types(
        metadata_checksum_type="sha384", policy="on_demand"
    )

    for repomd_type, repomd_checksum_type in repomd_checksum_types.items():
        assert repomd_checksum_type == "sha384"

    for package, package_checksum_type in primary_checksum_types.items():
        assert package_checksum_type == "sha256"


def test_on_demand_specified_metadata_and_package_checksum_type(
    get_checksum_types, delete_orphans_pre
):
    """Sync and publish an RPM repository and verify the checksum types."""
    repomd_checksum_types, primary_checksum_types = get_checksum_types(
        package_checksum_type="sha224", metadata_checksum_type="sha224", policy="on_demand"
    )

    for repomd_type, repomd_checksum_type in repomd_checksum_types.items():
        assert repomd_checksum_type == "sha224"

    for package, package_checksum_type in primary_checksum_types.items():
        # since none of the packages in question have sha224 checksums, the
        # checksums they do have will be used instead. In this case, sha256.
        assert package_checksum_type == "sha256"


@pytest.mark.parallel
def test_immediate_specified_package_checksum_type(get_checksum_types):
    """Sync and publish an RPM repository and verify the checksum types."""
    repomd_checksum_types, primary_checksum_types = get_checksum_types(
        package_checksum_type="sha384", policy="immediate"
    )

    for repomd_type, repomd_checksum_type in repomd_checksum_types.items():
        assert repomd_checksum_type == "sha256"

    for package, package_checksum_type in primary_checksum_types.items():
        assert package_checksum_type == "sha384"


@pytest.mark.parallel
def test_immediate_specified_metadata_checksum_type(get_checksum_types):
    """Sync and publish an RPM repository and verify the checksum types."""
    repomd_checksum_types, primary_checksum_types = get_checksum_types(
        metadata_checksum_type="sha384", policy="immediate"
    )

    for repomd_type, repomd_checksum_type in repomd_checksum_types.items():
        assert repomd_checksum_type == "sha384"

    for package, package_checksum_type in primary_checksum_types.items():
        assert package_checksum_type == "sha256"


@pytest.mark.parallel
def test_immediate_specified_metadata_and_package_checksum_type(get_checksum_types):
    """Sync and publish an RPM repository and verify the checksum types."""
    repomd_checksum_types, primary_checksum_types = get_checksum_types(
        package_checksum_type="sha224", metadata_checksum_type="sha224", policy="immediate"
    )

    for repomd_type, repomd_checksum_type in repomd_checksum_types.items():
        assert repomd_checksum_type == "sha224"

    for package, package_checksum_type in primary_checksum_types.items():
        assert package_checksum_type == "sha224"


@pytest.mark.parallel
def test_directory_layout_distribute_with_modules(generate_distribution, http_get):
    """Ensure no more files or folders are present when distribute repository with modules."""
    distribution = generate_distribution(RPM_MODULAR_FIXTURE_URL)
    parser = etree.XMLParser(recover=True)
    repository = etree.fromstring(http_get(distribution), parser=parser)
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
    assert "config.repo" in repository_root_items
    # Only these three items should be present
    assert len(repository_root_items) == 3


@pytest.mark.parallel
def test_directory_layout_distribute_with_treeinfo(generate_distribution, http_get):
    """Ensure no more files or folders are present when distribute repository with treeinfo."""
    distribution = generate_distribution(RPM_KICKSTART_FIXTURE_URL)
    parser = etree.XMLParser(recover=True)
    repository = etree.fromstring(http_get(distribution), parser=parser)
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
    assert "config.repo" in repository_root_items
    # assert how many items are present altogether
    # here is '+2' for 'repodata' and 'config.repo'
    assert len(repository_root_items) == len(RPM_KICKSTART_REPOSITORY_ROOT_CONTENT) + 2


@pytest.fixture(scope="class")
def generate_distribution(
    init_and_sync,
    gen_object_with_cleanup,
    rpm_distribution_api,
    rpm_publication_api,
    monitor_task,
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

        body = gen_distribution(publication=publication_href)
        distribution = gen_object_with_cleanup(rpm_distribution_api, body)

        return distribution.to_dict()["base_url"]

    return _generate_distribution
