import unittest
import os

from pulp_rpm.common import file_utils, constants


DATA_DIR = os.path.abspath(os.path.dirname(__file__)) + '/../../data'


class TestFileUtils(unittest.TestCase):
    def setUp(self):
        self.test_file = os.path.join(DATA_DIR, "cert.key")

    def test_calculate_checksum(self):
        test_file = open(self.test_file)
        try:
            file_checksum = file_utils.calculate_checksum(test_file)
        finally:
            test_file.close()

        self.assertEquals(file_checksum, '4da653eb38433cd3bfb0910453f836267a91336'
                                         '635d23f047aaecca1b2b960cd')

    def test_calculate_size(self):
        test_file = open(self.test_file)
        try:
            file_size = file_utils.calculate_size(test_file)
        finally:
            test_file.close()

        self.assertEquals(file_size, 1675)


class MakePackagesRelativePathTests(unittest.TestCase):
    def test_PULP_PACKAGES_DIR(self):
        """Test that PULP_PACKAGES_DIR is in returned path."""
        self.assertTrue(file_utils.make_packages_relative_path("foo.rpm").startswith(
            constants.PULP_PACKAGES_DIR))

    def test_lower_letter(self):
        """Test if folder is created from name starting with lowercase letter."""
        expected = constants.PULP_PACKAGES_DIR + "/f/foo.rpm"
        result = file_utils.make_packages_relative_path("foo.rpm")
        self.assertEqual(expected, result)

    def test_upper_letter(self):
        """Test if folder is created from name starting with uppercase letter."""
        expected = constants.PULP_PACKAGES_DIR + "/f/Foo.rpm"
        result = file_utils.make_packages_relative_path("Foo.rpm")
        self.assertEqual(expected, result)

    def test_number(self):
        """Test if folder is created from name starting with number."""
        expected = constants.PULP_PACKAGES_DIR + "/1/1foo.rpm"
        result = file_utils.make_packages_relative_path("1foo.rpm")
        self.assertEqual(expected, result)

    def test_not_basename(self):
        """Test if correct path is returned when supplied filename is not basename."""
        expected = constants.PULP_PACKAGES_DIR + "/f/foo.rpm"
        result = file_utils.make_packages_relative_path("bar/foo.rpm")
        self.assertEqual(expected, result)
