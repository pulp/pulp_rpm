import os

import mock

from pulp.client.commands.repo.upload import UploadCommand

from pulp_rpm.extensions.admin.upload import comps
from pulp_rpm.common.ids import TYPE_ID_PKG_GROUP
from pulp_rpm.devel.client_base import PulpClientTests


DATA_DIR = os.path.abspath(os.path.dirname(__file__)) + '/../../../../../../plugins/test'
XML_DIR = DATA_DIR + '/data/simple_repo_comps'
XML_FILENAME = 'Fedora-19-comps.xml'


class Create_CompsCommandTests(PulpClientTests):
    def setUp(self):
        super(Create_CompsCommandTests, self).setUp()
        self.upload_manager = mock.MagicMock()
        self.command = comps._CreateCompsCommand(self.context, self.upload_manager,
                                                 TYPE_ID_PKG_GROUP, comps.SUFFIX_XML,
                                                 comps.NAME_XML, comps.DESC_XML)

    def test_structure(self):
        self.assertTrue(isinstance(self.command, UploadCommand))
        self.assertEqual(self.command.name, comps.NAME_XML)
        self.assertEqual(self.command.description, comps.DESC_XML)
        self.assertEqual(self.command.suffix, comps.SUFFIX_XML)
        self.assertEqual(self.command.type_id, TYPE_ID_PKG_GROUP,)

    def test_determine_type_id(self):
        type_id = self.command.determine_type_id(None)
        self.assertEqual(type_id, TYPE_ID_PKG_GROUP,)

    def test_matching_files_in_dir(self):
        comps = self.command.matching_files_in_dir(XML_DIR)
        self.assertEqual(1, len(comps))
        self.assertEqual(os.path.basename(comps[0]), XML_FILENAME)

    def test_generate_unit_key(self):
        unit_key = self.command.generate_unit_key(None)

        self.assertEqual(unit_key, {})


class CreatecompsCommandTests(PulpClientTests):
    def setUp(self):
        super(CreatecompsCommandTests, self).setUp()
        self.upload_manager = mock.MagicMock()
        self.command = comps.CreateCompsCommand(self.context, self.upload_manager)

    def test_structure(self):
        self.assertTrue(isinstance(self.command, comps._CreateCompsCommand))
        self.assertEqual(self.command.name, comps.NAME_XML)
        self.assertEqual(self.command.description, comps.DESC_XML)
        self.assertEqual(self.command.suffix, comps.SUFFIX_XML)
        self.assertEqual(self.command.type_id, TYPE_ID_PKG_GROUP)
