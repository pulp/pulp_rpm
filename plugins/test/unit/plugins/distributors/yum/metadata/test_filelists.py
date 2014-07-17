import shutil
import tempfile
import unittest
from xml.dom import pulldom

import mock

from pulp_rpm.plugins.distributors.yum.metadata.filelists import FilelistsXMLFileContext


class FilelistsXMLFileContextTests(unittest.TestCase):

    def setUp(self):
        self.working_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.working_dir)

    def test_init(self):
        context = FilelistsXMLFileContext(self.working_dir, 3)
        self.assertEquals(context.fast_forward, False)
        self.assertEquals(context.num_packages, 3)

    def test_initialize_no_fast_forward(self):
        context = FilelistsXMLFileContext(self.working_dir, 3)
        # test to make sure we don't fail on initializing without fast forwarding
        context.initialize()

    def test_initialize_fast_forward(self):
        context = FilelistsXMLFileContext(self.working_dir, 3)
        context._open_metadata_file_handle = mock.Mock()
        context._write_file_header = mock.Mock()
        context.fast_forward = True
        node = mock.Mock(nodeName='filelists', attributes={'packages': mock.Mock(value='2')})
        end_node = mock.Mock(nodeName='filelists')
        node2 = mock.Mock(nodeName='filelists', attributes={'packages': mock.Mock(value='2')})

        context.xml_generator = [(pulldom.START_ELEMENT, node),
                                 (pulldom.END_ELEMENT, end_node),
                                 (pulldom.START_ELEMENT, node2)]

        context.initialize()

        self.assertEquals('5', node.attributes['packages'].value)
        # Check that we stopped processing at the end tag
        self.assertEquals('2', node2.attributes['packages'].value)

    def test_add_unit_metadata(self):
        context = FilelistsXMLFileContext(self.working_dir, 3)
        context.metadata_file_handle = mock.Mock()

        context.add_unit_metadata(mock.Mock(metadata={'repodata': {'filelists': 'bar'}}))

        context.metadata_file_handle.write.assert_called_once_with('bar')

