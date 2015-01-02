import os
import shutil
import tempfile

import mock
from pulp.plugins.model import Repository

from pulp_rpm.plugins.importers.yum.importer import YumImporter
import mock_conduits
from pulp_rpm.devel import rpm_support_base


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
