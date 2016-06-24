# -*- coding: utf-8 -*-
import re

from cStringIO import StringIO

import mock

from pulp.common.compat import unittest
from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.distributors.yum.metadata.updateinfo import UpdateinfoXMLFileContext


class UpdateinfoXMLFileContextTests(unittest.TestCase):
    """
    Test correct generation of updateinfo.xml file
    """
    @mock.patch('pulp.plugins.util.metadata_writer.MetadataFileContext._open_metadata_file_handle')
    def setUp(self, mock_parent_open_file_handle):
        self.context = UpdateinfoXMLFileContext('/foo', checksum_type='sha256')
        self.context.metadata_file_handle = StringIO()
        self.context._open_metadata_file_handle()

    def _generate_erratum_unit(self):
        """
        Generate erratum unit.
        """
        packages = [{'src': 'pulp-test-package-0.3.1-1.fc22.src.rpm',
                     'name': 'pulp-test-package',
                     'arch': 'x86_64',
                     'sums': 'sums',
                     'filename': 'pulp-test-package-0.3.1-1.fc22.x86_64.rpm',
                     'epoch': '0',
                     'version': '0.3.1',
                     'release': '1.fc22',
                     'type': 'sha256'},
                    {'src': 'another-pulp-test-package-3.2-1.fc22.src.rpm',
                     'name': 'another-pulp-test-package',
                     'arch': 'x86_64',
                     'filename': 'another-pulp-test-package-0.3.1-1.fc22.x86_64.rpm',
                     'epoch': '0',
                     'version': '3.2',
                     'release': '1.fc22',
                     'sum': ['md5', 'md5_checksum', 'sha256', 'sha256_checksum']}]
        unit_data = {'errata_id': 'RHSA-2014:0042',
                     'title': 'Some Title',
                     'release': '2',
                     'rights': 'You have the right to remain silent.',
                     'solution': 'Open Source is the solution to your problems.',
                     'severity': 'High',
                     'summary': 'A Summary',
                     # Note that pushcount is an int. This should be OK (no exceptions).
                     'pushcount': 1,
                     'status': 'symbol',
                     'type': 'security',
                     'version': '2.4.1',
                     'issued': '2014-05-27 00:00:00',
                     'references': [{'href': 'https://bugzilla.hostname/bug.cgi?id=XXXXX',
                                     'type': 'bugzilla',
                                     'id': 'XXXXX',
                                     'title': 'some title'}],
                     'updated': '2014-05-28 00:00:00',
                     'pkglist': [{'packages': packages, 'name': 'test-name', 'short': ''},
                                 {'packages': packages, 'name': 'test-name', 'short': ''}]}
        return models.Errata(**unit_data)

    def test_handles_integer_pushcount(self):
        """
        Test that the pushcount of type integer handled well.

        We had a bug[0] wherein uploaded errata couldn't be published because the pushcount would
        be represented as an int. Synchronized errata would have this field represented as a
        basestring. The descrepancy between these has been filed as a separate issue[1].

        [0] https://bugzilla.redhat.com/show_bug.cgi?id=1100848
        [1] https://bugzilla.redhat.com/show_bug.cgi?id=1101728
        """
        erratum = self._generate_erratum_unit()
        erratum.description = 'A Description'

        self.context.add_unit_metadata(erratum)

        generated_xml = self.context.metadata_file_handle.getvalue()
        self.assertTrue('<pushcount>1</pushcount>' in generated_xml)

    def test_no_description(self):
        """
        Test that if the erratum has no description, the empty description element should be
        generated.

        We had a bug[0] wherein an empty or missing description would result in
        XML that did not include a description element. The corresponding upstream
        repo (epel5) did have a description element that was merely empty, so the
        distributor was modified to always include the description element.

        [0] https://bugzilla.redhat.com/show_bug.cgi?id=1138475
        """
        erratum = self._generate_erratum_unit()

        self.context.add_unit_metadata(erratum)

        generated_xml = self.context.metadata_file_handle.getvalue()
        self.assertTrue(re.search('<description */>', generated_xml) is not None)

    def test_no_duplicated_pkglists(self):
        """
        Test that no duplicated pkglists are generated.
        """
        erratum = self._generate_erratum_unit()
        expected_pkg_str = '<package src="pulp-test-package-0.3.1-1.fc22.src.rpm" ' \
                           'name="pulp-test-package" epoch="0" version="0.3.1" '\
                           'release="1.fc22" arch="x86_64">'
        self.context.add_unit_metadata(erratum)

        generated_xml = self.context.metadata_file_handle.getvalue()
        self.assertEqual(generated_xml.count(expected_pkg_str), 1)

    def test__get_package_checksum_tuple_sums_field(self):
        """
        Test that the `sums` package field is handled correctly.
        """
        erratum = self._generate_erratum_unit()
        package_with_sums_field = erratum.pkglist[0]['packages'][0]
        result = self.context._get_package_checksum_tuple(package_with_sums_field)
        expected_checksum_tuple = ('sha256', 'sums')
        self.assertEqual(result, expected_checksum_tuple)

    def test__get_package_checksum_tuple_repo_type(self):
        """
        Test that the package checksum of the repository checksum type is published if available.
        """
        erratum = self._generate_erratum_unit()
        package_with_multiple_checksums = erratum.pkglist[0]['packages'][1]
        result = self.context._get_package_checksum_tuple(package_with_multiple_checksums)
        expected_checksum_tuple = ('sha256', 'sha256_checksum')
        self.assertEqual(result, expected_checksum_tuple)

    def test__get_package_checksum_tuple_no_checksum(self):
        """
        Test that the package checksum is not published if the requested checksum type is not
        available.
        """
        erratum = self._generate_erratum_unit()
        self.context.checksum_type = 'sha1'
        package_with_multiple_checksums = erratum.pkglist[0]['packages'][1]
        result = self.context._get_package_checksum_tuple(package_with_multiple_checksums)
        expected_checksum_tuple = ()
        self.assertEqual(result, expected_checksum_tuple)

    def test_add_errata_unit_metadata(self):
        """
        Test the generation of erratum unit.
        """
        erratum = self._generate_erratum_unit()
        self.context.add_unit_metadata(erratum)
        generated_xml = self.context.metadata_file_handle.getvalue()
        expected_xml = '<update status="symbol" from="" version="2.4.1" type="security">\n' \
                       '  <id>RHSA-2014:0042</id>\n' \
                       '  <issued date="2014-05-27 00:00:00" />\n' \
                       '  <reboot_suggested>False</reboot_suggested>\n' \
                       '  <title>Some Title</title>\n' \
                       '  <release>2</release>\n' \
                       '  <rights>You have the right to remain silent.</rights>\n' \
                       '  <solution>Open Source is the solution to your problems.</solution>\n' \
                       '  <severity>High</severity>\n' \
                       '  <summary>A Summary</summary>\n' \
                       '  <pushcount>1</pushcount>\n' \
                       '  <description />\n' \
                       '  <updated date="2014-05-28 00:00:00" />\n' \
                       '  <references>\n' \
                       '    <reference href="https://bugzilla.hostname/bug.cgi?id=XXXXX" ' \
                       'type="bugzilla" id="XXXXX" title="some title" />\n' \
                       '  </references>\n' \
                       '  <pkglist>\n' \
                       '    <collection short="">\n' \
                       '      <name>test-name</name>\n' \
                       '      <package src="pulp-test-package-0.3.1-1.fc22.src.rpm" ' \
                       'name="pulp-test-package" epoch="0" version="0.3.1" release="1.fc22" ' \
                       'arch="x86_64">\n' \
                       '        <filename>pulp-test-package-0.3.1-1.fc22.x86_64.rpm</filename>\n' \
                       '        <sum type="sha256">sums</sum>\n' \
                       '        <reboot_suggested>False</reboot_suggested>\n' \
                       '      </package>\n' \
                       '      <package src="another-pulp-test-package-3.2-1.fc22.src.rpm" ' \
                       'name="another-pulp-test-package" epoch="0" version="3.2" release="1.fc22" ' \
                       'arch="x86_64">\n' \
                       '        <filename>another-pulp-test-package-0.3.1-1.fc22.x86_64.rpm</filename>\n' \
                       '        <sum type="sha256">sha256_checksum</sum>\n' \
                       '        <reboot_suggested>False</reboot_suggested>\n' \
                       '      </package>\n' \
                       '    </collection>\n' \
                       '  </pkglist>\n' \
                       '</update>\n'
        self.assertEqual(generated_xml, expected_xml)
