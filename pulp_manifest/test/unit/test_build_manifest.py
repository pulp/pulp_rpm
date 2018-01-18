import os
import unittest
from pulp_manifest import build_manifest

DATA_DIR = os.path.abspath(os.path.dirname(__file__)) + '/../data'


class TestBuildManifest(unittest.TestCase):

    def test_get_digest(self):
        digest = build_manifest.get_digest(os.path.join(DATA_DIR, 'a.txt'))
        self.assertEquals('a1028f793b0aae9c51fa83e39975b254d78947620868f09e4a648e73486a623c',
                          digest)

    def test_traverse_dir(self):
        manifest = build_manifest.traverse_dir(DATA_DIR)
        self.assertEquals(len(manifest), 2)

if __name__ == '__main__':
    unittest.main()
