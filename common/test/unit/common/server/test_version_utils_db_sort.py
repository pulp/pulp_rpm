import pymongo
from pulp.server.db import connection

from pulp_rpm.common.version_utils import encode
from pulp_rpm.devel import rpm_support_base


class DatabaseSortTests(rpm_support_base.PulpRPMTests):
    """
    Tests using the database's sort capabilities rather than Python's to be closer to the
    actual usage.  This is in the server sub-package so it will not be tested on python-2.4
    platforms
    """

    def setUp(self):
        super(DatabaseSortTests, self).setUp()
        self.db = connection._DATABASE.test_version_compare

    def tearDown(self):
        connection._DATABASE.drop_collection('test_version_compare')

    def test_numbers(self):
        # If both the elements are numbers, the larger number is considered newer. So 5 is newer
        # than 4 and 10 is newer than 2.
        self.assert_greater_than_or_equal('5', '4')
        self.assert_greater_than_or_equal('1.2', '1.1')
        self.assert_greater_than_or_equal('3.9', '3.1')
        self.assert_greater_than_or_equal('3.10', '3.9')
        self.assert_greater_than_or_equal('3.11', '3.10')

    def test_letters(self):
        self.assert_greater_than_or_equal('beta', 'alpha')
        self.assert_greater_than_or_equal('0.2.beta.1', '0.2.alpha.17')

    def test_letter_case(self):
        # If both the elements are alphabetic, they are compared using the Unix strcmp function,
        # with the greater string resulting in a newer element. So 'add' is newer than 'ZULU'
        # (because lowercase characters win in strcmp comparisons).
        self.assert_greater_than_or_equal('add', 'ZULU')  # see fedora link in version_utils

    def test_letters_v_numbers(self):
        # If one of the elements is a number, while the other is alphabetic, the numeric elements is
        # considered newer. So 10 is newer than 'abc', and 0 is newer than 'Z'.
        self.assert_greater_than_or_equal('0', 'Z')
        self.assert_greater_than_or_equal('10', 'abc')

    def test_mixed(self):
        # '2a' is older than '2.0', because numbers are considered newer than letters.
        self.assert_greater_than_or_equal('2.0', '2a')

    def test_different_length_ints(self):
        # The elements in the list are compared one by one using the following algorithm. In case
        # one of the lists run out, the other label wins as the newer label. So, for example,
        # (1, 2) is newer than (1, 1), and (1, 2, 0) is newer than (1, 2).
        self.assert_greater_than_or_equal('1.2', '1.1.0')
        self.assert_greater_than_or_equal('1.2.0', '1.2')

    def test_different_length_letters(self):
        # If both the elements are alphabetic, they are compared using the Unix strcmp function,
        # with the greater string resulting in a newer element. So 'aba' is newer than 'ab'.
        self.assert_greater_than_or_equal('aba', 'ab')

    def test_leading_zeroes(self):
        self.assert_greater_than_or_equal('1.002', '1.1')

    def assert_greater_than_or_equal(self, version1, version2):
        encoded1 = encode(version1)
        encoded2 = encode(version2)

        self.db.insert({'version': version1, 'version_sort_index': encoded1}, safe=True)
        self.db.insert({'version': version2, 'version_sort_index': encoded2}, safe=True)

        sorted_versions = self.db.find({}).sort([('version_sort_index', pymongo.DESCENDING)])

        msg = '[%s, %s] was less than [%s, %s]' % (version1, encoded1, version2, encoded2)
        self.assertEqual(sorted_versions[0]['version'], version1, msg=msg)

        self.db.remove()  # clean up for multiple calls to this in a single test
