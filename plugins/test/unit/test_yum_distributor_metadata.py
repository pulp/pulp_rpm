import gzip
import os
import shutil
import unittest

from pulp.plugins.model import Unit

from pulp_rpm.common.ids import TYPE_ID_RPM
from pulp_rpm.plugins.distributors.yum.metadata.filelists import (
    FilelistsXMLFileContext, FILE_LISTS_NAMESPACE, FILE_LISTS_XML_FILE_NAME)
from pulp_rpm.plugins.distributors.yum.metadata.metadata import (
    MetadataFileContext, PreGeneratedMetadataContext, REPO_DATA_DIR_NAME)
from pulp_rpm.plugins.distributors.yum.metadata.other import (
    OtherXMLFileContext, OTHER_NAMESPACE, OTHER_XML_FILE_NAME)
from pulp_rpm.plugins.distributors.yum.metadata.prestodelta import (
    PrestodeltaXMLFileContext, PRESTO_DELTA_FILE_NAME)
from pulp_rpm.plugins.distributors.yum.metadata.primary import (
    PrimaryXMLFileContext, COMMON_NAMESPACE, RPM_NAMESPACE, PRIMARY_XML_FILE_NAME)
from pulp_rpm.plugins.distributors.yum.metadata.repomd import (
    RepomdXMLFileContext, REPO_XML_NAME_SPACE, RPM_XML_NAME_SPACE, REPOMD_FILE_NAME)
from pulp_rpm.plugins.distributors.yum.metadata.updateinfo import (
    UpdateinfoXMLFileContext, UPDATE_INFO_XML_FILE_NAME)
from pulp_rpm.plugins.importers.yum.repomd import packages, presto, updateinfo


DATA_DIR = os.path.join(os.path.dirname(__file__), '../data/')


