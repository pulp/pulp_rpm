import os
import unittest

from pulp_rpm.plugins.importers.yum import upload
from pulp_rpm.plugins.db import models
from pulp.plugins.util import verification


DATA_DIR = os.path.abspath(os.path.dirname(__file__)) + '/../../data/'
RPM_USUAL_NAME = DATA_DIR + 'pulp-test-package-0.3.1-1.fc11.x86_64.rpm'
RPM_UNUSUAL_NAME = DATA_DIR + 'unusual-rpm-filename.data'
SRPM_USUAL_NAME = DATA_DIR + 'test-srpm01-1.0-1.src.rpm'


class TestUploadGenerateRpmData(unittest.TestCase):
    """
    Tests for upload._generate_rpm_data
    """
    def test_usual_filename(self):
        unit_key, metadata = upload._generate_rpm_data(models.RPM.TYPE, RPM_USUAL_NAME, {})
        self.assertEquals('pulp-test-package-0.3.1-1.fc11.x86_64.rpm', metadata['filename'])

    def test_unusual_filename(self):
        unit_key, metadata = upload._generate_rpm_data(models.RPM.TYPE, RPM_UNUSUAL_NAME, {})
        self.assertEquals('pulp-test-package-0.3.1-1.fc11.x86_64.rpm', metadata['filename'])

    def test_srpm_filename(self):
        unit_key, metadata = upload._generate_rpm_data(models.SRPM.TYPE, SRPM_USUAL_NAME, {})
        self.assertEquals('test-srpm01-1.0-1.src.rpm', metadata['filename'])

    def test_user_metadata_present_no_checksum_type(self):
        """
        Test that when user metadata is provided, but doesn't contain a checksum type, the default
        type is used.
        """
        unit_key, metadata = upload._generate_rpm_data(models.RPM.TYPE, RPM_USUAL_NAME, {})
        self.assertEquals(verification.TYPE_SHA256, unit_key['checksumtype'])

    def test_user_metadata_present_with_checksum_type(self):
        """
        Test that when user metadata is provided and contains a checksum type, that type is used
        """
        unit_key, metadata = upload._generate_rpm_data(models.RPM.TYPE,
                                                       RPM_USUAL_NAME,
                                                       {'checksum_type': verification.TYPE_MD5})
        self.assertEquals(verification.TYPE_MD5, unit_key['checksumtype'])
