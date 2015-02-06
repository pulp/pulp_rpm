import gzip
import hashlib
import os
import shutil
import tempfile
import unittest
from xml.etree import cElementTree as et

from mock import patch
from pulp.plugins.model import Unit

from pulp_rpm.common.ids import TYPE_ID_RPM
from pulp_rpm.plugins.distributors.yum.metadata.metadata import (
    MetadataFileContext, PreGeneratedMetadataContext, REPO_DATA_DIR_NAME)
from pulp_rpm.plugins.distributors.yum.metadata.prestodelta import (
    PrestodeltaXMLFileContext, PRESTO_DELTA_FILE_NAME)
from pulp_rpm.plugins.distributors.yum.metadata.repomd import (
    RepomdXMLFileContext, REPO_XML_NAME_SPACE, RPM_XML_NAME_SPACE, REPOMD_FILE_NAME)
from pulp_rpm.plugins.distributors.yum.metadata.updateinfo import (
    UpdateinfoXMLFileContext, UPDATE_INFO_XML_FILE_NAME)
from pulp_rpm.plugins.importers.yum.repomd import packages, presto, updateinfo


DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', 'data')


class YumDistributorMetadataTests(unittest.TestCase):
    def setUp(self):
        super(YumDistributorMetadataTests, self).setUp()

        self.metadata_file_dir = tempfile.mkdtemp()

    def tearDown(self):
        super(YumDistributorMetadataTests, self).tearDown()

        if os.path.exists(self.metadata_file_dir):
            shutil.rmtree(self.metadata_file_dir)

    def _generate_rpm(self, name):

        unit_key = {'name': name,
                    'epoch': 0,
                    'version': 1,
                    'release': 0,
                    'arch': 'noarch',
                    'checksumtype': 'sha256',
                    'checksum': '1234657890'}

        unit_metadata = {'repodata': {'filelists': 'FILELISTS',
                                      'other': 'OTHER',
                                      'primary': 'PRIMARY'}}

        storage_path = os.path.join(self.metadata_file_dir, name)

        return Unit(TYPE_ID_RPM, unit_key, unit_metadata, storage_path)

    # -- metadata file context base class tests --------------------------------

    def test_metadata_instantiation(self):
        try:
            metadata_file_context = MetadataFileContext('fu.xml')
        except Exception, e:
            self.fail(e.message)

        self.assertEqual(metadata_file_context.checksum_type, None)

    def test_metadata_instantiation_with_checksum_type(self):
        test_checksum_type = 'sha1'

        try:
            metadata_file_context = MetadataFileContext('fu.xml', checksum_type=test_checksum_type)
        except Exception, e:
            self.fail(e.message)

        self.assertEqual(metadata_file_context.checksum_type, 'sha1')
        self.assertEqual(metadata_file_context.checksum_constructor,
                         getattr(hashlib, test_checksum_type))

    def test_open_handle(self):

        path = os.path.join(self.metadata_file_dir, 'open_handle.xml')
        context = MetadataFileContext(path)

        context._open_metadata_file_handle()

        self.assertTrue(os.path.exists(path))

        context._close_metadata_file_handle()

    def test_open_handle_bad_parent_permissions(self):

        test_dir = os.path.join(self.metadata_file_dir, 'test')
        os.makedirs(test_dir, mode=0000)

        path = os.path.join(test_dir, 'nope.xml')
        context = MetadataFileContext(path)

        self.assertRaises(RuntimeError, context._open_metadata_file_handle)

        os.chmod(test_dir, 0777)

    def test_open_handle_file_exists(self):

        path = os.path.join(self.metadata_file_dir, 'overwriteme.xml')
        context = MetadataFileContext(path)

        with open(path, 'w') as h:
            h.flush()

        try:
            context._open_metadata_file_handle()

        except Exception, e:
            self.fail(e.message)

        context._close_metadata_file_handle()

    def test_open_handle_bad_file_permissions(self):

        path = os.path.join(self.metadata_file_dir, 'nope_again.xml')
        context = MetadataFileContext(path)

        with open(path, 'w') as h:
            h.flush()
        os.chmod(path, 0000)

        self.assertRaises(RuntimeError, context._open_metadata_file_handle)

        os.chmod(path, 0777)

    def test_open_handle_gzip(self):

        path = os.path.join(self.metadata_file_dir, 'test.xml.gz')
        context = MetadataFileContext(path)

        context._open_metadata_file_handle()

        self.assertTrue(os.path.exists(path))

        context._write_xml_header()
        context._close_metadata_file_handle()

        try:
            h = gzip.open(path)

        except Exception, e:
            self.fail(e.message)

        h.close()

    def test_write_xml_header(self):

        path = os.path.join(self.metadata_file_dir, 'header.xml')
        context = MetadataFileContext(path)

        context._open_metadata_file_handle()
        context._write_xml_header()
        context._close_metadata_file_handle()

        self.assertTrue(os.path.exists(path))

        with open(path) as h:
            content = h.read()

        expected_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
        self.assertEqual(content, expected_content)

    def test_is_closed_gzip_file(self):
        path = os.path.join(DATA_DIR, 'foo.tar.gz')

        file_object = gzip.open(path)
        file_object.close()

        self.assertTrue(MetadataFileContext._is_closed(file_object))

    def test_is_open_gzip_file(self):
        path = os.path.join(DATA_DIR, 'foo.tar.gz')

        file_object = gzip.open(path)

        self.assertFalse(MetadataFileContext._is_closed(file_object))

        file_object.close()

    def test_is_closed_file(self):
        path = os.path.join(DATA_DIR, 'foo.tar.gz')

        # opening as a regular file, not with gzip
        file_object = open(path)
        file_object.close()

        self.assertTrue(MetadataFileContext._is_closed(file_object))

    def test_is_open_file(self):
        path = os.path.join(DATA_DIR, 'foo.tar.gz')

        # opening as a regular file, not with gzip
        file_object = open(path)

        self.assertFalse(MetadataFileContext._is_closed(file_object))

        file_object.close()

    def test_is_closed_file_attribute_error(self):
        # passing in a list gives it an object that does not have a closed attribute,
        # thus triggering
        # an Attribute error that cannot be solved with the python 2.6 compatibility code
        self.assertRaises(AttributeError, MetadataFileContext._is_closed, [])

    def test_finalize_closed_gzip_file(self):
        # this test makes sure that we can properly detect the closed state of
        # a gzip file, because on python 2.6 we have to take special measures
        # to do so.
        path = os.path.join(DATA_DIR, 'foo.tar.gz')

        context = MetadataFileContext('/a/b/c')
        context.metadata_file_handle = gzip.open(path)
        context.metadata_file_handle.close()

        # just make sure this doesn't complain.
        context.finalize()

    def test_finalize_checksum_type_none(self):

        path = os.path.join(self.metadata_file_dir, 'test.xml')
        context = MetadataFileContext(path)

        context._open_metadata_file_handle()
        context._write_xml_header()
        context._close_metadata_file_handle()
        context.finalize()

        self.assertEqual(context.metadata_file_path, path)

    def test_finalize_with_valid_checksum_type(self):

        path = os.path.join(self.metadata_file_dir, 'test.xml')
        checksum_type = 'sha1'
        context = MetadataFileContext(path, checksum_type)

        context._open_metadata_file_handle()
        context._write_xml_header()
        context.finalize()

        expected_metadata_file_name = context.checksum + '-' + 'test.xml'
        expected_metadata_file_path = os.path.join(self.metadata_file_dir,
                                                   expected_metadata_file_name)
        self.assertEqual(expected_metadata_file_path, context.metadata_file_path)

    def test_finalize_for_repomd_file_with_valid_checksum_type(self):

        path = os.path.join(self.metadata_file_dir, 'repomd.xml')
        checksum_type = 'sha1'
        context = MetadataFileContext(path, checksum_type)

        context._open_metadata_file_handle()
        context._write_xml_header()
        context._close_metadata_file_handle()
        context.finalize()

        self.assertEqual(context.metadata_file_path, path)

    # -- pre-generated metadata context tests ----------------------------------

    def test_pre_generated_metadata(self):

        path = os.path.join(self.metadata_file_dir, 'pre-gen.xml')
        context = PreGeneratedMetadataContext(path)
        unit = self._generate_rpm('test_rpm')

        context._open_metadata_file_handle()
        context._add_unit_pre_generated_metadata('primary', unit)
        context._close_metadata_file_handle()

        self.assertEqual(os.path.getsize(path), len('PRIMARY'))

    def test_pre_generated_metadata_no_repodata(self):

        path = os.path.join(self.metadata_file_dir, 'no-repodata.xml')
        context = PreGeneratedMetadataContext(path)
        unit = self._generate_rpm('no_repodata')

        unit.metadata.pop('repodata')

        context._open_metadata_file_handle()
        context._add_unit_pre_generated_metadata('primary', unit)
        context._close_metadata_file_handle()

        self.assertEqual(os.path.getsize(path), 0)

    def test_pre_generated_metadata_wrong_category(self):

        path = os.path.join(self.metadata_file_dir, 'wrong-category.xml')
        context = PreGeneratedMetadataContext(path)
        unit = self._generate_rpm('wrong_category')

        context._open_metadata_file_handle()
        context._add_unit_pre_generated_metadata('not_found', unit)
        context._close_metadata_file_handle()

        self.assertEqual(os.path.getsize(path), 0)

    def test_pre_generated_metadata_not_string(self):

        path = os.path.join(self.metadata_file_dir, 'not-string.xml')
        context = PreGeneratedMetadataContext(path)
        unit = self._generate_rpm('not_string')

        unit.metadata['repodata']['whatisthis'] = 1

        context._open_metadata_file_handle()
        context._add_unit_pre_generated_metadata('whatisthis', unit)
        context._close_metadata_file_handle()

        self.assertEqual(os.path.getsize(path), 0)

    # -- updateinfo.xml testing ------------------------------------------------

    def test_updateinfo_file_creation(self):

        path = os.path.join(self.metadata_file_dir,
                            REPO_DATA_DIR_NAME,
                            UPDATE_INFO_XML_FILE_NAME)

        context = UpdateinfoXMLFileContext(self.metadata_file_dir)

        context._open_metadata_file_handle()
        context._close_metadata_file_handle()

        self.assertTrue(os.path.exists(path))

    def test_updateinfo_opening_closing_tags(self):

        path = os.path.join(self.metadata_file_dir,
                            REPO_DATA_DIR_NAME,
                            UPDATE_INFO_XML_FILE_NAME)

        context = UpdateinfoXMLFileContext(self.metadata_file_dir)

        context._open_metadata_file_handle()

        self.assertRaises(NotImplementedError, context._write_root_tag_close)

        context._write_root_tag_open()

        try:
            context._write_root_tag_close()

        except Exception, e:
            self.fail(e.message)

        context._close_metadata_file_handle()

        self.assertNotEqual(os.path.getsize(path), 0)

        updateinfo_handle = gzip.open(path, 'r')
        content = updateinfo_handle.read()
        updateinfo_handle.close()

        self.assertEqual(content, '<updates>\n</updates>\n')

    def test_updateinfo_unit_metadata(self):

        path = os.path.join(self.metadata_file_dir,
                            REPO_DATA_DIR_NAME,
                            UPDATE_INFO_XML_FILE_NAME)

        handle = open(os.path.join(DATA_DIR, 'updateinfo.xml'), 'r')
        generator = packages.package_list_generator(handle, 'update',
                                                    updateinfo.process_package_element)

        erratum_unit = next(generator)

        # just checking
        self.assertEqual(erratum_unit.unit_key['id'], 'RHEA-2010:9999')

        context = UpdateinfoXMLFileContext(self.metadata_file_dir)
        context._open_metadata_file_handle()
        context.add_unit_metadata(erratum_unit)
        context._close_metadata_file_handle()

        self.assertNotEqual(os.path.getsize(path), 0)

        updateinfo_handle = gzip.open(path, 'r')
        content = updateinfo_handle.read()
        updateinfo_handle.close()

        self.assertEqual(content.count('from="enhancements@redhat.com"'), 1)
        self.assertEqual(content.count('status="final"'), 1)
        self.assertEqual(content.count('type="enhancements"'), 1)
        self.assertEqual(content.count('version="1"'), 1)
        self.assertEqual(content.count('<id>RHEA-2010:9999</id>'), 1)
        self.assertEqual(content.count('<collection short="F13PTP">'), 1)
        self.assertEqual(content.count('<package'), 2)
        self.assertEqual(content.count('<sum type="md5">f3c197a29d9b66c5b65c5d62b25db5b4</sum>'), 1)

    # -- prestodelta.xml testing -----------------------------------------------

    def test_prestodelta_unit_metadata(self):

        path = os.path.join(self.metadata_file_dir,
                            REPO_DATA_DIR_NAME,
                            PRESTO_DELTA_FILE_NAME)

        handle = open(os.path.join(DATA_DIR, 'prestodelta.xml'), 'r')
        generator = packages.package_list_generator(handle, 'newpackage',
                                                    presto.process_package_element)

        prestodelta_unit = next(generator)

        # double check we've grabbed the right one
        self.assertEqual(prestodelta_unit.metadata['new_package'], 'yum')
        self.assertEqual(prestodelta_unit.unit_key['release'], '16.fc16')

        context = PrestodeltaXMLFileContext(self.metadata_file_dir)
        context._open_metadata_file_handle()
        context.add_unit_metadata(prestodelta_unit)
        context._close_metadata_file_handle()

        prestodelta_handle = gzip.open(path, 'r')
        content = prestodelta_handle.read()
        prestodelta_handle.close()

        self.assertEqual(content.count('name="yum"'), 1)
        self.assertEqual(content.count('epoch="0"'), 2)  # also matches oldepoch
        self.assertEqual(content.count('version="3.4.3"'), 2)  # also matches oldversion
        self.assertEqual(content.count('release="16.fc16"'), 1)
        self.assertEqual(content.count('arch="noarch"'), 1)
        self.assertEqual(content.count('oldepoch="0"'), 1)
        self.assertEqual(content.count('oldversion="3.4.3"'), 1)
        self.assertEqual(content.count('oldrelease="11.fc16"'), 1)
        self.assertEqual(
            content.count('<filename>drpms/yum-3.4.3-11.fc16_3.4.3-16.fc16.noarch.drpm</filename>'),
            1)
        self.assertEqual(content.count(
            '<sequence>yum-3.4.3-11.fc16'
            '-fa4535420dc8db63b7349d4262e3920b211141321242121222421212124242121272421212121212a121'
            '2121286272121212309f210ee210be2108e210fc210de110ae110fd110cd1108c110db110ab110fa110ca1'
            '109a110b9110a8110f710c710e6108610d510a510f4109410d310a310f2109210e11</sequence>'),
            1)
        self.assertEqual(content.count('<size>183029</size>'), 1)
        self.assertEqual(content.count(
            '<checksum '
            'type="sha256">77fad55681f652e06e8ba8fd6f11e505c4d85041ee30a37bbf8f573c4fb8f570'
            '</checksum>'),
            1)

    # -- repomd.xml testing ----------------------------------------------------

    def test_repomd_file_creation(self):

        path = os.path.join(self.metadata_file_dir,
                            REPO_DATA_DIR_NAME,
                            REPOMD_FILE_NAME)

        context = RepomdXMLFileContext(self.metadata_file_dir)
        context._open_metadata_file_handle()
        context._close_metadata_file_handle()

        self.assertTrue(os.path.exists(path))

    def test_repomd_opening_closing_tags(self):

        path = os.path.join(self.metadata_file_dir,
                            REPO_DATA_DIR_NAME,
                            REPOMD_FILE_NAME)

        context = RepomdXMLFileContext(self.metadata_file_dir)
        context._open_metadata_file_handle()

        self.assertRaises(NotImplementedError, context._write_root_tag_close)

        try:
            context._write_root_tag_open()

        except Exception, e:
            self.fail(e.message)

        try:
            context._write_root_tag_close()

        except Exception, e:
            self.fail(e.message)

        context._close_metadata_file_handle()

        with open(path, 'r') as repomd_file_handle:

            content = repomd_file_handle.read()

            self.assertEqual(content.count('<repomd'), 1)
            self.assertEqual(content.count('xmlns="%s"' % REPO_XML_NAME_SPACE), 1)
            self.assertEqual(content.count('xmlns:rpm="%s"' % RPM_XML_NAME_SPACE), 1)
            self.assertEqual(content.count('<revision>'), 1)

    @patch('os.path.getmtime')
    def test_repomd_metadata_file_metadata(self, mock_getmtime):

        path = os.path.join(self.metadata_file_dir,
                            REPO_DATA_DIR_NAME,
                            REPOMD_FILE_NAME)

        test_metadata_file_name = 'metadata.gz'
        test_metadata_file_path = os.path.join(self.metadata_file_dir,
                                               REPO_DATA_DIR_NAME,
                                               test_metadata_file_name)
        test_metadata_content = 'The quick brown fox jumps over the lazy dog'

        os.makedirs(os.path.dirname(test_metadata_file_path))
        test_metadata_file_handle = gzip.open(test_metadata_file_path, 'w')
        test_metadata_file_handle.write(test_metadata_content)
        test_metadata_file_handle.close()

        mock_getmtime.return_value = 45.5
        context = RepomdXMLFileContext(self.metadata_file_dir)
        context._open_metadata_file_handle()
        context.add_metadata_file_metadata('metadata', test_metadata_file_path)
        context._close_metadata_file_handle()

        with open(path, 'r') as repomd_handle:
            content = repomd_handle.read()
            self.assertEqual(content.count('<data type="metadata"'), 1)
            self.assertEqual(content.count('<location href="%s/%s"' %
                                           (REPO_DATA_DIR_NAME, test_metadata_file_name)), 1)
            self.assertEqual(content.count('<timestamp>'), 1)
            # yum does an integer conversion on the timestamp
            # integer conversion of float strings will throw an error
            # so make sure this isn't a float
            xml_element = et.fromstring(content)
            ts_value = (xml_element.findall('timestamp'))[0].text
            int(ts_value)

            self.assertEqual(content.count('<size>'), 1)
            self.assertEqual(content.count('<checksum type="sha256">'), 1)
            self.assertEqual(
                content.count('<open-size>%s</open-size>' % len(test_metadata_content)), 1)
            self.assertEqual(content.count('<open-checksum type="sha256">'), 1)
