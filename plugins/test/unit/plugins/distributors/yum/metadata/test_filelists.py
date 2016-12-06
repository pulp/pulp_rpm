import shutil
import tempfile
import unittest

import mock

from pulp_rpm.plugins.distributors.yum.metadata.filelists import FilelistsXMLFileContext


class FilelistsXMLFileContextTests(unittest.TestCase):
    def setUp(self):
        self.working_dir = tempfile.mkdtemp()
        self.unit = mock.Mock()
        self.unit.render_filelists.return_value = 'somexml'

    def tearDown(self):
        shutil.rmtree(self.working_dir)

    def test_init(self):
        context = FilelistsXMLFileContext(self.working_dir, 3)
        self.assertEquals(context.fast_forward, False)
        self.assertEquals(context.num_packages, 3)

    def test_add_unit_metadata(self):
        context = FilelistsXMLFileContext(self.working_dir, 3, 'sha256')
        context.metadata_file_handle = mock.Mock()

        context.add_unit_metadata(self.unit)

        context.metadata_file_handle.write.assert_called_once_with('somexml')
        self.unit.render_filelists.assert_called_once_with('sha256')

    def test_add_unit_metadata_unicode(self):
        """
        Test that the filelists repodata is passed as a str even if it's a unicode object.
        """
        context = FilelistsXMLFileContext(self.working_dir, 3, 'sha256')
        context.metadata_file_handle = mock.Mock()
        expected_call = u'some unicode'
        self.unit.render_filelists.return_value = expected_call

        context.add_unit_metadata(self.unit)
        context.metadata_file_handle.write.assert_called_once_with(expected_call)
        self.unit.render_filelists.assert_called_once_with('sha256')
