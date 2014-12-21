# -*- coding: utf-8 -*-

import copy
import json
import os
import unittest

import mock
from pulp.server.db.migrate.models import _import_all_the_way

from pulp_rpm.plugins.db.models import RPM, SRPM


migration = _import_all_the_way('pulp_rpm.plugins.migrations.0011_new_importer')
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data',
                        '11_migrate_new_importer')


class TestMigrateNewImporter(unittest.TestCase):
    def setUp(self):
        self.rpm_unit = copy.deepcopy(RPM_UNIT)
        self.srpm_unit = copy.deepcopy(SRPM_UNIT)

    @mock.patch.object(migration, '_migrate_collection')
    def test_types(self, mock_add):
        migration.migrate()
        self.assertEqual(mock_add.call_count, 2)
        mock_add.assert_any_call(RPM.TYPE)
        mock_add.assert_any_call(SRPM.TYPE)

    @mock.patch('pulp.plugins.types.database.type_units_collection')
    def test_adds_size(self, mock_collection):
        mock_collection.return_value.find.return_value = [self.rpm_unit]
        self.assertFalse('size' in self.rpm_unit)

        migration._migrate_collection(RPM.TYPE)
        result = mock_collection.return_value.save.call_args[0][0]

        self.assertTrue('size' in result)
        self.assertEqual(result['size'], 88136)

    @mock.patch('pulp.plugins.types.database.type_units_collection')
    def test_adds_sourcerpm(self, mock_collection):
        mock_collection.return_value.find.return_value = [self.rpm_unit]
        self.assertFalse('sourcerpm' in self.rpm_unit)

        migration._migrate_collection(RPM.TYPE)
        result = mock_collection.return_value.save.call_args[0][0]

        self.assertTrue('sourcerpm' in result)
        self.assertEqual(result['sourcerpm'], 'pulp-2.1.1-1.el6.src.rpm')

    @mock.patch('pulp.plugins.types.database.type_units_collection')
    def test_adds_summary(self, mock_collection):
        mock_collection.return_value.find.return_value = [self.rpm_unit]
        self.assertFalse('summary' in self.rpm_unit)

        migration._migrate_collection(RPM.TYPE)
        result = mock_collection.return_value.save.call_args[0][0]

        self.assertTrue('summary' in result)
        self.assertEqual(result['summary'], 'The Pulp agent')

    @mock.patch('pulp.plugins.types.database.type_units_collection')
    def test_preserve_xml(self, mock_collection):
        mock_collection.return_value.find.return_value = [self.rpm_unit]

        migration._migrate_collection(RPM.TYPE)
        result = mock_collection.return_value.save.call_args[0][0]

        # ensure no changes to actual XML
        primary_xml = result['repodata']['primary']
        self.assertEqual(primary_xml, RPM_UNIT['repodata']['primary'])

    @mock.patch('pulp.plugins.types.database.type_units_collection')
    def test_reformats_provides(self, mock_collection):
        mock_collection.return_value.find.return_value = [self.rpm_unit]

        migration._migrate_collection(RPM.TYPE)
        result = mock_collection.return_value.save.call_args[0][0]

        provides = result['provides']
        found_pulp_agent = False
        self.assertTrue(len(provides) > 1)
        for entry in provides:
            self.assertTrue(isinstance(entry, dict))
            for name in ('name', 'flags', 'epoch', 'version', 'release'):
                self.assertTrue(name in entry)
            if entry['name'] == 'pulp-agent':
                found_pulp_agent = True
                self.assertEqual(entry['flags'], 'EQ')
                self.assertEqual(entry['epoch'], '0')
                self.assertEqual(entry['version'], '2.1.1')
                self.assertEqual(entry['release'], '1.el6')
        self.assertTrue(found_pulp_agent)

    @mock.patch('pulp.plugins.types.database.type_units_collection')
    def test_reformats_requires(self, mock_collection):
        mock_collection.return_value.find.return_value = [self.rpm_unit]

        migration._migrate_collection(RPM.TYPE)
        result = mock_collection.return_value.save.call_args[0][0]

        requires = result['requires']
        self.assertTrue(len(requires) > 1)
        for entry in requires:
            self.assertTrue(isinstance(entry, dict))
            for name in ('name', 'flags', 'epoch', 'version', 'release'):
                self.assertTrue(name in entry)

    @mock.patch('pulp.plugins.types.database.type_units_collection')
    def test_srpm_doesnt_have_sourcerpm_or_summary(self, mock_collection):
        self.assertTrue('sourcerpm' not in self.srpm_unit)
        self.assertTrue('summary' not in self.srpm_unit)
        mock_collection.return_value.find.return_value = [self.srpm_unit]

        migration._migrate_collection(SRPM.TYPE)
        result = mock_collection.return_value.save.call_args[0][0]
        self.assertTrue('sourcerpm' not in result)
        self.assertTrue('summary' not in result)

with open(os.path.join(DATA_DIR, 'rpm_unit.json'), 'r') as fp:
    RPM_UNIT = json.load(fp)

with open(os.path.join(DATA_DIR, 'srpm_unit.json'), 'r') as fp:
    SRPM_UNIT = json.load(fp)
