"""
Tests PulpImporter and PulpImport functionality.

NOTE: assumes ALLOWED_EXPORT_PATHS and ALLOWED_IMPORT_PATHS settings contain "/tmp" - all tests
will fail if this is not the case.
"""
from pulp_smash import api, cli, config, utils
from pulp_smash.utils import uuid4
from pulp_smash.pulp3.bindings import (
    delete_orphans,
    monitor_task,
    monitor_task_group,
    PulpTestCase,
)
from pulp_smash.pulp3.utils import gen_repo, get_content

from pulp_rpm.tests.functional.constants import RPM_KICKSTART_FIXTURE_URL, RPM_UNSIGNED_FIXTURE_URL
from pulp_rpm.tests.functional.utils import (
    gen_rpm_client,
    gen_rpm_remote,
)

from pulpcore.client.pulpcore import (
    ApiClient as CoreApiClient,
    ExportersPulpApi,
    ExportersPulpExportsApi,
    ImportersPulpApi,
    ImportersPulpImportsApi,
)
from pulpcore.client.pulp_rpm import (
    ContentDistributionTreesApi,
    RepositoriesRpmApi,
    RpmRepositorySyncURL,
    RemotesRpmApi,
)

NUM_REPOS = 2


class PulpImportTestBase(PulpTestCase):
    """
    Base functionality for PulpImporter and PulpImport test classes.
    """

    @classmethod
    def _setup_repositories(cls, url=None):
        """Create and sync a number of repositories to be exported."""
        # create and remember a set of repo
        import_repos = []
        export_repos = []
        remotes = []
        for r in range(NUM_REPOS):
            import_repo = cls.repo_api.create(gen_repo())
            export_repo = cls.repo_api.create(gen_repo())

            if url:
                body = gen_rpm_remote(url)
            else:
                body = gen_rpm_remote()
            remote = cls.remote_api.create(body)

            repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
            sync_response = cls.repo_api.sync(export_repo.pulp_href, repository_sync_data)
            monitor_task(sync_response.task)
            # remember it
            export_repos.append(export_repo)
            import_repos.append(import_repo)
            remotes.append(remote)
        return import_repos, export_repos, remotes

    @classmethod
    def _create_exporter(cls, cleanup=True):
        body = {
            "name": uuid4(),
            "repositories": [r.pulp_href for r in cls.export_repos],
            "path": "/tmp/{}".format(uuid4()),
        }
        exporter = cls.exporter_api.create(body)
        return exporter

    @classmethod
    def _create_export(cls):
        export_response = cls.exports_api.create(cls.exporter.pulp_href, {})
        monitor_task(export_response.task)
        task = cls.client.get(export_response.task)
        resources = task["created_resources"]
        export_href = resources[0]
        export = cls.exports_api.read(export_href)
        return export

    @classmethod
    def _create_chunked_export(cls):
        export_response = cls.exports_api.create(cls.exporter.pulp_href, {"chunk_size": "5KB"})
        monitor_task(export_response.task)
        task = cls.client.get(export_response.task)
        resources = task["created_resources"]
        export_href = resources[0]
        export = cls.exports_api.read(export_href)
        return export

    @classmethod
    def _delete_exporter(cls, delete_file=True):
        """
        Utility routine to delete an exporter.

        Also removes the export-directory and all its contents.
        """
        if delete_file:
            cli_client = cli.Client(cls.cfg)
            cmd = ("rm", "-rf", cls.exporter.path)
            cli_client.run(cmd, sudo=True)
        cls.exporter_api.delete(cls.exporter.pulp_href)

    @classmethod
    def tearDownClass(cls):
        """Clean up."""
        for remote in cls.remotes:
            cls.remote_api.delete(remote.pulp_href)

        for repo in cls.export_repos:
            cls.repo_api.delete(repo.pulp_href)

        for repo in cls.import_repos:
            cls.repo_api.delete(repo.pulp_href)

        cls._delete_exporter()

        delete_orphans()

    def _create_importer(self, name=None, cleanup=True):
        """Create an importer."""
        mapping = {}
        if not name:
            name = uuid4()

        for idx, repo in enumerate(self.export_repos):
            mapping[repo.name] = self.import_repos[idx].name

        body = {
            "name": name,
            "repo_mapping": mapping,
        }

        importer = self.importer_api.create(body)

        if cleanup:
            self.addCleanup(self.importer_api.delete, importer.pulp_href)

        return importer

    def _perform_import(self, importer, chunked=False):
        """Perform an import with importer."""
        if chunked:
            filenames = [
                f for f in list(self.chunked_export.output_file_info.keys()) if f.endswith("json")
            ]
            import_response = self.imports_api.create(importer.pulp_href, {"toc": filenames[0]})
        else:
            filenames = [
                f for f in list(self.export.output_file_info.keys()) if f.endswith("tar.gz")
            ]
            import_response = self.imports_api.create(importer.pulp_href, {"path": filenames[0]})
        task_group = monitor_task_group(import_response.task_group)

        return task_group


