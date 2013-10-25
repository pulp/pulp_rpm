# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the License
# (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied, including the
# implied warranties of MERCHANTABILITY, NON-INFRINGEMENT, or FITNESS FOR A
# PARTICULAR PURPOSE.
# You should have received a copy of GPLv2 along with this software;
# if not, see http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt

import gzip
import os
import shutil
import unittest

from pulp.plugins.model import Unit

from pulp_rpm.common.ids import TYPE_ID_RPM
from pulp_rpm.plugins.distributors.yum import metadata
from pulp_rpm.plugins.importers.yum.repomd import packages, updateinfo


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
            metadata.MetadataFileContext('fu.xml')

        except Exception, e:
            self.fail(e.message)

    def test_open_handle(self):

        path = os.path.join(self.metadata_file_dir, 'open_handle.xml')
        context = metadata.MetadataFileContext(path)

        context._open_metadata_file_handle()

        self.assertTrue(os.path.exists(path))

        context._close_metadata_file_handle()


    def test_open_handle_bad_parent_permissions(self):

        path = os.path.join(self.metadata_file_dir, 'nope.xml')
        context = metadata.MetadataFileContext(path)

        os.makedirs(self.metadata_file_dir, mode=0000)

        self.assertRaises(RuntimeError, context._open_metadata_file_handle)

        os.chmod(self.metadata_file_dir, 0777)

    def test_open_handle_file_exists(self):

        path = os.path.join(self.metadata_file_dir, 'overwriteme.xml')
        context = metadata.MetadataFileContext(path)

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
        context = metadata.MetadataFileContext(path)

        os.makedirs(self.metadata_file_dir)
        with open(path, 'w') as h:
            h.flush()
        os.chmod(path, 0000)

        self.assertRaises(RuntimeError, context._open_metadata_file_handle)

        os.chmod(path, 0777)

    def test_open_handle_gzip(self):

        path = os.path.join(self.metadata_file_dir, 'test.xml.gz')
        context = metadata.MetadataFileContext(path)

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
        context = metadata.MetadataFileContext(path)

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
        context = metadata.PreGeneratedMetadataContext(path)
        unit = self._generate_rpm('test_rpm')

        context._open_metadata_file_handle()
        context._add_unit_pre_generated_metadata('primary', unit)
        context._close_metadata_file_handle()

        self.assertEqual(os.path.getsize(path), len('PRIMARY'))

    def test_pre_generated_metadata_no_repodata(self):

        path = os.path.join(self.metadata_file_dir, 'no-repodata.xml')
        context = metadata.PreGeneratedMetadataContext(path)
        unit = self._generate_rpm('no_repodata')

        unit.metadata.pop('repodata')

        context._open_metadata_file_handle()
        context._add_unit_pre_generated_metadata('primary', unit)
        context._close_metadata_file_handle()

        self.assertEqual(os.path.getsize(path), 0)

    def test_pre_generated_metadata_wrong_category(self):

        path = os.path.join(self.metadata_file_dir, 'wrong-category.xml')
        context = metadata.PreGeneratedMetadataContext(path)
        unit = self._generate_rpm('wrong_category')

        context._open_metadata_file_handle()
        context._add_unit_pre_generated_metadata('not_found', unit)
        context._close_metadata_file_handle()

        self.assertEqual(os.path.getsize(path), 0)

    def test_pre_generated_metadata_not_string(self):

        path = os.path.join(self.metadata_file_dir, 'not-string.xml')
        context = metadata.PreGeneratedMetadataContext(path)
        unit = self._generate_rpm('not_string')

        unit.metadata['repodata']['whatisthis'] = 1

        context._open_metadata_file_handle()
        context._add_unit_pre_generated_metadata('whatisthis', unit)
        context._close_metadata_file_handle()

        self.assertEqual(os.path.getsize(path), 0)

    # -- primary.xml context testing -------------------------------------------

    def test_primary_file_creation(self):

        path = os.path.join(self.metadata_file_dir,
                            metadata.REPO_DATA_DIR_NAME,
                            metadata.PRIMARY_XML_FILE_NAME)

        context = metadata.PrimaryXMLFileContext(self.metadata_file_dir, 0)

        context._open_metadata_file_handle()
        context._close_metadata_file_handle()

        self.assertTrue(os.path.exists(path))

    def test_primary_opening_tag(self):

        path = os.path.join(self.metadata_file_dir,
                            metadata.REPO_DATA_DIR_NAME,
                            metadata.PRIMARY_XML_FILE_NAME)

        context = metadata.PrimaryXMLFileContext(self.metadata_file_dir, 0)

        context._open_metadata_file_handle()
        context._write_root_tag_open()
        context._close_metadata_file_handle()

        self.assertNotEqual(os.path.getsize(path), 0)

        with gzip.open(path, 'r') as primary_handle:

            content = primary_handle.read()

            self.assertTrue(content.startswith('<metadata'))
            self.assertEqual(content.count('xmlns="%s"' % metadata.COMMON_NAMESPACE), 1)
            self.assertEqual(content.count('xmlns:rpm="%s"' % metadata.RPM_NAMESPACE), 1)
            self.assertEqual(content.count('packages="0"'), 1)

    def test_primary_closing_tag(self):

        context = metadata.PrimaryXMLFileContext(self.metadata_file_dir, 0)
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
                            metadata.REPO_DATA_DIR_NAME,
                            metadata.PRIMARY_XML_FILE_NAME)

        unit = self._generate_rpm('seems-legit')

        context = metadata.PrimaryXMLFileContext(self.metadata_file_dir, 1)

        context._open_metadata_file_handle()
        context.add_unit_metadata(unit)
        context._close_metadata_file_handle()

        handle = gzip.open(path, 'r')
        content = handle.read()
        handle.close()

        self.assertEqual(content, 'PRIMARY')

    def test_primary_with_keyword(self):

        with metadata.PrimaryXMLFileContext(self.metadata_file_dir, 0):
            pass

        path = os.path.join(self.metadata_file_dir,
                            metadata.REPO_DATA_DIR_NAME,
                            metadata.PRIMARY_XML_FILE_NAME)

        self.assertTrue(os.path.exists(path))
        # the xml header, opening, and closing tags should have been written
        self.assertNotEqual(os.path.getsize(path), 0)

        with gzip.open(path, 'r') as primary_handle:

            content_lines = primary_handle.readlines()

            self.assertEqual(len(content_lines), 3)
            self.assertEqual(content_lines[0], '<?xml version="1.0" encoding="UTF-8"?>\n')
            self.assertEqual(content_lines[2], '</metadata>\n')

    def test_primary_with_keyword_and_add_unit(self):

        unit = self._generate_rpm('with-context')

        with metadata.PrimaryXMLFileContext(self.metadata_file_dir, 1) as context:

            try:
                context.add_unit_metadata(unit)

            except Exception, e:
                self.fail(e.message)

    # -- other.xml context testing ---------------------------------------------

    def test_other_file_creation(self):

        path = os.path.join(self.metadata_file_dir,
                            metadata.REPO_DATA_DIR_NAME,
                            metadata.OTHER_XML_FILE_NAME)

        context = metadata.OtherXMLFileContext(self.metadata_file_dir, 0)

        context._open_metadata_file_handle()
        context._close_metadata_file_handle()

        self.assertTrue(os.path.exists(path))

    def test_other_opening_tag(self):

        path = os.path.join(self.metadata_file_dir,
                            metadata.REPO_DATA_DIR_NAME,
                            metadata.OTHER_XML_FILE_NAME)

        context = metadata.OtherXMLFileContext(self.metadata_file_dir, 0)

        context._open_metadata_file_handle()
        context._write_root_tag_open()
        context._close_metadata_file_handle()

        self.assertNotEqual(os.path.getsize(path), 0)

        with gzip.open(path, 'r') as other_handle:

            context = other_handle.read()

            self.assertTrue(context.startswith('<otherdata'))
            self.assertEqual(context.count('xmlns="%s"' % metadata.OTHER_NAMESPACE), 1)
            self.assertEqual(context.count('packages="0"'), 1)

    def test_other_closing_tag(self):

        context = metadata.OtherXMLFileContext(self.metadata_file_dir, 0)
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
                            metadata.REPO_DATA_DIR_NAME,
                            metadata.OTHER_XML_FILE_NAME)

        unit = self._generate_rpm('uh-huh')

        context = metadata.OtherXMLFileContext(self.metadata_file_dir, 1)

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
                            metadata.REPO_DATA_DIR_NAME,
                            metadata.FILE_LISTS_XML_FILE_NAME)

        context = metadata.FilelistsXMLFileContext(self.metadata_file_dir, 0)

        context._open_metadata_file_handle()
        context._close_metadata_file_handle()

        self.assertTrue(os.path.exists(path))


    def test_filelists_opening_tag(self):

        path = os.path.join(self.metadata_file_dir,
                            metadata.REPO_DATA_DIR_NAME,
                            metadata.FILE_LISTS_XML_FILE_NAME)

        context = metadata.FilelistsXMLFileContext(self.metadata_file_dir, 0)

        context._open_metadata_file_handle()
        context._write_root_tag_open()
        context._close_metadata_file_handle()

        self.assertNotEqual(os.path.getsize(path), 0)

        with gzip.open(path, 'r') as filelists_handle:

            content = filelists_handle.read()

            self.assertTrue(content.startswith('<filelists'))
            self.assertEqual(content.count('xmlns="%s"' % metadata.FILE_LISTS_NAMESPACE), 1)
            self.assertEqual(content.count('packages="0"'), 1)

    def test_filelists_closing_tag(self):

        context = metadata.FilelistsXMLFileContext(self.metadata_file_dir, 0)
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
                            metadata.REPO_DATA_DIR_NAME,
                            metadata.FILE_LISTS_XML_FILE_NAME)

        unit = self._generate_rpm('ive-got-files')

        context = metadata.FilelistsXMLFileContext(self.metadata_file_dir, 1)

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
                            metadata.REPO_DATA_DIR_NAME,
                            metadata.UPDATE_INFO_XML_FILE_NAME)

        context = metadata.UpdateinfoXMLFileContext(self.metadata_file_dir)

        context._open_metadata_file_handle()
        context._close_metadata_file_handle()

        self.assertTrue(os.path.exists(path))

    def test_updateinfo_opening_closing_tags(self):

        path = os.path.join(self.metadata_file_dir,
                            metadata.REPO_DATA_DIR_NAME,
                            metadata.UPDATE_INFO_XML_FILE_NAME)

        context = metadata.UpdateinfoXMLFileContext(self.metadata_file_dir)

        context._open_metadata_file_handle()

        self.assertRaises(NotImplementedError, context._write_root_tag_close)

        context._write_root_tag_open()

        try:
            context._write_root_tag_close()

        except Exception, e:
            self.fail(e.message)

        context._close_metadata_file_handle()

        self.assertNotEqual(os.path.getsize(path), 0)

        with gzip.open(path, 'r') as updateinfo_handle:

            content = updateinfo_handle.read()

            self.assertEqual(content, '<updates>\n</updates>\n')

    def test_updateinfo_unit_metadata(self):

        path = os.path.join(self.metadata_file_dir,
                            metadata.REPO_DATA_DIR_NAME,
                            metadata.UPDATE_INFO_XML_FILE_NAME)

        handle = open(os.path.join(DATA_DIR, 'updateinfo.xml'), 'r')
        generator = packages.package_list_generator(handle, 'update',
                                                    updateinfo.process_package_element)

        erratum_unit = next(generator)

        # just checking
        self.assertEqual(erratum_unit.unit_key['id'], 'RHEA-2010:9999')

        context = metadata.UpdateinfoXMLFileContext(self.metadata_file_dir)
        context._open_metadata_file_handle()
        context.add_unit_metadata(erratum_unit)
        context._close_metadata_file_handle()

        self.assertNotEqual(os.path.getsize(path), 0)

        with gzip.open(path, 'r') as updateinfo_handle:

            content = updateinfo_handle.read()

            self.assertEqual(content.count('from="enhancements@redhat.com"'), 1)
            self.assertEqual(content.count('status="final"'), 1)
            self.assertEqual(content.count('type="enhancements"'), 1)
            self.assertEqual(content.count('version="1"'), 1)
            self.assertEqual(content.count('<id>RHEA-2010:9999</id>'), 1)
            self.assertEqual(content.count('<collection short="F13PTP">'), 1)
            self.assertEqual(content.count('<package'), 2)
            self.assertEqual(content.count('<sum type="md5">f3c197a29d9b66c5b65c5d62b25db5b4</sum>'), 1)

