import os
import pickle
import shutil
import tempfile

import mock
from pulp.plugins.model import Repository
from pulp.server.db.model.criteria import UnitAssociationCriteria

from pulp_rpm.plugins.importers.yum.importer import YumImporter
from pulp_rpm.common.ids import TYPE_ID_YUM_REPO_METADATA_FILE
import http_static_test_server
import mock_conduits
from pulp_rpm.devel import rpm_support_base


def relative_path_to_data_dir():
    """
    Determine the relative path the server data directory.
    :return: relative path to the data directory.
    :rtype: str
    :raise RuntimeError: when the path cannot be determined.
    """
    potential_data_dir = 'pulp_rpm/plugins/test/data/'

    while potential_data_dir:

        if os.path.exists(potential_data_dir):
            return potential_data_dir

        potential_data_dir = potential_data_dir.split('/', 1)[1]

    raise RuntimeError('Cannot determine data directory')


def full_path_to_data_dir():
    """
    Determine the full path the server data directory.
    :return: full path to the data directory.
    :rtype: str
    :raise RuntimeError: when the path cannot be determined.
    """
    current_dir = os.getcwd()
    relative_path = relative_path_to_data_dir()
    return os.path.join(current_dir, relative_path)


TEST_DRPM_REPO_FEED = 'http://localhost:8088/%s/test_drpm_repo/published/test_drpm_repo/' % \
    relative_path_to_data_dir()




class CustomMetadataTests(rpm_support_base.PulpRPMTests):

    @classmethod
    def setUpClass(cls):
        super(CustomMetadataTests, cls).setUpClass()
        cls.server = http_static_test_server.HTTPStaticTestServer()
        cls.server.start()

    @classmethod
    def tearDownClass(cls):
        super(CustomMetadataTests, cls).tearDownClass()
        cls.server.stop()
        cls.server = None

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

    def _test_drpm_repo_units(self):
        data_dir_path = full_path_to_data_dir()
        pickle_file = os.path.join(data_dir_path, 'test_drpm_repo', 'pickled_units')
        units = pickle.load(open(pickle_file))
        for u in units:
            u.storage_path = os.path.join(data_dir_path, u.storage_path)
        return units

    # -- custom metadata tests -------------------------------------------------

    def test_custom_metadata_import_units(self):
        importer = YumImporter()

        src_repo = self._mock_repo('test-presto-delta-metadata-source')
        dst_repo = self._mock_repo('test-presto-delta-metadata-destination')
        source_units = self._test_drpm_repo_units()
        import_unit_conduit = mock_conduits.import_unit_conduit(dst_repo.working_dir, source_units=source_units)
        config = mock_conduits.plugin_call_config(copy_children=False)

        importer.import_units(src_repo, dst_repo, import_unit_conduit, config)

        # make sure the metadata unit was imported
        criteria = UnitAssociationCriteria(type_ids=[TYPE_ID_YUM_REPO_METADATA_FILE])
        metadata_units = import_unit_conduit.get_units(criteria)

        self.assertEqual(len(metadata_units), 1)

        unit = metadata_units[0]

        self.assertEqual(unit.type_id, TYPE_ID_YUM_REPO_METADATA_FILE)
        self.assertEqual(unit.unit_key['data_type'], 'prestodelta')

        # make sure the unit was uniquely copied
        prestodelta_path = os.path.join(dst_repo.working_dir, dst_repo.id, 'prestodelta.xml.gz')
        self.assertTrue(os.path.exists(prestodelta_path), prestodelta_path)

