"""
Tests for the pulp_rpm.plugins.distributors.yum.metadata.updateinfo module.
"""
import copy
import re
import unittest

import mock

from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.distributors.yum.metadata import updateinfo


class UpdateinfoXMLFileContextTests(unittest.TestCase):
    """
    This is a test superclass for testing the UpdateinfoXMLFileContext class. It's setUp() method
    contructs one on self.updateinfo_xml_file_context.
    """

    def setUp(self):
        """
        Build an UpdateinfoXMLFileContext and store it on self.updateinfo_xml_file_context.
        """
        nevra_in_repo = set([('pulp-test-package', '0', '0.3.1', '1.fc22', 'x86_64')])
        self.updateinfo_xml_file_context = updateinfo.UpdateinfoXMLFileContext('some_working_dir',
                                                                               nevra_in_repo)
        # Let's fake the metadata_file_handle attribute so we can inspect calls to it.
        self.updateinfo_xml_file_context.metadata_file_handle = mock.MagicMock()

        self.packages = [{'src': 'pulp-test-package-0.3.1-1.fc22.src.rpm',
                          'name': 'pulp-test-package',
                          'arch': 'x86_64',
                          'sums': 'sums',
                          'filename': 'pulp-test-package-0.3.1-1.fc22.x86_64.rpm',
                          'epoch': '0',
                          'version': '0.3.1',
                          'release': '1.fc22',
                          'type': 'sha256'}]
        self.unit_data = {
            'errata_id': 'RHSA-2014:0042',
            'title': 'Some Title',
            'release': '2',
            'rights': 'You have the right to remain silent.',
            'solution': 'Open Source is the solution to your problems.',
            'severity': 'High',
            'summary': 'A Summary',
            # Note that pushcount is an int and not a string. This should be OK (no exceptions).
            'pushcount': 1,
            'status': 'symbol',
            'type': 'security',
            'version': '2.4.1',
            'issued': '2014-05-27 00:00:00',
            'reboot_suggested': True,
            'references': [],
            'updated': '2014-05-28 00:00:00',
            'pkglist': [{'packages': self.packages, 'name': 'test-name', 'short': ''},
                        {'packages': self.packages, 'name': 'test-name', 'short': ''}]}


class AddUnitMetadataTests(UpdateinfoXMLFileContextTests):
    """
    Tests the UpdateinfoXMLFileContext.add_unit_metadata() method.
    """

    def test_handles_integer_pushcount(self):
        """
        Test that the pushcount of type integer handled well.

        We had a bug[0] wherein uploaded errata couldn't be published because the pushcount would
        be represented as an int. Synchronized errata would have this field represented as a
        basestring. The descrepancy between these has been filed as a separate issue[1].

        [0] https://bugzilla.redhat.com/show_bug.cgi?id=1100848
        [1] https://bugzilla.redhat.com/show_bug.cgi?id=1101728
        """
        unit_data = copy.copy(self.unit_data)
        unit_data['description'] = 'A Description'
        erratum = models.Errata(**unit_data)

        self.updateinfo_xml_file_context.add_unit_metadata(erratum)

        self.assertEqual(self.updateinfo_xml_file_context.metadata_file_handle.write.call_count, 1)
        xml = self.updateinfo_xml_file_context.metadata_file_handle.write.mock_calls[0][1][0]
        self.assertTrue('<pushcount>1</pushcount>' in xml)

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
        erratum = models.Errata(**self.unit_data)

        self.updateinfo_xml_file_context.add_unit_metadata(erratum)

        self.assertEqual(self.updateinfo_xml_file_context.metadata_file_handle.write.call_count, 1)
        xml = self.updateinfo_xml_file_context.metadata_file_handle.write.mock_calls[0][1][0]
        self.assertTrue(re.search('<description */>', xml) is not None)

    def test_reboot_suggested(self):
        """
        Test that when reboot_suggested is True, the element is present in the XML
        """
        erratum = models.Errata(**self.unit_data)
        erratum.reboot_suggested = True

        self.updateinfo_xml_file_context.add_unit_metadata(erratum)

        self.assertEqual(self.updateinfo_xml_file_context.metadata_file_handle.write.call_count, 1)
        xml = self.updateinfo_xml_file_context.metadata_file_handle.write.mock_calls[0][1][0]
        self.assertTrue('reboot_suggested' in xml)

    def test_no_reboot_suggested(self):
        """
        Test that when reboot_suggested is False, the element is not present in the XML
        """
        erratum = models.Errata(**self.unit_data)
        erratum.reboot_suggested = False

        self.updateinfo_xml_file_context.add_unit_metadata(erratum)

        self.assertEqual(self.updateinfo_xml_file_context.metadata_file_handle.write.call_count, 1)
        xml = self.updateinfo_xml_file_context.metadata_file_handle.write.mock_calls[0][1][0]
        self.assertTrue('reboot_suggested' not in xml)

    def test_no_duplicated_pkglists(self):
        """
        Test that no duplicated pkglists are generated.
        """
        erratum = models.Errata(**self.unit_data)
        expected_pkg_str = '<package arch="x86_64" epoch="0" name="pulp-test-package"' \
                           ' release="1.fc22" src="pulp-test-package-0.3.1-1.fc22.src.rpm"' \
                           ' version="0.3.1">'

        self.updateinfo_xml_file_context.add_unit_metadata(erratum)

        self.assertEqual(self.updateinfo_xml_file_context.metadata_file_handle.write.call_count, 1)
        xml = self.updateinfo_xml_file_context.metadata_file_handle.write.mock_calls[0][1][0]
        self.assertEqual(xml.count(expected_pkg_str), 1)
