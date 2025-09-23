"""
Tests PulpImporter and PulpImport functionality.

NOTE: assumes ALLOWED_EXPORT_PATHS and ALLOWED_IMPORT_PATHS settings contain "/tmp" - all tests
will fail if this is not the case.
"""

import uuid
import pytest

from collections import namedtuple

from pulp_rpm.tests.functional.constants import RPM_KICKSTART_FIXTURE_URL, RPM_UNSIGNED_FIXTURE_URL

from pulpcore.client.pulp_rpm import RpmRepositorySyncURL

NUM_REPOS = 2

ExportFileInfo = namedtuple("ExportFileInfo", "output_file_info")


@pytest.fixture
def import_export_repositories(
    rpm_repository_api,
    rpm_repository_factory,
    rpm_rpmremote_factory,
    monitor_task,
):
    """Create and sync a number of repositories to be exported."""

    def _import_export_repositories(
        import_repos=None, export_repos=None, url=RPM_UNSIGNED_FIXTURE_URL
    ):
        if import_repos or export_repos:
            # repositories were initialized by the caller
            return import_repos, export_repos

        import_repos = []
        export_repos = []
        for r in range(NUM_REPOS):
            import_repo = rpm_repository_factory()
            export_repo = rpm_repository_factory()

            remote = rpm_rpmremote_factory(url=url)
            repository_sync_data = RpmRepositorySyncURL(remote=remote.pulp_href)
            sync_response = rpm_repository_api.sync(export_repo.pulp_href, repository_sync_data)
            monitor_task(sync_response.task)

            # remember it
            import_repo = rpm_repository_api.read(import_repo.pulp_href)
            export_repo = rpm_repository_api.read(export_repo.pulp_href)
            export_repos.append(export_repo)
            import_repos.append(import_repo)
        return import_repos, export_repos

    return _import_export_repositories


@pytest.fixture
def create_exporter(gen_object_with_cleanup, pulpcore_bindings, import_export_repositories):
    def _create_exporter(import_repos=None, export_repos=None, url=RPM_UNSIGNED_FIXTURE_URL):
        if not export_repos:
            _, export_repos = import_export_repositories(import_repos, export_repos, url=url)

        body = {
            "name": str(uuid.uuid4()),
            "repositories": [r.pulp_href for r in export_repos],
            "path": f"/tmp/{uuid.uuid4()}/",
        }
        exporter = gen_object_with_cleanup(pulpcore_bindings.ExportersPulpApi, body)
        return exporter

    return _create_exporter


@pytest.fixture
def create_export(pulpcore_bindings, create_exporter, monitor_task):
    def _create_export(
        import_repos=None, export_repos=None, url=RPM_UNSIGNED_FIXTURE_URL, exporter=None
    ):
        if not exporter:
            exporter = create_exporter(import_repos, export_repos, url=url)

        export_response = pulpcore_bindings.ExportersPulpExportsApi.create(exporter.pulp_href, {})
        export_href = monitor_task(export_response.task).created_resources[0]
        export = pulpcore_bindings.ExportersPulpExportsApi.read(export_href)
        return export

    return _create_export


@pytest.fixture
def create_chunked_export(pulpcore_bindings, create_exporter, monitor_task):
    def _create_chunked_export(import_repos, export_repos, url=RPM_UNSIGNED_FIXTURE_URL):
        exporter = create_exporter(import_repos, export_repos, url=url)
        export_response = pulpcore_bindings.ExportersPulpExportsApi.create(
            exporter.pulp_href, {"chunk_size": "5KB"}
        )
        export_href = monitor_task(export_response.task).created_resources[0]
        export = pulpcore_bindings.ExportersPulpExportsApi.read(export_href)
        return export

    return _create_chunked_export


@pytest.fixture
def pulp_importer_factory(gen_object_with_cleanup, import_export_repositories, pulpcore_bindings):
    def _pulp_importer_factory(
        import_repos=None,
        exported_repos=None,
        name=None,
        mapping=None,
        url=RPM_UNSIGNED_FIXTURE_URL,
    ):
        """Create an importer."""
        _import_repos, _exported_repos = import_export_repositories(
            import_repos, exported_repos, url=url
        )
        if not name:
            name = str(uuid.uuid4())

        if not mapping:
            mapping = {}
            if not import_repos:
                import_repos = _import_repos
            if not exported_repos:
                exported_repos = _exported_repos

            for idx, repo in enumerate(exported_repos):
                mapping[repo.name] = import_repos[idx].name

        body = {
            "name": name,
            "repo_mapping": mapping,
        }

        importer = gen_object_with_cleanup(pulpcore_bindings.ImportersPulpApi, body)

        return importer

    return _pulp_importer_factory


