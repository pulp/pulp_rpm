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

import unittest

import mock
from pulp.plugins.conduits.unit_import import ImportUnitConduit
from pulp.plugins.model import Unit, Repository
from pulp.server.db.model.criteria import UnitAssociationCriteria
import pulp.server.managers.factory as manager_factory

import model_factory
from pulp_rpm.common import models
from pulp_rpm.plugins.importers.yum import associate

manager_factory.initialize()


class TestAssociateUnit(unittest.TestCase):
    def setUp(self):
        self.repo = Repository('repo1')

    @mock.patch('shutil.copyfile')
    def test_rpm(self, mock_copyfile):
        model = model_factory.rpm_models(1)[0]
        unit = Unit(model.TYPE, model.unit_key, model.metadata, '/')

        # passing "None" ensures that the importer isn't being called
        ret = associate._associate_unit('', None, unit)

        self.assertTrue(ret is unit)
        self.assertEqual(mock_copyfile.call_count, 0)

    @mock.patch('shutil.copyfile')
    def test_yum_md_file(self, mock_copyfile):
        mock_conduit = mock.MagicMock(spec_set=ImportUnitConduit('', '', '', '', '', ''))
        model = model_factory.yum_md_file()
        unit = Unit(model.TYPE, model.unit_key, model.metadata, '/foo/bar')

        ret = associate._associate_unit(self.repo, mock_conduit, unit)

        expected_key = {'repo_id': self.repo.id, 'data_type': model.unit_key['data_type']}
        self.assertEqual(mock_conduit.init_unit.call_args[0][0], model.TYPE)
        self.assertEqual(mock_conduit.init_unit.call_args[0][1], expected_key)
        self.assertEqual(mock_conduit.init_unit.call_args[0][2], model.metadata)

        mock_conduit.save_unit.assert_called_once_with(mock_conduit.init_unit.return_value)

        mock_copyfile.assert_called_once_with(unit.storage_path,
                                              mock_conduit.init_unit.return_value.storage_path)


class TestGetRPMSToCopyByName(unittest.TestCase):
    RPM_NAMES = ('postfix', 'vim-common', 'python-mock')

    @mock.patch('pulp_rpm.plugins.importers.yum.existing.get_existing_units',
               autospec=True, return_value=tuple())
    def test_none_existing(self, mock_get_existing):
        mock_conduit = mock.MagicMock(spec_set=ImportUnitConduit('', '', '', '', '', ''))

        ret = associate.get_rpms_to_copy_by_name(self.RPM_NAMES, mock_conduit)

        self.assertTrue(isinstance(ret, set))
        self.assertEqual(ret, set(self.RPM_NAMES))
        self.assertEqual(mock_get_existing.call_count, 1)
        self.assertEqual(list(mock_get_existing.call_args[0][0]), list({'name': name} for name in self.RPM_NAMES))
        self.assertEqual(mock_get_existing.call_args[0][1], models.RPM.UNIT_KEY_NAMES)
        self.assertEqual(mock_get_existing.call_args[0][2], models.RPM.TYPE)
        self.assertEqual(mock_get_existing.call_args[0][3], mock_conduit.get_destination_units)

    def test_some_existing(self):
        postfix = model_factory.rpm_models(1)[0]
        postfix.name = 'postfix'
        vim = model_factory.rpm_models(1)[0]
        vim.name = 'vim-common'
        existing = [
            Unit(models.RPM.TYPE, postfix.unit_key, postfix.metadata, ''),
            Unit(models.RPM.TYPE, vim.unit_key, vim.metadata, ''),
        ]
        conduit = ImportUnitConduit('', '','', '', '', '')
        conduit.get_destination_units = mock.MagicMock(spec_set=conduit.get_destination_units,
                                                       return_value=existing)

        ret = associate.get_rpms_to_copy_by_name(self.RPM_NAMES, conduit)

        self.assertEqual(set(ret), set(['python-mock']))
        self.assertEqual(conduit.get_destination_units.call_count, 1)
        self.assertTrue(isinstance(conduit.get_destination_units.call_args[0][0], UnitAssociationCriteria))
        self.assertEqual(conduit.get_destination_units.call_args[0][0].type_ids, [models.RPM.TYPE])
        self.assertEqual(conduit.get_destination_units.call_args[0][0].unit_fields, models.RPM.UNIT_KEY_NAMES)
