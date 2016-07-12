import os
import shutil
import stat
import tempfile
import unittest

import mock
from pulp.plugins.config import PluginCallConfiguration
from pulp.plugins.model import Unit

from pulp_rpm.devel.skip import skip_broken
from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.importers.yum.repomd import group
from pulp_rpm.plugins.importers.yum import upload
import model_factory


DATA_DIR = os.path.join(os.path.dirname(__file__), '../../../../data')
XML_FILENAME = 'Fedora-19-comps.xml'


@skip_broken
class UploadDispatchTests(unittest.TestCase):
    """
    Tests the main driver method to ensure that it calls the correct _handle_* method
    for a given type with the correct signature. These tests also ensure the correct
    report is returned.
    """

    def setUp(self):
        super(UploadDispatchTests, self).setUp()

        self.unit_key = object()
        self.metadata = object()
        self.file_path = object()
        self.conduit = object()
        self.config = object()

    @mock.patch('pulp_rpm.plugins.importers.yum.upload._handle_package')
    def test_rpm(self, mock_handle):
        # Test
        report = upload.upload(None, models.RPM.TYPE, self.unit_key, self.metadata,
                               self.file_path, self.conduit, self.config)

        # Verify
        mock_handle.assert_called_once_with(None, models.RPM.TYPE, self.unit_key, self.metadata,
                                            self.file_path, self.conduit, self.config)

        self.assertTrue(report is not None)
        self.assertTrue(report['success_flag'])

    @mock.patch('pulp_rpm.plugins.importers.yum.upload._handle_package')
    def test_srpm(self, mock_handle):
        # Test
        report = upload.upload(None, models.SRPM.TYPE, self.unit_key, self.metadata,
                               self.file_path, self.conduit, self.config)

        # Verify
        mock_handle.assert_called_once_with(None, models.SRPM.TYPE, self.unit_key, self.metadata,
                                            self.file_path, self.conduit, self.config)

        self.assertTrue(report is not None)
        self.assertTrue(report['success_flag'])

    @mock.patch('pulp_rpm.plugins.importers.yum.upload._handle_package')
    def test_drpm(self, mock_handle):
        """Test if upload function choose correct function to handle DRPM."""
        # Test
        report = upload.upload(None, models.DRPM.TYPE, self.unit_key, self.metadata,
                               self.file_path, self.conduit, self.config)

        # Verify
        mock_handle.assert_called_once_with(None, models.DRPM.TYPE, self.unit_key, self.metadata,
                                            self.file_path, self.conduit, self.config)

        self.assertTrue(report is not None)
        self.assertTrue(report['success_flag'])

    @mock.patch('pulp_rpm.plugins.importers.yum.upload._handle_group_category')
    def test_group(self, mock_handle):
        # Test
        report = upload.upload(None, models.PackageGroup.TYPE, self.unit_key, self.metadata,
                               self.file_path, self.conduit, self.config)

        # Verify
        mock_handle.assert_called_once_with(None, models.PackageGroup.TYPE, self.unit_key,
                                            self.metadata, self.file_path, self.conduit,
                                            self.config)

        self.assertTrue(report is not None)
        self.assertTrue(report['success_flag'])

    @mock.patch('pulp_rpm.plugins.importers.yum.upload._handle_group_category')
    def test_category(self, mock_handle):
        # Test
        report = upload.upload(None, models.PackageCategory.TYPE, self.unit_key, self.metadata,
                               self.file_path, self.conduit, self.config)

        # Verify
        mock_handle.assert_called_once_with(None, models.PackageCategory.TYPE, self.unit_key,
                                            self.metadata, self.file_path, self.conduit,
                                            self.config)

        self.assertTrue(report is not None)
        self.assertTrue(report['success_flag'])

    @mock.patch('pulp_rpm.plugins.importers.yum.upload._handle_erratum')
    def test_erratum(self, mock_handle):
        # Test
        report = upload.upload(None, models.Errata.TYPE, self.unit_key, self.metadata,
                               self.file_path, self.conduit, self.config)

        # Verify
        mock_handle.assert_called_once_with(None, models.Errata.TYPE, self.unit_key,
                                            self.metadata, self.file_path, self.conduit,
                                            self.config)

        self.assertTrue(report is not None)
        self.assertTrue(report['success_flag'])

    @mock.patch('pulp_rpm.plugins.importers.yum.upload._handle_yum_metadata_file')
    def test_yum_metadata_file(self, mock_handle):
        # Test
        report = upload.upload(None, models.YumMetadataFile.TYPE, self.unit_key, self.metadata,
                               self.file_path, self.conduit, self.config)

        # Verify
        mock_handle.assert_called_once_with(None, models.YumMetadataFile.TYPE, self.unit_key,
                                            self.metadata, self.file_path, self.conduit,
                                            self.config)

        self.assertTrue(report is not None)
        self.assertTrue(report['success_flag'])

    def test_unsupported(self):
        # Test
        report = upload.upload(None, 'foo', self.unit_key, self.metadata,
                               self.file_path, self.conduit, self.config)

        # Verify
        self.assertTrue(report is not None)
        self.assertFalse(report['success_flag'])
        self.assertTrue('errors' in report['details'])
        self.assertTrue('foo' in report['details']['errors'][0])

    @mock.patch('pulp_rpm.plugins.importers.yum.upload._handle_package')
    def test_model_instantiation_error(self, mock_handle):
        # Setup
        mock_handle.side_effect = upload.ModelInstantiationError()

        # Test
        report = upload.upload(None, models.RPM.TYPE, self.unit_key, self.metadata,
                               self.file_path, self.conduit, self.config)

        # Verify
        self.assertTrue(not report['success_flag'])
        self.assertTrue('errors' in report['details'])
        self.assertTrue('invalid' in report['details']['errors'][0])

    @mock.patch('pulp_rpm.plugins.importers.yum.upload._handle_package')
    def test_store_file_error(self, mock_handle):
        # Setup
        mock_handle.side_effect = upload.StoreFileError()

        # Test
        report = upload.upload(None, models.RPM.TYPE, self.unit_key, self.metadata,
                               self.file_path, self.conduit, self.config)

        # Verify
        self.assertFalse(report['success_flag'])
        self.assertTrue('errors' in report['details'])
        self.assertTrue('storage' in report['details']['errors'][0])

    @mock.patch('pulp_rpm.plugins.importers.yum.upload._handle_package')
    def test_package_metadata_error(self, mock_handle):
        # Setup
        mock_handle.side_effect = upload.PackageMetadataError()

        # Test
        report = upload.upload(None, models.RPM.TYPE, self.unit_key, self.metadata,
                               self.file_path, self.conduit, self.config)

        # Verify
        self.assertFalse(report['success_flag'])
        self.assertTrue('errors' in report['details'])
        self.assertTrue('extracted' in report['details']['errors'][0])

    @mock.patch('pulp_rpm.plugins.importers.yum.upload._handle_package')
    def test_unexpected(self, mock_handle):
        # Setup
        mock_handle.side_effect = Exception()

        # Test
        report = upload.upload(None, models.RPM.TYPE, self.unit_key, self.metadata,
                               self.file_path, self.conduit, self.config)

        # Verify
        self.assertFalse(report['success_flag'])
        self.assertTrue('errors' in report['details'])
        self.assertTrue('unexpected' in report['details']['errors'][0])