@pytest.fixture
def perform_import(
    create_chunked_export,
    create_export,
    pulpcore_bindings,
    monitor_task_group,
    import_export_repositories,
):
    def _perform_import(
        importer, import_repos=None, export_repos=None, chunked=False, an_export=None, body=None
    ):
        """Perform an import with importer."""
        if body is None:
            body = {}

        if not an_export:
            if not (import_repos or export_repos):
                import_repos, export_repos = import_export_repositories()

            an_export = (
                create_chunked_export(import_repos, export_repos)
                if chunked
                else create_export(import_repos, export_repos)
            )

        if chunked:
            filenames = [f for f in list(an_export.output_file_info.keys()) if f.endswith("json")]
            if "toc" not in body:
                body["toc"] = filenames[0]
        else:
            filenames = [
                f
                for f in list(an_export.output_file_info.keys())
                if f.endswith("tar") or f.endswith(".tar.gz")
            ]
            if "path" not in body:
                body["path"] = filenames[0]

        import_response = pulpcore_bindings.ImportersPulpImportsApi.create(importer.pulp_href, body)
        task_group = monitor_task_group(import_response.task_group)

        return task_group

    return _perform_import


def test_import(
    pulp_importer_factory, import_export_repositories, perform_import, rpm_repository_api
):
    """Test an import."""
    import_repos, exported_repos = import_export_repositories()
    importer = pulp_importer_factory(import_repos, exported_repos)
    task_group = perform_import(importer, import_repos, exported_repos, chunked=True)
    assert (len(import_repos) + 1) == task_group.completed

    for repo in import_repos:
        repo = rpm_repository_api.read(repo.pulp_href)
        assert f"{repo.pulp_href}versions/1/" == repo.latest_version_href


def test_double_import(
    pulp_importer_factory,
    pulpcore_bindings,
    import_export_repositories,
    rpm_repository_api,
    perform_import,
):
    """Test two imports of our export."""
    import_repos, exported_repos = import_export_repositories()

    importer = pulp_importer_factory(import_repos, exported_repos)
    perform_import(importer, import_repos, exported_repos)
    perform_import(importer, import_repos, exported_repos)

    imports = pulpcore_bindings.ImportersPulpImportsApi.list(importer.pulp_href).results
    assert len(imports) == 2

    for repo in import_repos:
        repo = rpm_repository_api.read(repo.pulp_href)
        # still only one version as pulp won't create a new version if nothing changed
        assert f"{repo.pulp_href}versions/1/" == repo.latest_version_href


def test_distribution_tree_import(
    import_export_repositories,
    pulp_importer_factory,
    rpm_repository_api,
    rpm_content_distribution_trees_api,
    perform_import,
):
    """Tests for PulpImporter and PulpImport for repos with DistributionTrees."""
    import_repos, exported_repos = import_export_repositories(url=RPM_KICKSTART_FIXTURE_URL)
    importer = pulp_importer_factory(import_repos, exported_repos, url=RPM_UNSIGNED_FIXTURE_URL)
    task_group = perform_import(importer, import_repos, exported_repos)
    assert (len(import_repos) + 1) == task_group.completed

    for repo in import_repos:
        repo = rpm_repository_api.read(repo.pulp_href)
        assert f"{repo.pulp_href}versions/1/" == repo.latest_version_href

        trees = rpm_content_distribution_trees_api.list(repository_version=repo.latest_version_href)
        assert trees.count == 1


def test_clean_import(
    rpm_repository_api,
    import_export_repositories,
    create_export,
    pulp_importer_factory,
    monitor_task,
    pulpcore_bindings,
    perform_import,
):
    """Test an import into an empty instance."""
    # By the time we get here, setUpClass() has created repos and an export for us
    # Find the export file, create the importer, delete repos/export, and then let
    # the import happen
    import_repos, exported_repos = import_export_repositories()
    export = create_export(import_repos, exported_repos)
    filenames = [
        f
        for f in list(export.output_file_info.keys())
        if f.endswith("tar") or f.endswith(".tar.gz")
    ]
    importer = pulp_importer_factory(import_repos, exported_repos)

    an_export = ExportFileInfo(export.output_file_info)

    for repo in exported_repos:
        monitor_task(rpm_repository_api.delete(repo.pulp_href).task)
    monitor_task(pulpcore_bindings.OrphansCleanupApi.cleanup({"orphan_protection_time": 0}).task)

    existing_repos = rpm_repository_api.list().count
    # At this point we should be importing into a content-free-zone
    task_group = perform_import(importer, an_export=an_export, body={"path": filenames[0]})
    assert len(import_repos) + 1 == task_group.completed

    for repo in import_repos:
        repo = rpm_repository_api.read(repo.pulp_href)
        assert f"{repo.pulp_href}versions/1/" == repo.latest_version_href
    # We should have the same number of repositories, post-import, than however many we had
    # post-removal of the export-repos
    assert rpm_repository_api.list().count == existing_repos


