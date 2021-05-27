"""Tests that publish rpm plugin repositories."""
import gzip
import os
from tempfile import NamedTemporaryFile
from random import choice
from xml.etree import ElementTree

from pulp_smash import cli, config
from pulp_smash.utils import get_pulp_setting, http_get
from pulp_smash.pulp3.bindings import PulpTestCase, monitor_task
from pulp_smash.pulp3.utils import (
    delete_orphans,
    gen_repo,
    gen_distribution,
    get_content,
    get_content_summary,
    get_versions,
    modify_repo,
)

from pulp_rpm.tests.functional.constants import (
    RPM_ALT_LAYOUT_FIXTURE_URL,
    RPM_FIXTURE_SUMMARY,
    RPM_KICKSTART_FIXTURE_URL,
    RPM_KICKSTART_REPOSITORY_ROOT_CONTENT,
    RPM_LONG_UPDATEINFO_FIXTURE_URL,
    RPM_MODULAR_FIXTURE_URL,
    RPM_NAMESPACES,
    RPM_PACKAGE_CONTENT_NAME,
    RPM_REFERENCES_UPDATEINFO_URL,
    RPM_RICH_WEAK_FIXTURE_URL,
    RPM_SHA512_FIXTURE_URL,
    RPM_UNSIGNED_FIXTURE_URL,
    SRPM_UNSIGNED_FIXTURE_URL,
)
from pulp_rpm.tests.functional.utils import gen_rpm_client, gen_rpm_remote, skip_if
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401

from pulpcore.client.pulp_rpm import (
    DistributionsRpmApi,
    PublicationsRpmApi,
    RepositoriesRpmApi,
    RpmRepositorySyncURL,
    RemotesRpmApi,
    RpmRpmPublication,
)
from pulpcore.client.pulp_rpm.exceptions import ApiException


def read_xml_gz(content):
    """
    Read xml and xml.gz.

    Tests work normally but fails for S3 due '.gz'
    Why is it only compressed for S3?
    """
    with NamedTemporaryFile() as temp_file:
        temp_file.write(content)
        temp_file.seek(0)

        try:
            content_xml = gzip.open(temp_file.name).read()
        except OSError:
            # FIXME: fix this as in CI primary/update_info.xml has '.gz' but it is not gzipped
            content_xml = temp_file.read()
        return content_xml


class PublishAnyRepoVersionTestCase(PulpTestCase):
    """Test whether a particular repository version can be published.

    This test targets the following issues:

    * `Pulp #3324 <https://pulp.plan.io/issues/3324>`_
    * `Pulp Smash #897 <https://github.com/pulp/pulp-smash/issues/897>`_
    """

    def test_all(self):
        """Test whether a particular repository version can be published.

        1. Create a repository with at least 2 repository versions.
        2. Create a publication by supplying the latest ``repository_version``.
        3. Assert that the publication ``repository_version`` attribute points
           to the latest repository version.
        4. Create a publication by supplying the non-latest ``repository_version``.
        5. Assert that the publication ``repository_version`` attribute points
           to the supplied repository version.
        6. Assert that an exception is raised when providing two different
           repository versions to be published at same time.
        """
        cfg = config.get_config()
        client = gen_rpm_client()
        repo_api = RepositoriesRpmApi(client)
        remote_api = RemotesRpmApi(client)
        publications = PublicationsRpmApi(client)

        body = gen_rpm_remote()
        remote = remote_api.create(body)
        self.addCleanup(remote_api.delete, remote.pulp_href)

        repo = repo_api.create(gen_repo())
        self.addCleanup(repo_api.delete, repo.pulp_href)

        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_response = repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)

        # Step 1
        repo = repo_api.read(repo.pulp_href)
        for rpm_content in get_content(repo.to_dict())[RPM_PACKAGE_CONTENT_NAME]:
            modify_repo(cfg, repo.to_dict(), add_units=[rpm_content])
        version_hrefs = tuple(ver["pulp_href"] for ver in get_versions(repo.to_dict()))
        non_latest = choice(version_hrefs[:-1])

        # Step 2
        publish_data = RpmRpmPublication(repository=repo.pulp_href)
        publish_response = publications.create(publish_data)
        created_resources = monitor_task(publish_response.task).created_resources
        publication_href = created_resources[0]
        self.addCleanup(publications.delete, publication_href)
        publication = publications.read(publication_href)

        # Step 3
        self.assertEqual(publication.repository_version, version_hrefs[-1])

        # Step 4
        publish_data.repository_version = non_latest
        publish_data.repository = None
        publish_response = publications.create(publish_data)
        created_resources = monitor_task(publish_response.task).created_resources
        publication_href = created_resources[0]
        publication = publications.read(publication_href)

        # Step 5
        self.assertEqual(publication.repository_version, non_latest)

        # Step 6
        with self.assertRaises(ApiException):
            body = {"repository": repo.pulp_href, "repository_version": non_latest}
            publications.create(body)


