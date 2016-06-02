import shutil
import tempfile
import unittest

import mock

from pulp_rpm.plugins.distributors.yum.metadata.other import OtherXMLFileContext


class OtherXMLFileContextTests(unittest.TestCase):
    def setUp(self):
        self.working_dir = tempfile.mkdtemp()
        self.context = OtherXMLFileContext(self.working_dir, 3, 'sha256')
        self.unit = mock.Mock()
        self.unit.render_other.return_value = 'somexml'

    def tearDown(self):
        shutil.rmtree(self.working_dir)

    def test_init(self):
        self.assertEquals(self.context.fast_forward, False)
        self.assertEquals(self.context.num_packages, 3)

    def test_add_unit_metadata(self):
        self.context.metadata_file_handle = mock.Mock()
        self.context.add_unit_metadata(self.unit)
        self.context.metadata_file_handle.write.assert_called_once_with('somexml')
        self.unit.render_other.assert_called_once_with('sha256')

    def test_add_unit_metadata_unicode(self):
        """
        Test that the other repodata is passed as a str even if it's a unicode object.
        """
        self.context.metadata_file_handle = mock.Mock()
        expected_call = u'some unicode'
        self.unit.render_other.return_value = expected_call
        self.context.add_unit_metadata(self.unit)
        self.context.metadata_file_handle.write.assert_called_once_with(expected_call)
        self.unit.render_other.assert_called_once_with('sha256')
