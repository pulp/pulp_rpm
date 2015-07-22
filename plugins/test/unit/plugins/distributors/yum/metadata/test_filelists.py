import shutil
import tempfile
import unittest

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

    def test_add_unit_metadata(self):
        context = FilelistsXMLFileContext(self.working_dir, 3)
        context.metadata_file_handle = mock.Mock()

        context.add_unit_metadata(mock.Mock(metadata={'repodata': {'filelists': 'bar'}}))

        context.metadata_file_handle.write.assert_called_once_with('bar')

    def test_add_unit_metadata_unicode(self):
        """
        Test that the filelists repodata is passed as a str even if it's a unicode object.
        """
        context = FilelistsXMLFileContext(self.working_dir, 3)
        context.metadata_file_handle = mock.Mock()
        expected_call = 'some unicode'
        metadata = {
            'repodata': {'filelists': unicode(expected_call)}
        }

        context.add_unit_metadata(mock.Mock(metadata=metadata))
        context.metadata_file_handle.write.assert_called_once_with(expected_call)
