import pickle
import os
from StringIO import StringIO
import unittest

import mock

from pulp_rpm.yum_plugin import updateinfo
from pulp_rpm.plugins.importers.yum import upload


DATA_DIR = os.path.abspath(os.path.dirname(__file__)) + '/../../data/'
RPM_USUAL_NAME = DATA_DIR + 'pulp-test-package-0.3.1-1.fc11.x86_64.rpm'
RPM_UNUSUAL_NAME = DATA_DIR + 'unusual-rpm-filename.data'
SRPM_USUAL_NAME = DATA_DIR + 'test-srpm01-1.0-1.src.rpm'


class TestUploadFilenames(unittest.TestCase):

    def test_usual_filename(self):
        unit_key, metadata = upload._generate_rpm_data(RPM_USUAL_NAME, {})
        self.assertEquals('pulp-test-package-0.3.1-1.fc11.x86_64.rpm', metadata['filename'])

    def test_unusual_filename(self):
        unit_key, metadata = upload._generate_rpm_data(RPM_UNUSUAL_NAME, {})
        self.assertEquals('pulp-test-package-0.3.1-1.fc11.x86_64.rpm', metadata['filename'])

    def test_srpm_filename(self):
        unit_key, metadata = upload._generate_rpm_data(SRPM_USUAL_NAME, {})
        self.assertEquals('test-srpm01-1.0-1.src.rpm', metadata['filename'])