@mock.patch('pulp_rpm.plugins.importers.yum.upload.repo_controller')
@mock.patch('pulp_rpm.plugins.importers.yum.upload.plugin_api.get_unit_model_by_id')
@mock.patch('pulp_rpm.plugins.importers.yum.upload.update_fields_inbound')
class TestUploadErratum(unittest.TestCase):
    """
    Tests for uploading erratum.
    """

    def test_handle_with_link(self, m_update, m_model_by_id, m_repo_ctrl):
        """
        Ensure that erratum uploaded without the skip erratum link flag are associated.
        """
        unit_key = {'id': 'test-erratum'}
        metadata = {'a': 'a'}
        mock_repo = mock.MagicMock()
        mock_conduit = mock.MagicMock()
        config = PluginCallConfiguration({}, {})
        m_model_by_id.return_value.objects.filter.return_value.first.return_value = None
        m_unit = m_model_by_id().return_value

        upload._handle_erratum(mock_repo, 'm_type', unit_key, metadata, None,
                               mock_conduit, config)
        m_repo_ctrl.associate_single_unit.assert_called_once_with(mock_repo, m_unit)

    def test_handle_with_no_link(self, m_update, m_model_by_id, m_repo_ctrl):
        """
        Ensure that erratum uploaded with the skip erratum link flag are not associated.
        """
        unit_key = {'id': 'test-erratum'}
        metadata = {'a': 'a'}
        mock_repo = mock.MagicMock()
        mock_conduit = mock.MagicMock()
        config = PluginCallConfiguration(
            {}, {}, override_config={upload.CONFIG_SKIP_ERRATUM_LINK: True})
        upload._handle_erratum(mock_repo, 'm_type', unit_key, metadata, None,
                               mock_conduit, config)
        self.assertFalse(m_repo_ctrl.associate_single_unit.called)

    def test_handle_erratum_same_id(self, m_update, m_model_by_id, m_repo_ctrl):
        """
        Ensure that the merge of errata is initiated if the erratum with the same id already exists.
        """
        unit_key = {'id': 'test-erratum'}
        metadata = {'a': 'a'}
        mock_repo = mock.MagicMock()
        mock_conduit = mock.MagicMock()
        config = PluginCallConfiguration({}, {})
        m_unit = m_model_by_id.return_value.objects.filter.return_value.first.return_value

        upload._handle_erratum(mock_repo, 'm_type', unit_key, metadata, None,
                               mock_conduit, config)
        self.assertEqual(m_unit.merge_errata.call_count, 1)
        m_repo_ctrl.associate_single_unit.assert_called_once_with(mock_repo, m_unit)