class PulpImportTestCase(PulpImportTestBase):
    """
    Basic tests for PulpImporter and PulpImport.
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)
        cls.core_client = CoreApiClient(configuration=cls.cfg.get_bindings_config())
        cls.rpm_client = gen_rpm_client()

        cls.repo_api = RepositoriesRpmApi(cls.rpm_client)
        cls.remote_api = RemotesRpmApi(cls.rpm_client)
        cls.exporter_api = ExportersPulpApi(cls.core_client)
        cls.exports_api = ExportersPulpExportsApi(cls.core_client)
        cls.importer_api = ImportersPulpApi(cls.core_client)
        cls.imports_api = ImportersPulpImportsApi(cls.core_client)

        cls.import_repos, cls.export_repos, cls.remotes = cls._setup_repositories()
        cls.exporter = cls._create_exporter()
        cls.export = cls._create_export()
        cls.chunked_export = cls._create_chunked_export()

    def test_import(self):
        """Test an import."""
        importer = self._create_importer()
        task_group = self._perform_import(importer)
        self.assertEqual(len(self.import_repos) + 1, task_group.completed)
        for repo in self.import_repos:
            repo = self.repo_api.read(repo.pulp_href)
            self.assertEqual(f"{repo.pulp_href}versions/1/", repo.latest_version_href)

    def test_double_import(self):
        """Test two imports of our export."""
        importer = self._create_importer()
        self._perform_import(importer)
        self._perform_import(importer)

        imports = self.imports_api.list(importer.pulp_href).results
        self.assertEqual(len(imports), 2)

        for repo in self.import_repos:
            repo = self.repo_api.read(repo.pulp_href)
            # still only one version as pulp won't create a new version if nothing changed
            self.assertEqual(f"{repo.pulp_href}versions/1/", repo.latest_version_href)


class DistributionTreePulpImportTestCase(PulpImportTestBase):
    """
    Tests for PulpImporter and PulpImport for repos with DistributionTrees.
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)
        cls.core_client = CoreApiClient(configuration=cls.cfg.get_bindings_config())
        cls.rpm_client = gen_rpm_client()

        cls.repo_api = RepositoriesRpmApi(cls.rpm_client)
        cls.remote_api = RemotesRpmApi(cls.rpm_client)
        cls.exporter_api = ExportersPulpApi(cls.core_client)
        cls.exports_api = ExportersPulpExportsApi(cls.core_client)
        cls.importer_api = ImportersPulpApi(cls.core_client)
        cls.imports_api = ImportersPulpImportsApi(cls.core_client)
        cls.dist_tree_api = ContentDistributionTreesApi(cls.rpm_client)

        cls.import_repos, cls.export_repos, cls.remotes = cls._setup_repositories(
            RPM_KICKSTART_FIXTURE_URL
        )
        cls.exporter = cls._create_exporter()
        cls.export = cls._create_export()

    def test_import(self):
        """Test an import."""
        importer = self._create_importer()
        task_group = self._perform_import(importer)
        self.assertEqual(len(self.import_repos) + 1, task_group.completed)
        for repo in self.import_repos:
            repo = self.repo_api.read(repo.pulp_href)
            self.assertEqual(f"{repo.pulp_href}versions/1/", repo.latest_version_href)
            trees = self.dist_tree_api.list(repository_version=repo.latest_version_href)
            self.assertEqual(trees.count, 1)