class YumDistributorMetadataTests(unittest.TestCase):

    def setUp(self):
        super(YumDistributorMetadataTests, self).setUp()

        self.metadata_file_dir = '/tmp/test_yum_distributor_metadata/'

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
            MetadataFileContext('fu.xml')

        except Exception, e:
            self.fail(e.message)

    def test_open_handle(self):

        path = os.path.join(self.metadata_file_dir, 'open_handle.xml')
        context = MetadataFileContext(path)

        context._open_metadata_file_handle()

        self.assertTrue(os.path.exists(path))

        context._close_metadata_file_handle()


    def test_open_handle_bad_parent_permissions(self):

        path = os.path.join(self.metadata_file_dir, 'nope.xml')
        context = MetadataFileContext(path)

        os.makedirs(self.metadata_file_dir, mode=0000)

        self.assertRaises(RuntimeError, context._open_metadata_file_handle)

        os.chmod(self.metadata_file_dir, 0777)

    def test_open_handle_file_exists(self):

        path = os.path.join(self.metadata_file_dir, 'overwriteme.xml')
        context = MetadataFileContext(path)

        os.makedirs(self.metadata_file_dir)
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

        os.makedirs(self.metadata_file_dir)
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

    # -- primary.xml context testing -------------------------------------------

    def test_primary_file_creation(self):

        path = os.path.join(self.metadata_file_dir,
                            REPO_DATA_DIR_NAME,
                            PRIMARY_XML_FILE_NAME)

        context = PrimaryXMLFileContext(self.metadata_file_dir, 0)

        context._open_metadata_file_handle()
        context._close_metadata_file_handle()

        self.assertTrue(os.path.exists(path))

    def test_primary_opening_tag(self):

        path = os.path.join(self.metadata_file_dir,
                            REPO_DATA_DIR_NAME,
                            PRIMARY_XML_FILE_NAME)

        context = PrimaryXMLFileContext(self.metadata_file_dir, 0)

        context._open_metadata_file_handle()
        context._write_root_tag_open()
        context._close_metadata_file_handle()

        self.assertNotEqual(os.path.getsize(path), 0)

        primary_handle = gzip.open(path, 'r')
        content = primary_handle.read()
        primary_handle.close()

        self.assertTrue(content.startswith('<metadata'))
        self.assertEqual(content.count('xmlns="%s"' % COMMON_NAMESPACE), 1)
        self.assertEqual(content.count('xmlns:rpm="%s"' % RPM_NAMESPACE), 1)
        self.assertEqual(content.count('packages="0"'), 1)

    def test_primary_closing_tag(self):

        context = PrimaryXMLFileContext(self.metadata_file_dir, 0)
        context._open_metadata_file_handle()

        self.assertRaises(NotImplementedError, context._write_root_tag_close)

        context._write_root_tag_open()

        try:
            context._write_root_tag_close()

        except Exception, e:
            self.fail(e.message)

        context._close_metadata_file_handle()

    def test_primary_unit_metadata(self):

        path = os.path.join(self.metadata_file_dir,
                            REPO_DATA_DIR_NAME,
                            PRIMARY_XML_FILE_NAME)

        unit = self._generate_rpm('seems-legit')

        context = PrimaryXMLFileContext(self.metadata_file_dir, 1)

        context._open_metadata_file_handle()
        context.add_unit_metadata(unit)
        context._close_metadata_file_handle()

        handle = gzip.open(path, 'r')
        content = handle.read()
        handle.close()

        self.assertEqual(content, 'PRIMARY')

    def test_primary_with_keyword(self):

        with PrimaryXMLFileContext(self.metadata_file_dir, 0):
            pass

        path = os.path.join(self.metadata_file_dir,
                            REPO_DATA_DIR_NAME,
                            PRIMARY_XML_FILE_NAME)

        self.assertTrue(os.path.exists(path))
        # the xml header, opening, and closing tags should have been written
        self.assertNotEqual(os.path.getsize(path), 0)

        primary_handle = gzip.open(path, 'r')
        content_lines = primary_handle.readlines()
        primary_handle.close()

        self.assertEqual(len(content_lines), 3)
        self.assertEqual(content_lines[0], '<?xml version="1.0" encoding="UTF-8"?>\n')
        self.assertEqual(content_lines[2], '</metadata>\n')

    def test_primary_with_keyword_and_add_unit(self):

        unit = self._generate_rpm('with-context')

        with PrimaryXMLFileContext(self.metadata_file_dir, 1) as context:

            try:
                context.add_unit_metadata(unit)

            except Exception, e:
                self.fail(e.message)

    # -- other.xml context testing ---------------------------------------------

    def test_other_file_creation(self):

        path = os.path.join(self.metadata_file_dir,
                            REPO_DATA_DIR_NAME,
                            OTHER_XML_FILE_NAME)

        context = OtherXMLFileContext(self.metadata_file_dir, 0)

        context._open_metadata_file_handle()
        context._close_metadata_file_handle()

        self.assertTrue(os.path.exists(path))

    def test_other_opening_tag(self):

        path = os.path.join(self.metadata_file_dir,
                            REPO_DATA_DIR_NAME,
                            OTHER_XML_FILE_NAME)

        context = OtherXMLFileContext(self.metadata_file_dir, 0)

        context._open_metadata_file_handle()
        context._write_root_tag_open()
        context._close_metadata_file_handle()

        self.assertNotEqual(os.path.getsize(path), 0)

        other_handle = gzip.open(path, 'r')
        context = other_handle.read()
        other_handle.close()

        self.assertTrue(context.startswith('<otherdata'))
        self.assertEqual(context.count('xmlns="%s"' % OTHER_NAMESPACE), 1)
        self.assertEqual(context.count('packages="0"'), 1)

    def test_other_closing_tag(self):

        context = OtherXMLFileContext(self.metadata_file_dir, 0)
        context._open_metadata_file_handle()

        self.assertRaises(NotImplementedError, context._write_root_tag_close)

        context._write_root_tag_open()

        try:
            context._write_root_tag_close()

        except Exception, e:
            self.fail(e.message)

        context._close_metadata_file_handle()

    def test_other_unit_metadata(self):

        path = os.path.join(self.metadata_file_dir,
                            REPO_DATA_DIR_NAME,
                            OTHER_XML_FILE_NAME)

        unit = self._generate_rpm('uh-huh')

        context = OtherXMLFileContext(self.metadata_file_dir, 1)

        context._open_metadata_file_handle()
        context.add_unit_metadata(unit)
        context._close_metadata_file_handle()

        self.assertNotEqual(os.path.getsize(path), 0)

        handle = gzip.open(path, 'r')
        content = handle.read()
        handle.close()

        self.assertEqual(content, 'OTHER')

    # -- filelists.xml context testing -----------------------------------------

    def test_filelists_file_creation(self):

        path = os.path.join(self.metadata_file_dir,
                            REPO_DATA_DIR_NAME,
                            FILE_LISTS_XML_FILE_NAME)

        context = FilelistsXMLFileContext(self.metadata_file_dir, 0)

        context._open_metadata_file_handle()
        context._close_metadata_file_handle()

        self.assertTrue(os.path.exists(path))


    def test_filelists_opening_tag(self):

        path = os.path.join(self.metadata_file_dir,
                            REPO_DATA_DIR_NAME,
                            FILE_LISTS_XML_FILE_NAME)

        context = FilelistsXMLFileContext(self.metadata_file_dir, 0)

        context._open_metadata_file_handle()
        context._write_root_tag_open()
        context._close_metadata_file_handle()

        self.assertNotEqual(os.path.getsize(path), 0)

        filelists_handle = gzip.open(path, 'r')
        content = filelists_handle.read()
        filelists_handle.close()

        self.assertTrue(content.startswith('<filelists'))
        self.assertEqual(content.count('xmlns="%s"' % FILE_LISTS_NAMESPACE), 1)
        self.assertEqual(content.count('packages="0"'), 1)

    def test_filelists_closing_tag(self):

        context = FilelistsXMLFileContext(self.metadata_file_dir, 0)
        context._open_metadata_file_handle()

        self.assertRaises(NotImplementedError, context._write_root_tag_close)

        context._write_root_tag_open()

        try:
            context._write_root_tag_close()

        except Exception, e:
            self.fail(e.message)

        context._close_metadata_file_handle()

    def test_filelists_unit_metadata(self):

        path = os.path.join(self.metadata_file_dir,
                            REPO_DATA_DIR_NAME,
                            FILE_LISTS_XML_FILE_NAME)

        unit = self._generate_rpm('ive-got-files')

        context = FilelistsXMLFileContext(self.metadata_file_dir, 1)

        context._open_metadata_file_handle()
        context.add_unit_metadata(unit)
        context._close_metadata_file_handle()

        handle = gzip.open(path, 'r')
        content = handle.read()
        handle.close()

        self.assertEqual(content, 'FILELISTS')

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

    def test_prestodelta_file_creation(self):

        path = os.path.join(self.metadata_file_dir,
                            REPO_DATA_DIR_NAME,
                            PRESTO_DELTA_FILE_NAME)

        context = PrestodeltaXMLFileContext(self.metadata_file_dir)

        context._open_metadata_file_handle()
        context._close_metadata_file_handle()

        self.assertTrue(os.path.exists(path))

    def test_prestodelta_opening_closing_tags(self):

        path = os.path.join(self.metadata_file_dir,
                            REPO_DATA_DIR_NAME,
                            PRESTO_DELTA_FILE_NAME)

        context = PrestodeltaXMLFileContext(self.metadata_file_dir)

        context._open_metadata_file_handle()

        self.assertRaises(NotImplementedError, context._write_root_tag_close)

        context._write_root_tag_open()

        try:
            context._write_root_tag_close()

        except Exception, e:
            self.fail(e.message)

        context._close_metadata_file_handle()

        self.assertNotEqual(os.path.getsize(path), 0)

        prestodelta_handle = gzip.open(path, 'r')
        content = prestodelta_handle.read()
        prestodelta_handle.close()

        self.assertEqual(content, '<prestodelta>\n</prestodelta>\n')

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
        self.assertEqual(content.count('epoch="0"'), 2) # also matches oldepoch
        self.assertEqual(content.count('version="3.4.3"'), 2) # also matches oldversion
        self.assertEqual(content.count('release="16.fc16"'), 1)
        self.assertEqual(content.count('arch="noarch"'), 1)
        self.assertEqual(content.count('oldepoch="0"'), 1)
        self.assertEqual(content.count('oldversion="3.4.3"'), 1)
        self.assertEqual(content.count('oldrelease="11.fc16"'), 1)
        self.assertEqual(content.count('<filename>drpms/yum-3.4.3-11.fc16_3.4.3-16.fc16.noarch.drpm</filename>'), 1)
        self.assertEqual(content.count('<sequence>yum-3.4.3-11.fc16-fa4535420dc8db63b7349d4262e3920b211141321242121222421212124242121272421212121212a1212121286272121212309f210ee210be2108e210fc210de110ae110fd110cd1108c110db110ab110fa110ca1109a110b9110a8110f710c710e6108610d510a510f4109410d310a310f2109210e11</sequence>'), 1)
        self.assertEqual(content.count('<size>183029</size>'), 1)
        self.assertEqual(content.count('<checksum type="sha256">77fad55681f652e06e8ba8fd6f11e505c4d85041ee30a37bbf8f573c4fb8f570</checksum>'), 1)

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

    def test_repomd_metadata_file_metadata(self):

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
            self.assertEqual(content.count('<size>'), 1)
            self.assertEqual(content.count('<checksum type="sha256">'), 1)
            self.assertEqual(content.count('<open-size>%s</open-size>' % len(test_metadata_content)), 1)
            self.assertEqual(content.count('<open-checksum type="sha256">'), 1)

