import shutil
import tempfile
import unittest
from xml.dom import pulldom

import mock

from pulp_rpm.plugins.distributors.yum.metadata.other import OtherXMLFileContext


class PrimaryXMLFileContextTests(unittest.TestCase):

    def setUp(self):
        self.working_dir = tempfile.mkdtemp()
        self.context = OtherXMLFileContext(self.working_dir, 3)

    def tearDown(self):
        shutil.rmtree(self.working_dir)

    def test_init(self):
        self.assertEquals(self.context.fast_forward, False)
        self.assertEquals(self.context.num_packages, 3)

    def test_initialize_no_fast_forward(self):
        # test to make sure we don't fail on initializing without fast forwarding
        self.context.initialize()

    def test_initialize_fast_forward(self):
        self.context._open_metadata_file_handle = mock.Mock()
        self.context._write_file_header = mock.Mock()
        self.context.fast_forward = True
        node = mock.Mock(nodeName='otherdata', attributes={'packages': mock.Mock(value='2')})
        end_node = mock.Mock(nodeName='otherdata')
        node2 = mock.Mock(nodeName='otherdata', attributes={'packages': mock.Mock(value='2')})

        self.context.xml_generator = [(pulldom.START_ELEMENT, node),
                                      (pulldom.END_ELEMENT, end_node),
                                      (pulldom.START_ELEMENT, node2)]

        self.context.initialize()

        self.assertEquals('5', node.attributes['packages'].value)
        # Check that we stopped processing at the end tag
        self.assertEquals('2', node2.attributes['packages'].value)

    def test_add_unit_metadata(self):
        self.context.metadata_file_handle = mock.Mock()
        self.context.add_unit_metadata(mock.Mock(metadata={'repodata': {'other': 'bar'}}))
        self.context.metadata_file_handle.write.assert_called_once_with('bar')