@skip_broken
class UploadYumRepoMetadataFileTests(unittest.TestCase):
    def setUp(self):
        super(UploadYumRepoMetadataFileTests, self).setUp()

        self.tmp_dir = tempfile.mkdtemp(prefix='pulp-rpm-upload-tests')
        self.upload_source_filename = os.path.join(self.tmp_dir, 'yum-repo-metadata.source')
        self.upload_dest_filename = os.path.join(self.tmp_dir, 'yum-repo-metadata.dest')
        with open(self.upload_source_filename, 'w') as f:
            f.write('test metadata file')

    def tearDown(self):
        super(UploadYumRepoMetadataFileTests, self).tearDown()

        if os.path.exists(self.tmp_dir):
            shutil.rmtree(self.tmp_dir)

    def test_handle_yum_metadata_file(self):
        # Setup
        unit_key = {'data_type': 'product-id', 'repo_id': 'test-repo'}
        metadata = {'local_path': 'repodata/productid', 'checksum': 'abcdef',
                    'checksumtype': 'sha256'}
        config = PluginCallConfiguration({}, {})
        mock_repo = mock.MagicMock()

        mock_conduit = mock.MagicMock()
        inited_unit = Unit(models.YumMetadataFile.TYPE, unit_key, metadata,
                           self.upload_dest_filename)
        mock_conduit.init_unit.return_value = inited_unit

        # Test
        upload._handle_yum_metadata_file(mock_repo, models.YumMetadataFile.TYPE, unit_key, metadata,
                                         self.upload_source_filename, mock_conduit, config)

        # Verify

        # File was moved correctly
        self.assertTrue(not os.path.exists(self.upload_source_filename))
        self.assertTrue(os.path.exists(self.upload_dest_filename))

        #   Conduit calls
        expected_relative_path = 'test-repo/repodata/productid'
        mock_conduit.init_unit.assert_called_once_with(models.YumMetadataFile.TYPE, unit_key,
                                                       metadata, expected_relative_path)
        mock_conduit.save_unit.assert_called_once()
        saved_unit = mock_conduit.save_unit.call_args[0][0]
        self.assertEqual(inited_unit, saved_unit)

    def test_handle_yum_metadata_file_model_error(self):
        # Setup
        unit_key = {'foo': 'bar'}
        mock_repo = mock.MagicMock()

        # Test
        self.assertRaises(upload.ModelInstantiationError, upload._handle_yum_metadata_file,
                          mock_repo, models.Errata.TYPE, unit_key, {}, None, None, None)

    def test_handle_yum_metadata_file_storage_error(self):
        # Setup
        unit_key = {'data_type': 'product-id', 'repo_id': 'test-repo'}
        metadata = {'local_path': 'repodata/productid'}
        config = PluginCallConfiguration({}, {})
        mock_repo = mock.MagicMock()

        mock_conduit = mock.MagicMock()
        inited_unit = Unit(models.YumMetadataFile.TYPE, unit_key, metadata,
                           '/foo/bar/baz')
        # Test will fail if that directory is writable by the unit test, but I'm willing to
        # take that chance.

        mock_conduit.init_unit.return_value = inited_unit

        # Test
        self.assertRaises(upload.StoreFileError, upload._handle_yum_metadata_file, mock_repo,
                          models.YumMetadataFile.TYPE, unit_key, metadata,
                          self.upload_source_filename, mock_conduit, config)