class SyncPublishTestCase(PulpTestCase):
    """Test sync and publish for different RPM repositories.

    This test targets the following issue:

    `Pulp #4108 <https://pulp.plan.io/issues/4108>`_.
    `Pulp #4134 <https://pulp.plan.io/issues/4134>`_.
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = gen_rpm_client()
        cls.repo_api = RepositoriesRpmApi(cls.client)
        cls.remote_api = RemotesRpmApi(gen_rpm_client())
        cls.publications = PublicationsRpmApi(cls.client)

    def test_rpm_rich_weak(self):
        """Sync and publish an RPM repository. See :meth: `do_test`."""
        self.do_test(RPM_RICH_WEAK_FIXTURE_URL)

    def test_rpm_long_updateinfo(self):
        """Sync and publish an RPM repository. See :meth: `do_test`."""
        self.do_test(RPM_LONG_UPDATEINFO_FIXTURE_URL)

    def test_rpm_alt_layout(self):
        """Sync and publish an RPM repository. See :meth: `do_test`."""
        self.do_test(RPM_ALT_LAYOUT_FIXTURE_URL)

    def test_rpm_sha512(self):
        """Sync and publish an RPM repository. See :meth: `do_test`."""
        self.do_test(RPM_SHA512_FIXTURE_URL)

    def test_srpm(self):
        """Sync and publish a SRPM repository. See :meth: `do_test`."""
        self.do_test(SRPM_UNSIGNED_FIXTURE_URL)

    def do_test(self, url):
        """Sync and publish an RPM repository given a feed URL."""
        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        body = gen_rpm_remote(url=url)
        remote = self.remote_api.create(body)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)

        publish_data = RpmRpmPublication(repository=repo.pulp_href)
        publish_response = self.publications.create(publish_data)
        created_resources = monitor_task(publish_response.task).created_resources
        publication_href = created_resources[0]
        self.addCleanup(self.publications.delete, publication_href)

        self.assertIsNotNone(publication_href)


class SyncPublishReferencesUpdateTestCase(PulpTestCase):
    """Sync/publish a repo that ``updateinfo.xml`` contains references."""

    def test_all(self):
        """Sync/publish a repo that ``updateinfo.xml`` contains references.

        This test targets the following issue:

        `Pulp #3998 <https://pulp.plan.io/issues/3998>`_.
        """
        client = gen_rpm_client()
        repo_api = RepositoriesRpmApi(client)
        remote_api = RemotesRpmApi(client)
        publications = PublicationsRpmApi(client)

        repo = repo_api.create(gen_repo())
        self.addCleanup(repo_api.delete, repo.pulp_href)

        body = gen_rpm_remote(RPM_REFERENCES_UPDATEINFO_URL)
        remote = remote_api.create(body)
        self.addCleanup(remote_api.delete, remote.pulp_href)

        # Sync the repository.
        self.assertEqual(repo.latest_version_href, f"{repo.pulp_href}versions/0/")
        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_response = repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        repo = repo_api.read(repo.pulp_href)

        self.assertIsNotNone(repo.latest_version_href)

        content_summary = get_content_summary(repo.to_dict())
        self.assertDictEqual(content_summary, RPM_FIXTURE_SUMMARY, content_summary)

        publish_data = RpmRpmPublication(repository=repo.pulp_href)
        publish_response = publications.create(publish_data)
        created_resources = monitor_task(publish_response.task).created_resources
        publication_href = created_resources[0]

        self.assertIsNotNone(publication_href)

        self.addCleanup(publications.delete, publication_href)


class ValidateNoChecksumTagTestCase(PulpTestCase):
    """Publish repository and validate the updateinfo.

    This Test does the following:

    1. Create a rpm repo and a remote.
    2. Sync the repo with the remote.
    3. Publish and distribute the repo.
    4. Check whether CheckSum tag ``sum`` not present in ``updateinfo.xml``.

    This test targets the following issue:

    * `Pulp #4109 <https://pulp.plan.io/issues/4109>`_
    * `Pulp #4033 <https://pulp.plan.io/issues/4033>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = gen_rpm_client()
        cls.repo_api = RepositoriesRpmApi(cls.client)
        cls.remote_api = RemotesRpmApi(cls.client)
        cls.publications = PublicationsRpmApi(cls.client)
        cls.distributions = DistributionsRpmApi(cls.client)

    def test_all(self):
        """Sync and publish an RPM repository and verify the checksum."""
        # 1. create repo and remote
        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        body = gen_rpm_remote()
        remote = self.remote_api.create(body)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        # 2. Sync it
        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)

        # 3. Publish and distribute
        publish_data = RpmRpmPublication(repository=repo.pulp_href)
        publish_response = self.publications.create(publish_data)
        created_resources = monitor_task(publish_response.task).created_resources
        publication_href = created_resources[0]
        self.addCleanup(self.publications.delete, publication_href)

        body = gen_distribution()
        body["publication"] = publication_href
        distribution_response = self.distributions.create(body)
        created_resources = monitor_task(distribution_response.task).created_resources
        distribution = self.distributions.read(created_resources[0])
        self.addCleanup(self.distributions.delete, distribution.pulp_href)

        # 4. check the tag 'sum' is not present in updateinfo.xml
        repomd = ElementTree.fromstring(
            http_get(os.path.join(distribution.base_url, "repodata/repomd.xml"))
        )

        update_xml_url = self._get_updateinfo_xml_path(repomd)
        update_xml_content = http_get(os.path.join(distribution.base_url, update_xml_url))
        update_xml = read_xml_gz(update_xml_content)
        update_info_content = ElementTree.fromstring(update_xml)

        tags = {elem.tag for elem in update_info_content.iter()}
        self.assertNotIn("sum", tags, update_info_content)

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


class ChecksumTypeTestCase(PulpTestCase):
    """Publish repository and validate the updateinfo.

    This Test does the following:

    1. Create a rpm repo and a remote.
    2. Sync the repo with the remote.
    3. Publish and distribute the repo.
    4. Verify the checksum types

    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        delete_orphans()
        cls.cfg = config.get_config()
        cls.client = gen_rpm_client()
        cls.repo_api = RepositoriesRpmApi(cls.client)
        cls.remote_api = RemotesRpmApi(cls.client)
        cls.publications = PublicationsRpmApi(cls.client)
        cls.distributions = DistributionsRpmApi(cls.client)

    def setUp(self):
        """Clean up any orphans since it interferes with download policy specific behavior."""
        delete_orphans()

    def get_checksum_types(self, **kwargs):
        """Sync and publish an RPM repository."""
        fixture_url = kwargs.get("fixture_url", RPM_UNSIGNED_FIXTURE_URL)
        package_checksum_type = kwargs.get("package_checksum_type")
        metadata_checksum_type = kwargs.get("metadata_checksum_type")
        policy = kwargs.get("policy", "immediate")

        # 1. create repo and remote
        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        body = gen_rpm_remote(policy=policy, url=fixture_url)
        remote = self.remote_api.create(body)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        # 2. Sync it
        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href, mirror=False)
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)

        # 3. Publish and distribute
        publish_data = RpmRpmPublication(
            repository=repo.pulp_href,
            package_checksum_type=package_checksum_type,
            metadata_checksum_type=metadata_checksum_type,
        )
        publish_response = self.publications.create(publish_data)
        created_resources = monitor_task(publish_response.task).created_resources
        publication_href = created_resources[0]
        self.addCleanup(self.publications.delete, publication_href)

        body = gen_distribution()
        body["publication"] = publication_href
        distribution_response = self.distributions.create(body)
        created_resources = monitor_task(distribution_response.task).created_resources
        distribution = self.distributions.read(created_resources[0])
        self.addCleanup(self.distributions.delete, distribution.pulp_href)

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

    def test_on_demand_unspecified_checksum_types(self):
        """Sync and publish an RPM repository and verify the checksum types."""
        repomd_checksum_types, primary_checksum_types = self.get_checksum_types(
            fixture_url=RPM_SHA512_FIXTURE_URL, policy="on_demand"
        )

        for repomd_type, repomd_checksum_type in repomd_checksum_types.items():
            # hack to account for the fact that our md5 and sha512 repos use md5 and sha256
            # checksums for all metadata *except* updateinfo :(
            if not repomd_type == "updateinfo":
                self.assertEqual(repomd_checksum_type, "sha512")

        for package, package_checksum_type in primary_checksum_types.items():
            # since none of the packages in question have sha512 checksums, the
            # checksums they do have will be used instead. In this case, sha512.
            self.assertEqual(package_checksum_type, "sha512")

    def test_immediate_unspecified_checksum_types(self):
        """Sync and publish an RPM repository and verify the checksum types."""
        repomd_checksum_types, primary_checksum_types = self.get_checksum_types(
            fixture_url=RPM_SHA512_FIXTURE_URL, policy="immediate"
        )

        for repomd_type, repomd_checksum_type in repomd_checksum_types.items():
            # hack to account for the fact that our md5 and sha512 repos use md5 and sha256
            # checksums for all metadata *except* updateinfo :(
            if not repomd_type == "updateinfo":
                self.assertEqual(repomd_checksum_type, "sha512")

        for package, package_checksum_type in primary_checksum_types.items():
            self.assertEqual(package_checksum_type, "sha512")

    def test_on_demand_specified_package_checksum_type(self):
        """Sync and publish an RPM repository and verify the checksum types."""
        repomd_checksum_types, primary_checksum_types = self.get_checksum_types(
            package_checksum_type="sha384", policy="on_demand"
        )

        for repomd_type, repomd_checksum_type in repomd_checksum_types.items():
            self.assertEqual(repomd_checksum_type, "sha256")

        for package, package_checksum_type in primary_checksum_types.items():
            # since none of the packages in question have sha384 checksums, the
            # checksums they do have will be used instead. In this case, sha256.
            self.assertEqual(package_checksum_type, "sha256")

    def test_on_demand_specified_metadata_checksum_type(self):
        """Sync and publish an RPM repository and verify the checksum types."""
        repomd_checksum_types, primary_checksum_types = self.get_checksum_types(
            metadata_checksum_type="sha384", policy="on_demand"
        )

        for repomd_type, repomd_checksum_type in repomd_checksum_types.items():
            self.assertEqual(repomd_checksum_type, "sha384")

        for package, package_checksum_type in primary_checksum_types.items():
            self.assertEqual(package_checksum_type, "sha256")

    def test_on_demand_specified_metadata_and_package_checksum_type(self):
        """Sync and publish an RPM repository and verify the checksum types."""
        repomd_checksum_types, primary_checksum_types = self.get_checksum_types(
            package_checksum_type="sha224", metadata_checksum_type="sha224", policy="on_demand"
        )

        for repomd_type, repomd_checksum_type in repomd_checksum_types.items():
            self.assertEqual(repomd_checksum_type, "sha224")

        for package, package_checksum_type in primary_checksum_types.items():
            # since none of the packages in question have sha224 checksums, the
            # checksums they do have will be used instead. In this case, sha256.
            self.assertEqual(package_checksum_type, "sha256")

    def test_immediate_specified_package_checksum_type(self):
        """Sync and publish an RPM repository and verify the checksum types."""
        repomd_checksum_types, primary_checksum_types = self.get_checksum_types(
            package_checksum_type="sha384", policy="immediate"
        )

        for repomd_type, repomd_checksum_type in repomd_checksum_types.items():
            self.assertEqual(repomd_checksum_type, "sha256")

        for package, package_checksum_type in primary_checksum_types.items():
            self.assertEqual(package_checksum_type, "sha384")

    def test_immediate_specified_metadata_checksum_type(self):
        """Sync and publish an RPM repository and verify the checksum types."""
        repomd_checksum_types, primary_checksum_types = self.get_checksum_types(
            metadata_checksum_type="sha384", policy="immediate"
        )

        for repomd_type, repomd_checksum_type in repomd_checksum_types.items():
            self.assertEqual(repomd_checksum_type, "sha384")

        for package, package_checksum_type in primary_checksum_types.items():
            self.assertEqual(package_checksum_type, "sha256")

    def test_immediate_specified_metadata_and_package_checksum_type(self):
        """Sync and publish an RPM repository and verify the checksum types."""
        repomd_checksum_types, primary_checksum_types = self.get_checksum_types(
            package_checksum_type="sha224", metadata_checksum_type="sha224", policy="immediate"
        )

        for repomd_type, repomd_checksum_type in repomd_checksum_types.items():
            self.assertEqual(repomd_checksum_type, "sha224")

        for package, package_checksum_type in primary_checksum_types.items():
            self.assertEqual(package_checksum_type, "sha224")


class SqliteMetadataTestCase(PulpTestCase):
    """Publish repository and validate the updateinfo.

    This Test does the following:

    1. Create a rpm repo and a remote.
    2. Sync the repo with the remote.
    3. Publish with and without sqlite metadata and distribute the repo.
    4. Verify that the sqlite metadata files are/not present when expected.

    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        delete_orphans()
        cls.cfg = config.get_config()
        cls.client = gen_rpm_client()
        cls.repo_api = RepositoriesRpmApi(cls.client)
        cls.remote_api = RemotesRpmApi(cls.client)
        cls.publications = PublicationsRpmApi(cls.client)
        cls.distributions = DistributionsRpmApi(cls.client)

    def do_test(self, with_sqlite):
        """Sync and publish an RPM repository."""
        # 1. create repo and remote
        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        body = gen_rpm_remote(policy="on_demand")
        remote = self.remote_api.create(body)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        # 2. Sync it
        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)

        # 3. Publish and distribute
        publish_data = RpmRpmPublication(repository=repo.pulp_href, sqlite_metadata=with_sqlite)
        publish_response = self.publications.create(publish_data)
        created_resources = monitor_task(publish_response.task).created_resources
        publication_href = created_resources[0]
        self.addCleanup(self.publications.delete, publication_href)

        body = gen_distribution()
        body["publication"] = publication_href
        distribution_response = self.distributions.create(body)
        created_resources = monitor_task(distribution_response.task).created_resources
        distribution = self.distributions.read(created_resources[0])
        self.addCleanup(self.distributions.delete, distribution.pulp_href)

        repomd = ElementTree.fromstring(
            http_get(os.path.join(distribution.base_url, "repodata/repomd.xml"))
        )

        data_xpath = "{{{}}}data".format(RPM_NAMESPACES["metadata/repo"])
        data_elems = [elem for elem in repomd.findall(data_xpath)]

        sqlite_files = [elem for elem in data_elems if elem.get("type").endswith("_db")]

        if with_sqlite:
            self.assertEquals(3, len(sqlite_files))

            for db_elem in sqlite_files:
                location_xpath = "{{{}}}location".format(RPM_NAMESPACES["metadata/repo"])
                db_href = db_elem.find(location_xpath).get("href")
                http_get(os.path.join(distribution.base_url, db_href))
        else:
            self.assertEquals(0, len(sqlite_files))

    def test_sqlite_metadata(self):
        """Sync and publish an RPM repository and verify that the sqlite metadata exists."""
        self.do_test(True)

    def test_no_sqlite_metadata(self):
        """Sync and publish an RPM repository and verify that no sqlite metadata was generated."""
        self.do_test(False)


class PublishDirectoryLayoutTestCase(PulpTestCase):
    """Test published directory layout."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = gen_rpm_client()
        cls.repo_api = RepositoriesRpmApi(cls.client)
        cls.remote_api = RemotesRpmApi(gen_rpm_client())
        cls.publications = PublicationsRpmApi(cls.client)
        cls.distributions = DistributionsRpmApi(cls.client)

    def test_distribute_with_modules(self):
        """Ensure no more files or folders are present when distribute repository with modules."""
        distribution = self.do_test(RPM_MODULAR_FIXTURE_URL)
        repository = ElementTree.fromstring(http_get(distribution))
        # Get links from repository HTML
        # Each link is an item (file or directory) in repository root
        repository_root_items = []
        for elem in repository.iter():
            if elem.tag == "a":
                repository_root_items.append(elem.attrib["href"])

        # Check if 'Packages' and 'repodata' are present
        # Trailing '/' is present for easier check
        self.assertIn("Packages/", repository_root_items)
        self.assertIn("repodata/", repository_root_items)
        # Only three items should be present, two mentioned above and 'config.repo'
        self.assertEqual(len(repository_root_items), 3)

    def test_distribute_with_treeinfo(self):
        """Ensure no more files or folders are present when distribute repository with treeinfo."""
        distribution = self.do_test(RPM_KICKSTART_FIXTURE_URL)
        repository = ElementTree.fromstring(http_get(distribution))
        # Get links from repository HTML
        # Each link is an item (file or directory) in repository root
        repository_root_items = []
        for elem in repository.iter():
            if elem.tag == "a":
                repository_root_items.append(elem.attrib["href"])
        # Check if all treeinfo related directories are present
        # Trailing '/' is present for easier check
        for directory in RPM_KICKSTART_REPOSITORY_ROOT_CONTENT:
            self.assertIn(directory, repository_root_items)

        self.assertIn("repodata/", repository_root_items)
        # assert how many items are present altogether
        # here is '+2' for 'repodata' and 'config.repo'
        self.assertEqual(len(repository_root_items), len(RPM_KICKSTART_REPOSITORY_ROOT_CONTENT) + 2)

    def do_test(self, url=None):
        """Sync and publish an RPM repository.

        - create repository
        - create remote
        - sync the remote
        - create publication
        - create distribution

        Args:
            url(string):
                Optional URL of repositoy that should be use as a remote

        Returns (string):
            RPM distribution base_url.
        """
        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        if url:
            body = gen_rpm_remote(url=url)
        else:
            body = gen_rpm_remote()

        remote = self.remote_api.create(body)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)

        publish_data = RpmRpmPublication(repository=repo.pulp_href)
        publish_response = self.publications.create(publish_data)
        created_resources = monitor_task(publish_response.task).created_resources
        publication_href = created_resources[0]
        self.addCleanup(self.publications.delete, publication_href)

        body = gen_distribution()
        body["publication"] = publication_href
        distribution_response = self.distributions.create(body)
        created_resources = monitor_task(distribution_response.task).created_resources
        distribution = self.distributions.read(created_resources[0])
        self.addCleanup(self.distributions.delete, distribution.pulp_href)

        return distribution.to_dict()["base_url"]


class PublishUnsupportedChecksumTestCase(PulpTestCase):
    """Test unsupported publish."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = gen_rpm_client()
        cls.cli_client = cli.Client(cls.cfg)
        cls.repo_api = RepositoriesRpmApi(cls.client)
        cls.remote_api = RemotesRpmApi(gen_rpm_client())
        cls.publications = PublicationsRpmApi(cls.client)
        cls.distributions = DistributionsRpmApi(cls.client)
        cls.md5_allowed = "md5" in get_pulp_setting(cls.cli_client, "ALLOWED_CONTENT_CHECKSUMS")

    @skip_if(bool, "md5_allowed", True)
    def test_publish_with_unsupported_checksum_type(self):
        """
        Sync and try publish an RPM repository.

        - Sync repository with on_demand policy
        - Try to publish with 'md5' checksum type
        - Publish should fail because 'md5' is not allowed

        This test require disallowed 'MD5' checksum type from ALLOWED_CONTENT_CHECKSUMS settings.
        """
        # 1. create repo and remote
        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        body = gen_rpm_remote(policy="on_demand")
        remote = self.remote_api.create(body)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        # 2. Sync it
        repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)

        # 3. Publish and fail
        publish_data = RpmRpmPublication(repository=repo.pulp_href, package_checksum_type="md5")
        with self.assertRaises(ApiException) as ctx:
            self.publications.create(publish_data)
        self.assertIn("Checksum must be one of the allowed checksum types.", ctx.exception.body)