def test_create_missing_repos(
    init_and_sync,
    rpm_rpmremote_api,
    rpm_repository_api,
    rpm_content_distribution_trees_api,
    monitor_task,
    pulpcore_bindings,
    gen_object_with_cleanup,
    monitor_task_group,
    add_to_cleanup,
):
    """
    Tests for PulpImporter and create-missing-repos.

    1. Create a dist-tree remote and a synced repository
    2. Create an exporter
    3. Export the repos, remember the export-file
    4. post-export-cleanup
       a. delete repos
       b. delete exporter
       c. orphan cleanup
    5. create importer
    6. import the export, create_repos=True
    7. Inspect the results
       a. Only 2 new repos exist
       b. dist-tree-repo has expected addon/variant/etc
    """
    entity_map = {}

    # Step 1, sync repositories
    entity_map["rpm-repo"], entity_map["rpm-remote"] = init_and_sync(policy="immediate")
    entity_map["ks-repo"], entity_map["ks-remote"] = init_and_sync(
        url=RPM_KICKSTART_FIXTURE_URL, policy="immediate"
    )

    entity_map["ks-content"] = rpm_content_distribution_trees_api.list(
        repository_version=entity_map["ks-repo"].latest_version_href
    ).results

    # Step 2, exporter
    body = {
        "name": str(uuid.uuid4()),
        "repositories": [entity_map["rpm-repo"].pulp_href, entity_map["ks-repo"].pulp_href],
        "path": f"/tmp/{uuid.uuid4()}/",
    }
    exporter = gen_object_with_cleanup(pulpcore_bindings.ExportersPulpApi, body)
    entity_map["exporter-path"] = exporter.path

    # Step 3, export
    export_response = pulpcore_bindings.ExportersPulpExportsApi.create(exporter.pulp_href, {})
    export_href = monitor_task(export_response.task).created_resources[0]
    export = pulpcore_bindings.ExportersPulpExportsApi.read(export_href)
    filenames = [
        f
        for f in list(export.output_file_info.keys())
        if f.endswith("tar") or f.endswith(".tar.gz")
    ]
    entity_map["export-filename"] = filenames[0]

    assert len(exporter.repositories) == len(export.exported_resources)
    assert export.output_file_info is not None

    for an_export_filename in export.output_file_info.keys():
        assert "//" not in an_export_filename

    # Step 4, exporter/repo-cleanup, orphans
    pulpcore_bindings.ExportersPulpApi.delete(exporter.pulp_href)
    rpm_rpmremote_api.delete(entity_map["rpm-remote"].pulp_href)
    rpm_rpmremote_api.delete(entity_map["ks-remote"].pulp_href)
    rpm_repository_api.delete(entity_map["rpm-repo"].pulp_href)
    rpm_repository_api.delete(entity_map["ks-repo"].pulp_href)
    monitor_task(pulpcore_bindings.OrphansCleanupApi.cleanup({"orphan_protection_time": 0}).task)

    saved_entities = entity_map

    """Steps 5-7 from above."""
    existing_repos = rpm_repository_api.list().count

    # Step 5
    body = {
        "name": str(uuid.uuid4()),
    }
    importer = gen_object_with_cleanup(pulpcore_bindings.ImportersPulpApi, body)

    # Step 6
    # At this point we should be importing into a content-free-zone
    import_response = pulpcore_bindings.ImportersPulpImportsApi.create(
        importer.pulp_href,
        {"path": saved_entities["export-filename"], "create_repositories": True},
    )
    task_group = monitor_task_group(import_response.task_group)
    # We should have created 1 import and 2 repositories here
    assert 3 == task_group.completed

    # Find the repos we just created
    rpm_repo = rpm_repository_api.list(name=saved_entities["rpm-repo"].name).results[0]
    ks_repo = rpm_repository_api.list(name=saved_entities["ks-repo"].name).results[0]
    add_to_cleanup(rpm_repository_api, rpm_repo.pulp_href)
    add_to_cleanup(rpm_repository_api, ks_repo.pulp_href)

    # 7. Inspect the results
    # Step 7a
    assert f"{rpm_repo.pulp_href}versions/1/" == rpm_repo.latest_version_href
    assert f"{ks_repo.pulp_href}versions/1/" == ks_repo.latest_version_href

    # Step 7b
    imported_ks_content = rpm_content_distribution_trees_api.list(
        repository_version=ks_repo.latest_version_href
    ).results
    orig_dtree = saved_entities["ks-content"][0].to_dict()
    imported_dtree = imported_ks_content[0].to_dict()
    for disttree_content_type in ["addons", "checksums", "images", "variants"]:
        assert len(orig_dtree[disttree_content_type]) == len(imported_dtree[disttree_content_type])

    # Make sure we only created the repos being imported
    assert rpm_repository_api.list().count == existing_repos + 2
