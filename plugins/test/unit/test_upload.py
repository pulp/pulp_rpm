# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

import json
import os
import re
import unittest

import mock
from pulp.plugins.conduits.upload import UploadConduit
from pulp.plugins.config import PluginCallConfiguration
from pulp.plugins.model import Repository, SyncReport, Unit

from pulp_rpm.common.models import RPM, SRPM
from pulp_rpm.common import models
from pulp_rpm.plugins.importers.yum import upload
from pulp_rpm.plugins.importers.yum.parse import rpm


# this is here because we need to mock the function, but also keep a reference
# to the original
get_package_xml = rpm.get_package_xml


class TestUploadRPM(unittest.TestCase):
    def setUp(self):
        self.repo = Repository('repo1')
        self.conduit = UploadConduit(self.repo.id, 'yum_importer', 'user', 'me')
        self.metadata = json.loads(WALRUS_JSON)
        self.model = RPM.from_package_info(self.metadata)
        self.file_path = os.path.join(os.path.dirname(__file__), '../data/walrus-5.21-1.noarch.rpm')

    def wrap_get_package_xml(self, storage_path):
        return get_package_xml(self.file_path)

    @mock.patch('pulp_rpm.plugins.importers.yum.parse.rpm.get_package_xml', autospec=True)
    @mock.patch('shutil.move', autospec=True)
    def test_location_in_repodata(self, mock_copy, mock_get_xml):
        """This is in response to BZ 993452"""
        mock_get_xml.side_effect = self.wrap_get_package_xml
        unit = Unit(self.model.TYPE, self.model.unit_key, self.model.metadata, self.model.relative_path)
        self.conduit.init_unit = mock.MagicMock(spec_set=self.conduit.init_unit,
                                                return_value=unit)
        self.conduit.save_unit = mock.MagicMock(spec_set=self.conduit.save_unit)

        report = upload.upload(self.repo, models.RPM.TYPE, None,
                               None, self.file_path, self.conduit, None)

        self.assertTrue(report.success_flag)
        # now make sure the correct location tag exists
        saved_unit = self.conduit.save_unit.call_args[0][0]
        primary = saved_unit.metadata['repodata']['primary']
        regex = r'<location href="%s"/>' % os.path.basename(self.file_path)
        self.assertTrue(re.search(regex, primary) is not None)


class TestUploadSRPM(unittest.TestCase):
    def setUp(self):
        self.repo = Repository('repo1')
        self.conduit = UploadConduit(self.repo.id, 'yum_importer', 'user', 'me')
        self.metadata = json.load(
            open(os.path.join(os.path.dirname(__file__), '../data/crash-trace-command-1.0-4.el6.src.json')))
        self.model = SRPM.from_package_info(self.metadata)
        self.file_path = os.path.join(os.path.dirname(__file__), '../data/crash-trace-command-1.0-4.el6.src.rpm')

    def wrap_get_package_xml(self, storage_path):
        return get_package_xml(self.file_path)

    @mock.patch('pulp_rpm.plugins.importers.yum.parse.rpm.get_package_xml', autospec=True)
    @mock.patch('shutil.move', autospec=True)
    def test_upload(self, mock_copy, mock_get_xml):
        mock_get_xml.side_effect = self.wrap_get_package_xml
        unit = Unit(self.model.TYPE, self.model.unit_key, self.model.metadata, self.model.relative_path)
        self.conduit.init_unit = mock.MagicMock(spec_set=self.conduit.init_unit,
                                                return_value=unit)
        self.conduit.save_unit = mock.MagicMock(spec_set=self.conduit.save_unit)

        report = upload.upload(self.repo, models.SRPM.TYPE, self.model.unit_key,
                               self.model.metadata, self.file_path, self.conduit, {})

        self.assertTrue(report.success_flag)
        # now make sure the correct location tag exists
        saved_unit = self.conduit.save_unit.call_args[0][0]
        primary = saved_unit.metadata['repodata']['primary']
        regex = r'<location href="%s"/>' % os.path.basename(self.file_path)
        self.assertTrue(re.search(regex, primary) is not None)
        # spot check that the requires were found and put in the right places
        self.assertTrue(primary.find('zlib-devel') >= 0)
        self.assertEqual(len(saved_unit.metadata['requires']), 2)


class TestUploadGroup(unittest.TestCase):
    def setUp(self):
        self.repo = Repository('repo1')
        self.conduit = UploadConduit(self.repo.id, 'yum_importer', 'user', 'me')
        self.metadata = {'unit_metadata': {
            'mandatory_package_names': None,
            'name': 'pulp-test',
            'default': None,
            'display_order': 0,
            'description': 'test group',
            'user_visible': None,
            'translated_name': '',
            'translated_description': {},
            'optional_package_names': None,
            'default_package_names': None,
            'langonly': None,
            'conditional_package_names': []}
        }

    def test_upload(self):
        self.conduit.init_unit = mock.MagicMock(spec_set=self.conduit.init_unit)
        self.conduit.save_unit = mock.MagicMock(spec_set=self.conduit.save_unit)
        unit_key = {'id': 'group1', 'repo_id': self.repo.id}

        report = upload.upload(self.repo, models.PackageGroup.TYPE, unit_key,
                               self.metadata, '', self.conduit,
                               PluginCallConfiguration({}, {}))

        self.conduit.init_unit.assert_called_once_with(models.PackageGroup.TYPE,
                                                       unit_key, self.metadata, '')
        self.conduit.save_unit.assert_called_once_with(self.conduit.init_unit.return_value)
        self.assertTrue(isinstance(report, SyncReport))
        self.assertTrue(report.success_flag)


WALRUS_JSON = """{
    "build_time": 1331831368,
    "buildhost": "smqe-ws15",
    "vendor": null,
    "size": 2445,
    "group": "Internet/Applications",
    "relative_url_path": null,
    "filename": "walrus-5.21-1.noarch.rpm",
    "epoch": "0",
    "version": "5.21",
    "files": {
        "file": [
            "/tmp/walrus.txt"
        ],
        "dir": []
    },
    "description": "A dummy package of walrus",
    "time": 1331832461,
    "header_range": {
        "start": 872,
        "end": 2293
    },
    "arch": "noarch",
    "name": "walrus",
    "sourcerpm": "walrus-5.21-1.src.rpm",
    "checksumtype": "sha256",
    "license": "GPLv2",
    "changelog": [],
    "url": "http://tstrachota.fedorapeople.org",
    "checksum": "e837a635cc99f967a70f34b268baa52e0f412c1502e08e924ff5b09f1f9573f2",
    "summary": "A dummy package of walrus",
    "relativepath": "walrus-5.21-1.noarch.rpm",
    "release": "1"
}"""