class ParallelImportTestCase(PulpImportTestBase):
    """
    Tests for PulpImporter and PulpImport parallel import into a clean repository.
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)
        cls.core_client = CoreApiClient(configuration=cls.cfg.get_bindings_config())
        cls.rpm_client = gen_rpm_client()

        cls.repo_api = RepositoriesRpmApi(cls.rpm_client)
        cls.remote_api = RemotesRpmApi(cls.rpm_client)
        cls.exporter_api = ExportersPulpApi(cls.core_client)
        cls.exports_api = ExportersPulpExportsApi(cls.core_client)
        cls.importer_api = ImportersPulpApi(cls.core_client)
        cls.imports_api = ImportersPulpImportsApi(cls.core_client)
        cls.dist_tree_api = ContentDistributionTreesApi(cls.rpm_client)

        cls.import_repos, cls.export_repos, cls.remotes = cls._setup_repositories(
            RPM_UNSIGNED_FIXTURE_URL
        )
        cls.exporter = cls._create_exporter()
        cls.export = cls._create_export()

    @classmethod
    def tearDownClass(cls):
        """No need for class to clean up, we've already done it."""
        pass

    def tearDown(self):
        """Remaining clean up repos/export already gone by now."""
        for repo in self.import_repos:
            self.repo_api.delete(repo.pulp_href)
        delete_orphans()

    def _post_export_cleanup(self):
        """
        Remove the exported repos and their content, so we're importing into a 'clean' db.
        """
        self._delete_exporter(delete_file=False)
        for remote in self.remotes:
            self.remote_api.delete(remote.pulp_href)
        for repo in self.export_repos:
            self.repo_api.delete(repo.pulp_href)
        delete_orphans()

    def test_clean_import(self):
        """Test an import into an empty instance."""
        # By the time we get here, setUpClass() has created repos and an export for us
        # Find the export file, create the importer, delete repos/export, and then let
        # the import happen
        filenames = [f for f in list(self.export.output_file_info.keys()) if f.endswith("tar.gz")]
        importer = self._create_importer()
        self._post_export_cleanup()
        existing_repos = self.repo_api.list().count
        # At this point we should be importing into a content-free-zone
        import_response = self.imports_api.create(importer.pulp_href, {"path": filenames[0]})
        task_group = monitor_task_group(import_response.task_group)
        self.assertEqual(len(self.import_repos) + 1, task_group.completed)
        for repo in self.import_repos:
            repo = self.repo_api.read(repo.pulp_href)
            self.assertEqual(f"{repo.pulp_href}versions/1/", repo.latest_version_href)
        # We should have the same number of repositories, post-import, than however many we had
        # post-removal of the export-repos
        self.assertEqual(self.repo_api.list().count, existing_repos)


