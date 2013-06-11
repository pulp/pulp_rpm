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

from itertools import count
import unittest

import mock
from pulp.plugins.conduits.unit_import import ImportUnitConduit
from pulp.plugins.model import Unit, Repository
import pulp.server.managers.factory as manager_factory

from pulp_rpm.common import models
from pulp_rpm.plugins.importers.yum import associate

manager_factory.initialize()

rpm_counter = count()

def rpm_model_factory():
    count = rpm_counter.next()
    return models.RPM(
        'name-%d' % count,
        0,
        '2.1.%d' % count,
        '1-1',
        'x86_64',
        'sha256',
        'somehash-%d' % count,
        {}
    )

yum_md_file_counter = count()

def yum_md_file_factory():
    return models.YumMetadataFile(models.YumMetadataFile.TYPE,
                                  'repo-%d' % yum_md_file_counter.next(), {})


class TestAssociateUnit(unittest.TestCase):
    def setUp(self):
        self.repo = Repository('repo1')

    @mock.patch('shutil.copyfile')
    def test_rpm(self, mock_copyfile):
        model = rpm_model_factory()
        unit = Unit(model.TYPE, model.unit_key, model.metadata, '/')

        # passing "None" ensures that the importer isn't being called
        ret = associate._associate_unit('', None, unit)

        self.assertTrue(ret is unit)
        self.assertEqual(mock_copyfile.call_count, 0)

    @mock.patch('shutil.copyfile')
    def test_yum_md_file(self, mock_copyfile):
        mock_conduit = mock.MagicMock(spec_set=ImportUnitConduit('', '', '', '', '', ''))
        model = yum_md_file_factory()
        unit = Unit(model.TYPE, model.unit_key, model.metadata, '/foo/bar')

        ret = associate._associate_unit(self.repo, mock_conduit, unit)

        expected_key = {'repo_id': self.repo.id, 'data_type': model.unit_key['data_type']}
        self.assertEqual(mock_conduit.init_unit.call_args[0][0], model.TYPE)
        self.assertEqual(mock_conduit.init_unit.call_args[0][1], expected_key)
        self.assertEqual(mock_conduit.init_unit.call_args[0][2], model.metadata)

        mock_conduit.save_unit.assert_called_once_with(mock_conduit.init_unit.return_value)

        mock_copyfile.assert_called_once_with(unit.storage_path,
                                              mock_conduit.init_unit.return_value.storage_path)

