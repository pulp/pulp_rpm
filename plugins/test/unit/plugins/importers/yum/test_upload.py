import os
import shutil
import tempfile
import unittest

import mock
from pulp.plugins.config import PluginCallConfiguration
from pulp.plugins.model import Unit

from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.importers.yum.repomd import packages, updateinfo
from pulp_rpm.plugins.importers.yum import upload


DATA_DIR = os.path.join(os.path.dirname(__file__), '../../../../data')


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
        mock_handle.assert_called_once_with(models.RPM.TYPE, self.unit_key, self.metadata,
                                            self.file_path, self.conduit, self.config)

        self.assertTrue(report is not None)
        self.assertTrue(report['success_flag'])

    @mock.patch('pulp_rpm.plugins.importers.yum.upload._handle_package')
    def test_srpm(self, mock_handle):
        # Test
        report = upload.upload(None, models.SRPM.TYPE, self.unit_key, self.metadata,
                               self.file_path, self.conduit, self.config)

        # Verify
        mock_handle.assert_called_once_with(models.SRPM.TYPE, self.unit_key, self.metadata,
                                            self.file_path, self.conduit, self.config)

        self.assertTrue(report is not None)
        self.assertTrue(report['success_flag'])

    @mock.patch('pulp_rpm.plugins.importers.yum.upload._handle_group_category')
    def test_group(self, mock_handle):
        # Test
        report = upload.upload(None, models.PackageGroup.TYPE, self.unit_key, self.metadata,
                               self.file_path, self.conduit, self.config)

        # Verify
        mock_handle.assert_called_once_with(models.PackageGroup.TYPE, self.unit_key,
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
        mock_handle.assert_called_once_with(models.PackageCategory.TYPE, self.unit_key,
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
        mock_handle.assert_called_once_with(models.Errata.TYPE, self.unit_key,
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
        mock_handle.assert_called_once_with(models.YumMetadataFile.TYPE, self.unit_key,
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


class UploadErratumTests(unittest.TestCase):

    @mock.patch('pulp_rpm.plugins.importers.yum.upload._link_errata_to_rpms')
    def test_handle_erratum_with_link(self, mock_link):
        # Setup
        unit_key = {'id': 'test-erratum'}
        metadata = {'a': 'a'}
        config = PluginCallConfiguration({}, {})

        mock_conduit = mock.MagicMock()
        inited_unit = Unit(models.Errata.TYPE, unit_key, metadata, None)
        saved_unit = Unit(models.Errata.TYPE, unit_key, metadata, None)
        saved_unit.id = 'ihaveanidnow'
        mock_conduit.init_unit.return_value = inited_unit
        mock_conduit.save_unit.return_value = saved_unit

        # Test
        upload._handle_erratum(models.Errata.TYPE, unit_key, metadata, None,
                               mock_conduit, config)

        # Verify
        mock_conduit.init_unit.assert_called_once_with(models.Errata.TYPE, unit_key,
                                                       metadata, None)
        mock_conduit.save_unit.assert_called_once_with(inited_unit)

        mock_link.assert_called_once()
        self.assertEqual(mock_link.call_args[0][0], mock_conduit)
        self.assertTrue(isinstance(mock_link.call_args[0][1], models.Errata))
        # it is very important that this is the saved_unit, and not the inited_unit,
        # because the underlying link logic requires it to have an "id".
        self.assertTrue(mock_link.call_args[0][2] is saved_unit)

    @mock.patch('pulp_rpm.plugins.importers.yum.upload._link_errata_to_rpms')
    def test_handle_erratum_no_link(self, mock_link):
        # Setup
        unit_key = {'id': 'test-erratum'}
        metadata = {'a': 'a'}
        config = PluginCallConfiguration({}, {},
                                         override_config={upload.CONFIG_SKIP_ERRATUM_LINK: True})
        mock_conduit = mock.MagicMock()

        # Test
        upload._handle_erratum(models.Errata.TYPE, unit_key, metadata, None,
                               mock_conduit, config)

        # Verify
        self.assertEqual(0, mock_link.call_count)

    def test_handle_erratum_model_error(self):
        # Setup
        unit_key = {'foo': 'bar'}

        # Test
        self.assertRaises(upload.ModelInstantiationError, upload._handle_erratum,
                          models.Errata.TYPE, unit_key, {}, None, None, None)

    def test_link_errata_to_rpms(self):
        # Setup
        mock_conduit = mock.MagicMock()
        mock_conduit.get_units.return_value = ['a', 'b']

        sample_errata_file = os.path.join(DATA_DIR, 'RHBA-2010-0836.erratum.xml')
        with open(sample_errata_file) as f:
            errata = packages.package_list_generator(f,
                                                     updateinfo.PACKAGE_TAG,
                                                     updateinfo.process_package_element)
            errata = list(errata)[0]

        errata_unit = Unit(models.Errata.TYPE, errata.unit_key, errata.clean_metadata, None)

        # Test
        upload._link_errata_to_rpms(mock_conduit, errata, errata_unit)

        # Verify
        self.assertEqual(2, mock_conduit.get_units.call_count)  # once each for RPM and SRPM
        self.assertEqual(4, mock_conduit.link_unit.call_count)  # twice each for RPM and SRPM


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

        mock_conduit = mock.MagicMock()
        inited_unit = Unit(models.YumMetadataFile.TYPE, unit_key, metadata,
                           self.upload_dest_filename)
        mock_conduit.init_unit.return_value = inited_unit

        # Test
        upload._handle_yum_metadata_file(models.YumMetadataFile.TYPE, unit_key, metadata,
                                         self.upload_source_filename, mock_conduit, config)

        # Verify

        #   File was moved correctly
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

        # Test
        self.assertRaises(upload.ModelInstantiationError, upload._handle_yum_metadata_file,
                          models.Errata.TYPE, unit_key, {}, None, None, None)

    def test_handle_yum_metadata_file_storage_error(self):
        # Setup
        unit_key = {'data_type': 'product-id', 'repo_id': 'test-repo'}
        metadata = {'local_path': 'repodata/productid'}
        config = PluginCallConfiguration({}, {})

        mock_conduit = mock.MagicMock()
        inited_unit = Unit(models.YumMetadataFile.TYPE, unit_key, metadata,
                           '/foo/bar/baz')
        # Test will fail if that directory is writable by the unit test, but I'm willing to
        # take that chance.

        mock_conduit.init_unit.return_value = inited_unit

        # Test
        self.assertRaises(upload.StoreFileError, upload._handle_yum_metadata_file,
                          models.YumMetadataFile.TYPE, unit_key, metadata,
                          self.upload_source_filename, mock_conduit, config)


class GroupCategoryTests(unittest.TestCase):

    def test_handle_for_group(self):
        # Setup
        unit_key = {'id': 'test-group', 'repo_id': 'test-repo'}
        metadata = {}
        config = PluginCallConfiguration({}, {})

        mock_conduit = mock.MagicMock()
        inited_unit = Unit(models.PackageGroup.TYPE, unit_key, metadata, None)
        mock_conduit.init_unit.return_value = inited_unit

        # Test
        upload._handle_group_category(models.PackageGroup.TYPE, unit_key, metadata, None,
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

        mock_conduit = mock.MagicMock()
        inited_unit = Unit(models.PackageCategory.TYPE, unit_key, metadata, None)
        mock_conduit.init_unit.return_value = inited_unit

        # Test
        upload._handle_group_category(models.PackageCategory.TYPE, unit_key, metadata, None,
                                      mock_conduit, config)

        # Verify
        mock_conduit.init_unit.assert_called_once_with(models.PackageCategory.TYPE, unit_key,
                                                       metadata, None)
        mock_conduit.save_unit.assert_called_once()
        saved_unit = mock_conduit.save_unit.call_args[0][0]
        self.assertEqual(inited_unit, saved_unit)

    def test_model_error(self):
        # Setup
        unit_key = {'foo': 'bar'}

        # Test
        self.assertRaises(upload.ModelInstantiationError, upload._handle_group_category,
                          models.PackageGroup.TYPE, unit_key, {}, None, None, None)


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

    @mock.patch('pulp_rpm.plugins.importers.yum.upload._generate_rpm_data')
    def test_handle_package(self, mock_generate):
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

        mock_conduit = mock.MagicMock()
        inited_unit = Unit(models.RPM.TYPE, unit_key, metadata, self.upload_dest_filename)
        mock_conduit.init_unit.return_value = inited_unit

        # Test
        upload._handle_package(models.RPM.TYPE, user_unit_key, user_metadata, self.upload_src_filename,
                               mock_conduit, config)

        # Verify

        #   File was moved as part of the import
        self.assertTrue(os.path.exists(self.upload_dest_filename))
        self.assertTrue(not os.path.exists(self.upload_src_filename))

        #   Mock calls
        mock_generate.assert_called_once_with(self.upload_src_filename, user_metadata)

        full_unit_key = dict(unit_key)
        full_metadata = dict(metadata)

        full_unit_key.update(user_unit_key)
        full_metadata.update(user_metadata)
        expected_relative_path = models.RPM(metadata=full_metadata, **full_unit_key).relative_path

        mock_conduit.init_unit.assert_called_once_with(models.RPM.TYPE, full_unit_key,
                                                       full_metadata, expected_relative_path)
        mock_conduit.save_unit.assert_called_once()
        saved_unit = mock_conduit.save_unit.call_args[0][0]
        self.assertEqual(inited_unit, saved_unit)

    @mock.patch('pulp_rpm.plugins.importers.yum.upload._generate_rpm_data')
    def test_handle_metadata_error(self, mock_generate):
        # Setup
        mock_generate.side_effect = Exception()

        # Test
        self.assertRaises(upload.PackageMetadataError, upload._handle_package, None, None,
                          None, None, None, None)

    @mock.patch('pulp_rpm.plugins.importers.yum.upload._generate_rpm_data')
    def test_handle_model_instantiation_error(self, mock_generate):
        # Setup
        mock_generate.return_value = {}, {}  # incomplete unit key, will error

        # Test
        self.assertRaises(upload.ModelInstantiationError, upload._handle_package,
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

        mock_conduit = mock.MagicMock()
        mock_conduit.init_unit.side_effect = IOError()

        # Test
        self.assertRaises(upload.StoreFileError, upload._handle_package, models.RPM.TYPE,
                          unit_key, metadata, self.upload_src_filename, mock_conduit, config)

    def test_generate_rpm_data(self):
        # Test
        unit_key, metadata = upload._generate_rpm_data(self.upload_src_filename, {})

        # Verify
        self.assertEqual(unit_key['name'], 'walrus')
        self.assertEqual(unit_key['epoch'], '0')
        self.assertEqual(unit_key['version'], '5.21')
        self.assertEqual(unit_key['release'], '1')
        self.assertEqual(unit_key['arch'], 'noarch')
        self.assertEqual(unit_key['checksum'], 'e837a635cc99f967a70f34b268baa52e0f412c1502e08e924ff5b09f1f9573f2')
        self.assertEqual(unit_key['checksumtype'], 'sha256')

        self.assertEqual(metadata['buildhost'], 'smqe-ws15')
        self.assertEqual(metadata['description'], 'A dummy package of walrus')
        self.assertEqual(metadata['filename'], 'walrus-5.21-1.noarch.rpm')
        self.assertEqual(metadata['license'], 'GPLv2')
        self.assertEqual(metadata['relativepath'], 'walrus-5.21-1.noarch.rpm')
        self.assertEqual(metadata['vendor'], None)

    def test_generate_rpm_data_user_checksum(self):
        # Test
        unit_key, metadata = upload._generate_rpm_data(self.upload_src_filename,
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
        unit_key, metadata = upload._generate_rpm_data(self.upload_src_filename,
                                                       {'checksum_type': None})

        # Verify
        self.assertEqual(unit_key['name'], 'walrus')
        self.assertEqual(unit_key['epoch'], '0')
        self.assertEqual(unit_key['version'], '5.21')
        self.assertEqual(unit_key['release'], '1')
        self.assertEqual(unit_key['arch'], 'noarch')
        self.assertEqual(unit_key['checksum'], 'e837a635cc99f967a70f34b268baa52e0f412c1502e08e924ff5b09f1f9573f2')
        self.assertEqual(unit_key['checksumtype'], 'sha256')

        self.assertEqual(metadata['buildhost'], 'smqe-ws15')
        self.assertEqual(metadata['description'], 'A dummy package of walrus')
        self.assertEqual(metadata['filename'], 'walrus-5.21-1.noarch.rpm')
        self.assertEqual(metadata['license'], 'GPLv2')
        self.assertEqual(metadata['relativepath'], 'walrus-5.21-1.noarch.rpm')
        self.assertEqual(metadata['vendor'], None)
