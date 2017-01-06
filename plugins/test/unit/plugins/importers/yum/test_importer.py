import os
import shutil
import tempfile

from mongoengine import NotUniqueError
import mock
from pulp.plugins.model import Repository

from pulp_rpm.devel.skip import skip_broken
from pulp_rpm.plugins.importers.yum.importer import YumImporter
import mock_conduits
from pulp_rpm.devel import rpm_support_base
from pulp_rpm.plugins.db import models


@skip_broken
class CustomMetadataTests(rpm_support_base.PulpRPMTests):
    def setUp(self):
        super(CustomMetadataTests, self).setUp()
        self.root_dir = tempfile.mkdtemp(prefix='test-custom-metadata-')
        self.content_dir = os.path.join(self.root_dir, 'content')
        os.makedirs(self.content_dir)

    def tearDown(self):
        super(CustomMetadataTests, self).tearDown()
        shutil.rmtree(self.root_dir)

    def _mock_repo(self, repo_id):
        repo = mock.Mock(spec=Repository)
        repo.id = repo_id
        repo.working_dir = os.path.join(self.root_dir, 'working', repo_id)
        os.makedirs(repo.working_dir)
        return repo

    @mock.patch('pulp_rpm.plugins.importers.yum.importer.associate.associate')
    def test_custom_metadata_import_units(self, mock_associate):
        importer = YumImporter()

        src_repo = self._mock_repo('test-presto-delta-metadata-source')
        dst_repo = self._mock_repo('test-presto-delta-metadata-destination')
        import_unit_conduit = mock_conduits.import_unit_conduit(dst_repo.working_dir)
        config = mock_conduits.plugin_call_config(copy_children=False)

        importer.import_units(src_repo, dst_repo, import_unit_conduit, config)

        mock_associate.assert_called_once_with(src_repo, dst_repo, import_unit_conduit, config,
                                               None)


class GroupTests(rpm_support_base.PulpRPMTests):
    def setUp(self):
        super(GroupTests, self).setUp()
        self.root_dir = tempfile.mkdtemp(prefix='test-custom-metadata-')
        self.content_dir = os.path.join(self.root_dir, 'content')
        os.makedirs(self.content_dir)

    def tearDown(self):
        super(GroupTests, self).tearDown()
        shutil.rmtree(self.root_dir)

    @mock.patch("pulp_rpm.plugins.importers.yum.upload.repo_controller")
    @mock.patch("pulp_rpm.plugins.db.models.PackageGroup.objects")
    @mock.patch("pulp_rpm.plugins.db.models.PackageGroup._get_db")
    @mock.patch("pulp_rpm.plugins.importers.yum.upload.plugin_api")
    def test_foo(self, _plugin_api, _get_db, _objects, _repo_controller):
        _plugin_api.get_unit_model_by_id.return_value = models.PackageGroup
        collection = _get_db.return_value.__getitem__.return_value
        collection.save.side_effect = NotUniqueError()

        existing_unit = _objects.filter.return_value.first.return_value

        repo_id = 'test-upload-unit'
        repo = mock.Mock(spec=Repository)
        repo.id = repo_id
        repo.working_dir = os.path.join(self.root_dir, 'working', repo_id)

        transfer_repo = mock.Mock(repo_obj=repo)

        importer = YumImporter()

        conduit = mock_conduits.import_unit_conduit(repo.working_dir)
        config = mock_conduits.plugin_call_config(copy_children=False)
        unit_key = dict(repo_id=repo_id, package_group_id="foo")
        pkgs = ['a', 'b']
        now = 1234567890.123
        unit_metadata = dict(mandatory_package_names=pkgs, _last_updated=now)
        type_id = "package_group"

        file_path = None
        importer.upload_unit(transfer_repo, type_id, unit_key, unit_metadata,
                             file_path, conduit, config)

        _repo_controller.associate_single_unit.assert_called_once_with(
            repo, existing_unit)
        self.assertEquals(pkgs, existing_unit.mandatory_package_names)
