from unittest import TestCase
from datetime import datetime
from pulp_rpm.app.shared_utils import is_previous_version, urlpath_sanitize, parse_time


class TestSharedUtils(TestCase):
    """Test shared_utils functions."""

    def test_is_previous_version(self):
        """Test version-comparator."""
        # Versions must be int or 1.2.3
        # non-integer versions return False, always
        # True if version <= target

        # None
        self.assertTrue(is_previous_version(None, "1"))
        self.assertTrue(is_previous_version("1", None))
        self.assertTrue(is_previous_version(None, None))

        # Integer versions
        # v = t : v < t : v > t
        self.assertTrue(is_previous_version("1", "1"))
        self.assertTrue(is_previous_version("1", "2"))
        self.assertFalse(is_previous_version("2", "1"))

        # m.n
        # v = t : v m. < t m. : v m.n < t m.n : v m. > t.m : v m.n > t.m.n
        self.assertTrue(is_previous_version("1.2", "1.2"))
        self.assertTrue(is_previous_version("1.2", "2.2"))
        self.assertTrue(is_previous_version("1.2", "1.3"))
        self.assertFalse(is_previous_version("2.2", "1.2"))
        self.assertFalse(is_previous_version("2.2", "2.1"))

        # non-numeric : v not-digits : t not-digits : v-dot-nondigits : t dot-non-digits
        self.assertFalse(is_previous_version("foo", "1.2"))
        self.assertFalse(is_previous_version("1.2", "bar"))
        self.assertFalse(is_previous_version("foo.2", "2.1"))
        self.assertFalse(is_previous_version("1.2", "bar.1"))
        self.assertTrue(is_previous_version("1.foo", "2.bar"))
        self.assertFalse(is_previous_version("1.foo", "1.bar"))

    def test_urlpath_sanitize(self):
        """Test urljoin-replacement."""
        # arbitrary number of args become one single-slash-separated string
        a_expected = "a"
        ab_expected = "a/b"
        abc_expected = "a/b/c"

        # a /a a/ /a/
        self.assertEqual(a_expected, urlpath_sanitize("a"))
        self.assertEqual(a_expected, urlpath_sanitize("/a"))
        self.assertEqual(a_expected, urlpath_sanitize("a/"))
        self.assertEqual(a_expected, urlpath_sanitize("/a/"))

        # a b : a/ b : /a b : a b/ : a /b : a /b/ : a/ /b
        self.assertEqual(ab_expected, urlpath_sanitize("a", "b"))
        self.assertEqual(ab_expected, urlpath_sanitize("a/", "b"))
        self.assertEqual(ab_expected, urlpath_sanitize("/a", "b"))
        self.assertEqual(ab_expected, urlpath_sanitize("a", "b/"))
        self.assertEqual(ab_expected, urlpath_sanitize("a", "/b"))
        self.assertEqual(ab_expected, urlpath_sanitize("a", "/b/"))
        self.assertEqual(ab_expected, urlpath_sanitize("a/", "/b"))
        self.assertEqual(ab_expected, urlpath_sanitize("a/", "", "/b"))
        self.assertEqual(ab_expected, urlpath_sanitize("a/", "/", "/b"))

        # a b c : a /b/ /c : /a/ /b/ /c/
        self.assertEqual(abc_expected, urlpath_sanitize("a", "b", "c"))
        self.assertEqual(abc_expected, urlpath_sanitize("a", "/b/", "/c"))
        self.assertEqual(abc_expected, urlpath_sanitize("/a/", "/b/", "/c/"))

    def test_parse_time(self):
        """Test parse_time."""
        ts_input = "1626714399"
        ts_expected = 1626714399
        iso_input = "2012-01-27 16:08:06"
        iso_expected = datetime(2012, 1, 27, 16, 8, 6)

        self.assertEqual(ts_expected, parse_time(ts_input))
        self.assertNotEqual(ts_input, parse_time(ts_input))

        self.assertEqual(iso_expected, parse_time(iso_input))
        self.assertNotEqual(iso_input, parse_time(iso_input))

        self.assertIsNone(parse_time("abcd"))