@skip_broken
class GroupCategoryTests(unittest.TestCase):

    def test_handle_for_group(self):
        # Setup
        unit_key = {'id': 'test-group', 'repo_id': 'test-repo'}
        metadata = {}
        config = PluginCallConfiguration({}, {})
        mock_repo = mock.MagicMock()

        mock_conduit = mock.MagicMock()
        inited_unit = Unit(models.PackageGroup.TYPE, unit_key, metadata, None)
        mock_conduit.init_unit.return_value = inited_unit

        # Test
        upload._handle_group_category(mock_repo, models.PackageGroup.TYPE, unit_key, metadata, None,
                                      mock_conduit, config)

        # Verify
        mock_conduit.init_unit.assert_called_once_with(models.PackageGroup.TYPE, unit_key,
                                                       metadata, None)
        mock_conduit.save_unit.assert_called_once()
        saved_unit = mock_conduit.save_unit.call_args[0][0]
        self.assertEqual(inited_unit, saved_unit)

    def test_handle_for_category(self):
        # Setup
        unit_key = {'id': 'test-category', 'repo_id': 'test-repo'}
        metadata = {}
        config = PluginCallConfiguration({}, {})
        mock_repo = mock.MagicMock()

        mock_conduit = mock.MagicMock()
        inited_unit = Unit(models.PackageCategory.TYPE, unit_key, metadata, None)
        mock_conduit.init_unit.return_value = inited_unit

        # Test
        upload._handle_group_category(mock_repo, models.PackageCategory.TYPE, unit_key, metadata,
                                      None, mock_conduit, config)

        # Verify
        mock_conduit.init_unit.assert_called_once_with(models.PackageCategory.TYPE, unit_key,
                                                       metadata, None)
        mock_conduit.save_unit.assert_called_once()
        saved_unit = mock_conduit.save_unit.call_args[0][0]
        self.assertEqual(inited_unit, saved_unit)

    @mock.patch('pulp_rpm.plugins.importers.yum.upload._get_file_units')
    def test_handle_for_comps(self, mock_file_units):
        # Setup
        self.sample_comps_filename = os.path.join(DATA_DIR, 'simple_repo_comps', XML_FILENAME)
        unit_key = {}
        metadata = {}
        config = PluginCallConfiguration({}, {})
        mock_repo = mock.MagicMock()
        mock_repo.id = 'some_id'
        mock_conduit = mock.MagicMock()

        # Test
        upload._handle_group_category(mock_repo, models.PackageCategory.TYPE, unit_key, metadata,
                                      self.sample_comps_filename, mock_conduit, config)

        # Verify
        self.assertEqual(mock_file_units.call_count, 3)
        group_args = (self.sample_comps_filename, group.process_group_element, group.GROUP_TAG,
                      mock_conduit, mock_repo.id)
        category_args = (self.sample_comps_filename, group.process_category_element,
                         group.CATEGORY_TAG, mock_conduit, mock_repo.id)
        environment_args = (self.sample_comps_filename, group.process_environment_element,
                            group.ENVIRONMENT_TAG, mock_conduit, mock_repo.id)
        self.assertEqual(mock_file_units.call_args_list[0][0], group_args)
        self.assertEqual(mock_file_units.call_args_list[1][0], category_args)
        self.assertEqual(mock_file_units.call_args_list[2][0], environment_args)

    def test_model_error(self):
        # Setup
        unit_key = {'foo': 'bar'}
        mock_repo = mock.MagicMock()

        # Test
        self.assertRaises(upload.ModelInstantiationError, upload._handle_group_category, mock_repo,
                          models.PackageGroup.TYPE, unit_key, {}, None, None, None)

    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.packages.package_list_generator',
                autospec=True)
    def test_get_file_units(self, mock_generator):
        # Setup
        self.sample_comps_filename = os.path.join(DATA_DIR, 'simple_repo_comps', XML_FILENAME)
        mock_repo = mock.MagicMock()
        mock_repo.id = 'some_id'
        mock_conduit = mock.MagicMock()
        mock_process_element = mock.Mock()
        category = tuple(model_factory.category_models(3))
        mock_generator.return_value = category

        # Test
        upload._get_file_units(self.sample_comps_filename, mock_process_element, 'foo',
                               mock_conduit, mock_repo.id)

        # Verify
        self.assertEqual(mock_generator.call_count, 1)

        for model in category:
            mock_conduit.init_unit.assert_any_call(model.TYPE, model.unit_key, model.metadata, None)
            mock_conduit.save_unit.assert_any_call(mock_conduit.init_unit.return_value)
        self.assertEqual(mock_conduit.save_unit.call_count, 3)