class CreateMissingReposImportTestCase(PulpTestCase):
    """
     Tests for PulpImporter and create-missing-repos.

     1. Create a regular and a dist-tree remote
     2. Create a repo for each
     3. Sync both repos
     4. Create an exporter
     5. Export the repos, remember the export-file
     6. post-export-cleanup
        a. delete repos
        b. delete exporter
        c. orphan cleanup
    7. create importer
    8. import the export, create_repos=True
    9. Inspect the results
       a. Only 2 new repos exist
       b. dist-tree-repo has expected addon/variant/etc
    """

    def setUp(self):
        """API-access, steps 1-6 above."""
        self.cfg = config.get_config()
        self.client = api.Client(self.cfg, api.json_handler)
        self.core_client = CoreApiClient(configuration=self.cfg.get_bindings_config())
        self.rpm_client = gen_rpm_client()

        self.repo_api = RepositoriesRpmApi(self.rpm_client)
        self.remote_api = RemotesRpmApi(self.rpm_client)
        self.exporter_api = ExportersPulpApi(self.core_client)
        self.exports_api = ExportersPulpExportsApi(self.core_client)
        self.importer_api = ImportersPulpApi(self.core_client)
        self.imports_api = ImportersPulpImportsApi(self.core_client)
        self.dist_tree_api = ContentDistributionTreesApi(self.rpm_client)

        entity_map = {}

        # Step 1, remotes
        body = {"name": utils.uuid4(), "url": RPM_UNSIGNED_FIXTURE_URL, "policy": "immediate"}
        entity_map["rpm-remote"] = self.remote_api.create(body)
        body = {"name": utils.uuid4(), "url": RPM_KICKSTART_FIXTURE_URL, "policy": "immediate"}
        entity_map["ks-remote"] = self.remote_api.create(body)

        # Step 2, repositories
        body = {"name": utils.uuid4()}
        entity_map["rpm-repo"] = self.repo_api.create(body)
        body = {"name": utils.uuid4()}
        entity_map["ks-repo"] = self.repo_api.create(body)

        # Step 3, sync
        repository_sync_data = RpmRepositorySyncURL(remote=entity_map["rpm-remote"].pulp_href)
        sync_response = self.repo_api.sync(entity_map["rpm-repo"].pulp_href, repository_sync_data)
        monitor_task(sync_response.task)

        repository_sync_data = RpmRepositorySyncURL(remote=entity_map["ks-remote"].pulp_href)
        sync_response = self.repo_api.sync(entity_map["ks-repo"].pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        # Read back sync'd ks-repo, so we can compare post-import
        entity_map["ks-repo"] = self.repo_api.read(entity_map["ks-repo"].pulp_href)
        entity_map["ks-content"] = get_content(entity_map["ks-repo"].to_dict())

        # Step 4, exporter
        body = {
            "name": uuid4(),
            "repositories": [entity_map["rpm-repo"].pulp_href, entity_map["ks-repo"].pulp_href],
            "path": "/tmp/{}".format(uuid4()),
        }
        exporter = self.exporter_api.create(body)
        entity_map["exporter-path"] = exporter.path

        # Step 5, export
        export_response = self.exports_api.create(exporter.pulp_href, {})
        export_href = monitor_task(export_response.task).created_resources[0]
        export = self.exports_api.read(export_href)
        filenames = [f for f in list(export.output_file_info.keys()) if f.endswith("tar.gz")]
        entity_map["export-filename"] = filenames[0]

        # Step 6, exporter/repo-cleanup, orphans
        self.exporter_api.delete(exporter.pulp_href)
        self.remote_api.delete(entity_map["rpm-remote"].pulp_href)
        self.remote_api.delete(entity_map["ks-remote"].pulp_href)
        self.repo_api.delete(entity_map["rpm-repo"].pulp_href)
        self.repo_api.delete(entity_map["ks-repo"].pulp_href)
        delete_orphans()

        self.saved_entities = entity_map

    def tearDown(self):
        """Final cleanup (export-files and orphans)."""
        cli_client = cli.Client(self.cfg)
        cmd = ("rm", "-rf", self.saved_entities["exporter-path"])
        cli_client.run(cmd, sudo=True)
        delete_orphans()

    def test_createrepos_import(self):
        """Steps 7-9 from above."""
        existing_repos = self.repo_api.list().count

        # Step 7
        body = {
            "name": uuid4(),
        }
        importer = self.importer_api.create(body)
        self.addCleanup(self.importer_api.delete, importer.pulp_href)

        # Step 8
        # At this point we should be importing into a content-free-zone
        import_response = self.imports_api.create(
            importer.pulp_href,
            {"path": self.saved_entities["export-filename"], "create_repositories": True},
        )
        task_group = monitor_task_group(import_response.task_group)
        # We should have created 1 import and 2 repositories here
        self.assertEqual(3, task_group.completed)

        # Find the repos we just created
        rpm_repo = self.repo_api.list(name=self.saved_entities["rpm-repo"].name).results[0]
        self.addCleanup(self.repo_api.delete, rpm_repo.pulp_href)
        ks_repo = self.repo_api.list(name=self.saved_entities["ks-repo"].name).results[0]
        self.addCleanup(self.repo_api.delete, ks_repo.pulp_href)

        # 9. Inspect the results
        # Step 9a
        self.assertEqual(f"{rpm_repo.pulp_href}versions/1/", rpm_repo.latest_version_href)
        self.assertEqual(f"{ks_repo.pulp_href}versions/1/", ks_repo.latest_version_href)

        # Step 9b
        imported_ks_content = get_content(ks_repo.to_dict())
        orig_dtree = self.saved_entities["ks-content"]["rpm.distribution_tree"][0]
        imported_dtree = imported_ks_content["rpm.distribution_tree"][0]
        for disttree_content_type in ["addons", "checksums", "images", "variants"]:
            self.assertEqual(
                len(orig_dtree[disttree_content_type]), len(imported_dtree[disttree_content_type])
            )

        # Make sure we only created the repos being imported
        self.assertEqual(self.repo_api.list().count, existing_repos + 2)
