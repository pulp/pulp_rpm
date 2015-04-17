"""
Tests for the pulp_rpm.plugins.distributors.yum.metadata.updateinfo module.
"""
import re
import unittest

from pulp.plugins import model
import mock

from pulp_rpm.common import ids
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
        self.updateinfo_xml_file_context = updateinfo.UpdateinfoXMLFileContext('some_working_dir')
        # Let's fake the metadata_file_handle attribute so we can inspect calls to it.
        self.updateinfo_xml_file_context.metadata_file_handle = mock.MagicMock()


class AddUnitMetadataTests(UpdateinfoXMLFileContextTests):
    """
    Tests the UpdateinfoXMLFileContext.add_unit_metadata() method.
    """

    def test_handles_integer_pushcount(self):
        """
        We had a bug[0] wherein uploaded errata couldn't be published because the pushcount would
        be represented as an int. Synchronized errata would have this field represented as a
        basestring. The descrepancy between these has been filed as a separate issue[1].

        [0] https://bugzilla.redhat.com/show_bug.cgi?id=1100848
        [1] https://bugzilla.redhat.com/show_bug.cgi?id=1101728
        """
        type_id = ids.TYPE_ID_ERRATA
        unit_key = {'id': 'RHSA-2014:0042'}
        metadata = {
            'title': 'Some Title',
            'release': '2',
            'rights': 'You have the right to remain silent.',
            'description': 'A Description',
            'solution': 'Open Source is the solution to your problems.',
            'severity': 'High',
            'summary': 'A Summary',
            # Note that pushcount is an int and not a string. This should be OK (no exceptions).
            'pushcount': 1,
            'status': 'symbol',
            'type': 'security',
            'version': '2.4.1',
            'issued': '2014-05-27',
            'reboot_suggested': 'true',
            'references': [],
        }
        storage_path = '/some/path'
        created = '2014-04-27'
        updated = '2014-04-28'
        erratum_unit = model.AssociatedUnit(type_id, unit_key, metadata, storage_path, created,
                                            updated)

        # This should not cause any Exception
        self.updateinfo_xml_file_context.add_unit_metadata(erratum_unit)

        self.assertEqual(self.updateinfo_xml_file_context.metadata_file_handle.write.call_count, 1)
        xml = self.updateinfo_xml_file_context.metadata_file_handle.write.mock_calls[0][1][0]
        self.assertTrue('<pushcount>1</pushcount>' in xml)

    def test_no_description(self):
        """
        We had a bug[0] wherein an empty or missing description would result in
        XML that did not include a description element. The corresponding upstream
        repo (epel5) did have a description element that was merely empty, so the
        distributor was modified to always include the description element.

        [0] https://bugzilla.redhat.com/show_bug.cgi?id=1138475
        """
        type_id = ids.TYPE_ID_ERRATA
        unit_key = {'id': 'RHSA-2014:0042'}
        metadata = {
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
            'issued': '2014-05-27',
            'reboot_suggested': 'true',
            'references': [],
        }
        storage_path = '/some/path'
        created = '2014-04-27'
        updated = '2014-04-28'
        erratum_unit = model.AssociatedUnit(type_id, unit_key, metadata, storage_path, created,
                                            updated)

        # This should not cause any Exception
        self.updateinfo_xml_file_context.add_unit_metadata(erratum_unit)

        self.assertEqual(self.updateinfo_xml_file_context.metadata_file_handle.write.call_count, 1)
        xml = self.updateinfo_xml_file_context.metadata_file_handle.write.mock_calls[0][1][0]
        self.assertTrue(re.search('<description */>', xml) is not None)