@skip_broken
class UploadPackageTests(unittest.TestCase):
    def setUp(self):
        super(UploadPackageTests, self).setUp()

        sample_rpm_filename = os.path.join(DATA_DIR, 'walrus-5.21-1.noarch.rpm')

        self.tmp_dir = tempfile.mkdtemp(prefix='pulp-rpm-upload-tests')

        # The import moves the source into the destination, so copy the RPM out of the
        # git repository so we don't go breaking things.
        shutil.copy(sample_rpm_filename, self.tmp_dir)

        self.upload_src_filename = os.path.join(self.tmp_dir,
                                                os.path.basename(sample_rpm_filename))
        self.upload_dest_filename = os.path.join(self.tmp_dir, 'rpm-uploaded.rpm')

    def tearDown(self):
        super(UploadPackageTests, self).tearDown()

        if os.path.exists(self.tmp_dir):
            shutil.rmtree(self.tmp_dir)

    @mock.patch('pulp_rpm.plugins.importers.yum.upload.purge.remove_unit_duplicate_nevra')
    @mock.patch('pulp_rpm.plugins.importers.yum.upload._generate_rpm_data')
    def test_handle_package(self, mock_generate, mock_nevra):
        # Setup
        unit_key = {
            'name': 'walrus',
            'epoch': '1',
            'version': '5.21',
            'release': '1',
            'arch': 'noarch',
            'checksumtype': 'sha256',
            'checksum': 'e837a635cc99f967a70f34b268baa52e0f412c1502e08e924ff5b09f1f9573f2',
        }
        metadata = {
            'filename': ''
        }
        mock_generate.return_value = unit_key, metadata

        user_unit_key = {'version': '100'}
        user_metadata = {'extra-meta': 'e'}
        config = PluginCallConfiguration({}, {})
        mock_repo = mock.MagicMock()

        mock_conduit = mock.MagicMock()
        inited_unit = Unit(models.RPM.TYPE, unit_key, metadata, self.upload_dest_filename)
        mock_conduit.init_unit.return_value = inited_unit

        # Test
        upload._handle_package(mock_repo, models.RPM.TYPE, user_unit_key, user_metadata,
                               self.upload_src_filename, mock_conduit, config)

        # Verify

        # File was moved as part of the import
        self.assertTrue(os.path.exists(self.upload_dest_filename))
        self.assertTrue(not os.path.exists(self.upload_src_filename))

        #   Mock calls
        mock_generate.assert_called_once_with(models.RPM.TYPE,
                                              self.upload_src_filename,
                                              user_metadata)

        full_unit_key = dict(unit_key)
        full_metadata = dict(metadata)

        full_unit_key.update(user_unit_key)
        full_metadata.update(user_metadata)
        expected_relative_path = models.RPM(metadata=full_metadata, **full_unit_key).relative_path

        mock_conduit.init_unit.assert_called_once_with(models.RPM.TYPE, full_unit_key,
                                                       full_metadata, expected_relative_path)

        mock_nevra.assert_called_once_with(full_unit_key, models.RPM.TYPE, mock_repo.id)

        mock_conduit.save_unit.assert_called_once()
        saved_unit = mock_conduit.save_unit.call_args[0][0]
        self.assertEqual(inited_unit, saved_unit)

    @mock.patch('pulp_rpm.plugins.importers.yum.upload._generate_rpm_data')
    def test_handle_metadata_error(self, mock_generate):
        # Setup
        class FooException(Exception):
            pass
        mock_generate.side_effect = FooException()
        mock_repo = mock.MagicMock()

        # Test - Ensure we haven't blindly masked an exception
        self.assertRaises(FooException, upload._handle_package, mock_repo, None, None,
                          None, None, None, None)

    @mock.patch('pulp_rpm.plugins.importers.yum.upload._generate_rpm_data')
    def test_handle_model_instantiation_error(self, mock_generate):
        # Setup
        mock_generate.return_value = {}, {}  # incomplete unit key, will error
        mock_repo = mock.MagicMock()

        # Test
        self.assertRaises(upload.ModelInstantiationError, upload._handle_package, mock_repo,
                          models.RPM.TYPE, None, None, None, None, None)

    @mock.patch('pulp_rpm.plugins.importers.yum.upload._generate_rpm_data')
    def test_handle_storage_error(self, mock_generate):
        # Setup
        unit_key = {
            'name': 'walrus',
            'epoch': '1',
            'version': '5.21',
            'release': '1',
            'arch': 'noarch',
            'checksumtype': 'sha256',
            'checksum': 'e837a635cc99f967a70f34b268baa52e0f412c1502e08e924ff5b09f1f9573f2',
        }
        metadata = {
            'filename': ''
        }
        mock_generate.return_value = unit_key, metadata
        config = PluginCallConfiguration({}, {})
        mock_repo = mock.MagicMock()

        mock_conduit = mock.MagicMock()
        mock_conduit.init_unit.side_effect = IOError()

        # Test
        self.assertRaises(upload.StoreFileError, upload._handle_package, mock_repo, models.RPM.TYPE,
                          unit_key, metadata, self.upload_src_filename, mock_conduit, config)

    def test_generate_rpm_data(self):
        # Test
        unit_key, metadata = upload._generate_rpm_data(models.RPM.TYPE,
                                                       self.upload_src_filename, {})

        # Verify
        self.assertEqual(unit_key['name'], 'walrus')
        self.assertEqual(unit_key['epoch'], '0')
        self.assertEqual(unit_key['version'], '5.21')
        self.assertEqual(unit_key['release'], '1')
        self.assertEqual(unit_key['arch'], 'noarch')
        self.assertEqual(unit_key['checksum'],
                         'e837a635cc99f967a70f34b268baa52e0f412c1502e08e924ff5b09f1f9573f2')
        self.assertEqual(unit_key['checksumtype'], 'sha256')

        self.assertEqual(metadata['buildhost'], 'smqe-ws15')
        self.assertEqual(metadata['description'], 'A dummy package of walrus')
        self.assertEqual(metadata['filename'], 'walrus-5.21-1.noarch.rpm')
        self.assertEqual(metadata['license'], 'GPLv2')
        self.assertEqual(metadata['relativepath'], 'walrus-5.21-1.noarch.rpm')
        self.assertEqual(metadata['vendor'], None)
        time_val = os.stat(self.upload_src_filename)[stat.ST_MTIME]
        self.assertEqual(metadata['build_time'], 1331831368)
        self.assertEqual(metadata['time'], time_val)

    def test_generate_rpm_data_user_checksum(self):
        # Test
        unit_key, metadata = upload._generate_rpm_data(models.RPM.TYPE,
                                                       self.upload_src_filename,
                                                       {'checksum_type': 'sha1'})

        # Verify
        self.assertEqual(unit_key['name'], 'walrus')
        self.assertEqual(unit_key['epoch'], '0')
        self.assertEqual(unit_key['version'], '5.21')
        self.assertEqual(unit_key['release'], '1')
        self.assertEqual(unit_key['arch'], 'noarch')
        self.assertEqual(unit_key['checksum'], '8dea2b64fc52062d79d5f96ba6415bffae4d2153')
        self.assertEqual(unit_key['checksumtype'], 'sha1')

        self.assertEqual(metadata['buildhost'], 'smqe-ws15')
        self.assertEqual(metadata['description'], 'A dummy package of walrus')
        self.assertEqual(metadata['filename'], 'walrus-5.21-1.noarch.rpm')
        self.assertEqual(metadata['license'], 'GPLv2')
        self.assertEqual(metadata['relativepath'], 'walrus-5.21-1.noarch.rpm')
        self.assertEqual(metadata['vendor'], None)

    def test_generate_rpm_data_user_checksum_null(self):
        # Test
        unit_key, metadata = upload._generate_rpm_data(models.RPM.TYPE,
                                                       self.upload_src_filename,
                                                       {'checksum_type': None})

        # Verify
        self.assertEqual(unit_key['name'], 'walrus')
        self.assertEqual(unit_key['epoch'], '0')
        self.assertEqual(unit_key['version'], '5.21')
        self.assertEqual(unit_key['release'], '1')
        self.assertEqual(unit_key['arch'], 'noarch')
        self.assertEqual(unit_key['checksum'],
                         'e837a635cc99f967a70f34b268baa52e0f412c1502e08e924ff5b09f1f9573f2')
        self.assertEqual(unit_key['checksumtype'], 'sha256')

        self.assertEqual(metadata['buildhost'], 'smqe-ws15')
        self.assertEqual(metadata['description'], 'A dummy package of walrus')
        self.assertEqual(metadata['filename'], 'walrus-5.21-1.noarch.rpm')
        self.assertEqual(metadata['license'], 'GPLv2')
        self.assertEqual(metadata['relativepath'], 'walrus-5.21-1.noarch.rpm')
        self.assertEqual(metadata['vendor'], None)

    def test__generate_rpm_data_sanitizes_checksum_type(self):
        """
        Assert that _generate_rpm_data() sanitizes the checksum type.
        """
        unit_key, metadata = upload._generate_rpm_data(models.RPM.TYPE,
                                                       self.upload_src_filename,
                                                       {'checksum_type': 'sha'})

        self.assertEqual(unit_key['name'], 'walrus')
        self.assertEqual(unit_key['epoch'], '0')
        self.assertEqual(unit_key['version'], '5.21')
        self.assertEqual(unit_key['release'], '1')
        self.assertEqual(unit_key['arch'], 'noarch')
        self.assertEqual(unit_key['checksum'], '8dea2b64fc52062d79d5f96ba6415bffae4d2153')
        # The checksumtype is sha1, even though it was set to sha because it was sanitized.
        self.assertEqual(unit_key['checksumtype'], 'sha1')

        self.assertEqual(metadata['buildhost'], 'smqe-ws15')
        self.assertEqual(metadata['description'], 'A dummy package of walrus')
        self.assertEqual(metadata['filename'], 'walrus-5.21-1.noarch.rpm')
        self.assertEqual(metadata['license'], 'GPLv2')
        self.assertEqual(metadata['relativepath'], 'walrus-5.21-1.noarch.rpm')
        self.assertEqual(metadata['vendor'], None)


class UploadDRPMPackageTests(unittest.TestCase):
    """
    tests upload of DRPM package
    """
    def setUp(self):
        super(UploadDRPMPackageTests, self).setUp()

        sample_drpm_filename = os.path.join(DATA_DIR,
                                            'yum-3.2.29-20.fc16_from_el6_3.4.3-8.fc16.noarch.drpm')

        self.tmp_dir = tempfile.mkdtemp(prefix='pulp-rpm-upload-tests')

        # The import moves the source into the destination, so copy the DRPM out of the
        # git repository so we don't go breaking things.
        shutil.copy(sample_drpm_filename, self.tmp_dir)

        self.upload_src_filename = os.path.join(self.tmp_dir,
                                                os.path.basename(sample_drpm_filename))
        self.upload_dest_filename = os.path.join(self.tmp_dir, 'rpm-uploaded.drpm')

    def tearDown(self):
        super(UploadDRPMPackageTests, self).tearDown()

        if os.path.exists(self.tmp_dir):
            shutil.rmtree(self.tmp_dir)

    def test_extract_drpm_data(self):
        """
        Test correctness of DRPM metadata extraction.
        """
        # Test
        drpm_data = upload._extract_drpm_data(self.upload_src_filename)

        # Verify
        self.assertEqual(drpm_data['oldrelease'], '20.fc16_from_el6')
        self.assertEqual(drpm_data['sequence'], (
            'yum-3.2.29-20.fc16_from_el6-4d1beb61671e5cd33b731e1807e6bc7821114132124212122242121212'
            '42421212724212121212124242121212b427212121230cd2109d210ec210bc210ab210de110ae110fd110c'
            'd110ec1108c110db110ab110fa110ca1109a110b9110a8110f710c710e6108610d510a510f4109410d310a'
            '310f2109210e11'))
        self.assertEqual(drpm_data['oldepoch'], '0')
        self.assertEqual(drpm_data['oldversion'], '3.2.29')
        self.assertEqual(drpm_data['filename'],
                         'drpms/yum-3.2.29-20.fc16_from_el6_3.4.3-8.fc16.noarch.drpm')
        self.assertEqual(drpm_data['new_package'], 'yum')
        self.assertEqual(drpm_data['epoch'], '0')
        self.assertEqual(drpm_data['version'], '3.4.3')
        self.assertEqual(drpm_data['signing_key'], None)
        self.assertEqual(drpm_data['release'], '8.fc16')
        self.assertEqual(drpm_data['arch'], 'noarch')
        self.assertEqual(drpm_data['size'], 353265)


class TestUpdateProvidesRequires(unittest.TestCase):
    # a snippet from repodata primary xml for a package
    # this snippet has been truncated to only provide the tags needed to test
    PRIMARY_EXCERPT = '''
<package type="rpm">
  <name>shark</name>
  <arch>noarch</arch>
  <version epoch="0" rel="1" ver="0.1" />
  <checksum pkgid="YES"
  type="sha256">951e0eacf3e6e6102b10acb2e689243b5866ec2c7720e783749dbd32f4a69ab3</checksum>
  <summary>A dummy package of shark</summary>
  <description>A dummy package of shark</description>
  <packager />
  <url>http://tstrachota.fedorapeople.org</url>
  <time build="1331831369" file="1331832459" />
  <size archive="296" installed="42" package="2441" />
  <location href="fixme/shark-0.1-1.noarch.rpm" />
  <format>
    <rpm:license>GPLv2</rpm:license>
    <rpm:vendor />
    <rpm:group>Internet/Applications</rpm:group>
    <rpm:buildhost>smqe-ws15</rpm:buildhost>
    <rpm:sourcerpm>shark-0.1-1.src.rpm</rpm:sourcerpm>
    <rpm:header-range end="2289" start="872" />
    <rpm:provides>
      <rpm:entry epoch="0" flags="EQ" name="shark" rel="1" ver="0.1" />
    </rpm:provides>
    <rpm:requires>
      <rpm:entry name="shark" flags="EQ" epoch="0" ver="0.1" rel="1"/>
      <rpm:entry name="walrus" flags="EQ" epoch="0" ver="5.21" rel="1"/>
    </rpm:requires>
  </format>
</package>
    '''
    OTHER_EXCERPT = '''
<package arch="noarch" name="shark"
    pkgid="951e0eacf3e6e6102b10acb2e689243b5866ec2c7720e783749dbd32f4a69ab3">
    <version epoch="0" rel="1" ver="0.1" />
</package>'''
    FILELISTS_EXCERPT = '''
<package arch="noarch" name="shark"
    pkgid="951e0eacf3e6e6102b10acb2e689243b5866ec2c7720e783749dbd32f4a69ab3">
    <version epoch="0" rel="1" ver="0.1" />
    <file>/tmp/shark.txt</file>
</package>'''

    def setUp(self):
        self.unit = models.RPM()
        self.unit.repodata['primary'] = self.PRIMARY_EXCERPT
        self.unit.repodata['filelists'] = self.FILELISTS_EXCERPT
        self.unit.repodata['other'] = self.OTHER_EXCERPT

    def test_update_provides_requires(self):
        upload._update_provides_requires(self.unit)
        self.assertEqual(len(self.unit.provides), 1)
        self.assertEqual(len(self.unit.requires), 2)
