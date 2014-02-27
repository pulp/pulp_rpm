# -*- coding: utf-8 -*-
# Copyright (c) 2012 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

from pulp.plugins.types import database as types_db
from pulp.plugins.types.model import TypeDefinition
from pulp.server.db.model.repository import Repo, RepoContentUnit, RepoImporter
from pulp.server.db.migrate.models import _import_all_the_way
from pulp.server.managers import factory

from pulp_rpm.common import ids
from pulp_rpm.devel import rpm_support_base


# Trimmed down versions of the type defs
TYPE_DEF_GROUP = TypeDefinition('package_group', '', '', ['id', 'repo_id'], [], [])
TYPE_DEF_CATEGORY = TypeDefinition('package_category', '', '', ['id', 'repo_id'], [], [])


class Migration0004Tests(rpm_support_base.PulpRPMTests):

    def setUp(self):
        super(Migration0004Tests, self).setUp()

        # Special way to import modules that start with a number
        self.migration = _import_all_the_way('pulp_rpm.plugins.migrations.0004_pkg_group_category_repoid')

        factory.initialize()
        types_db.update_database([TYPE_DEF_GROUP, TYPE_DEF_CATEGORY])

        # Create the repositories necessary for the tests
        self.source_repo_id = 'source-repo' # where units were copied from with the bad code
        self.dest_repo_id = 'dest-repo' # where bad units were copied to

        source_repo = Repo(self.source_repo_id, '')
        Repo.get_collection().insert(source_repo, safe=True)

        dest_repo = Repo(self.dest_repo_id, '')
        Repo.get_collection().insert(dest_repo, safe=True)

        source_importer = RepoImporter(self.source_repo_id, 'yum_importer', 'yum_importer', {})
        RepoImporter.get_collection().insert(source_importer, safe=True)

        dest_importer = RepoImporter(self.dest_repo_id, 'yum_importer', 'yum_importer', {})
        RepoImporter.get_collection().insert(dest_importer, safe=True)

    def tearDown(self):
        super(Migration0004Tests, self).tearDown()

        # Delete any sample data added for the test
        types_db.clean()

        RepoContentUnit.get_collection().remove()
        RepoImporter.get_collection().remove()
        Repo.get_collection().remove()

    def test_migrate_duplicates(self):
        """
        This tests the correct behavior when we try to change the repo_id on an object, and end up causing
        a duplicate error due to our uniqueness constraint.
        """
        # Let's put two units here with the same IDs with two different repo_ids, and the run the
        # migration.
        source_repo_group_id = add_unit('group', self.source_repo_id, ids.TYPE_ID_PKG_GROUP)
        dest_repo_group_id = add_unit('group', self.dest_repo_id, ids.TYPE_ID_PKG_GROUP)

        associate_unit(source_repo_group_id, self.dest_repo_id, ids.TYPE_ID_PKG_GROUP)
        associate_unit(dest_repo_group_id, self.dest_repo_id, ids.TYPE_ID_PKG_GROUP)

        # Migrate should not cause a DuplicateKeyError
        self.migration.migrate()

        # Verify that both groups remain.
        group_collection = types_db.type_units_collection(ids.TYPE_ID_PKG_GROUP)
        all_groups = list(group_collection.find())
        self.assertEqual(len(all_groups), 2)
        self.assertEqual(group_collection.find({'id': 'group', 'repo_id': self.dest_repo_id}).count(), 1)
        self.assertEqual(group_collection.find({'id': 'group', 'repo_id': self.source_repo_id}).count(), 1)

        # Let's make sure that the dest group is associated, but not the source one
        query_manager = factory.repo_unit_association_query_manager()
        dest_units = query_manager.get_units(self.dest_repo_id)
        self.assertEqual(len(dest_units), 1)
        dest_unit = dest_units[0]
        self.assertEqual(dest_unit['unit_type_id'], ids.TYPE_ID_PKG_GROUP)
        self.assertEqual(dest_unit['unit_id'], dest_repo_group_id)
        self.assertEqual(query_manager.get_units(self.source_repo_id), [])

        # Verify the repo counts
        self.assertEqual(Repo.get_collection().find({'id': 'source-repo'})[0]['content_unit_counts'], {})
        self.assertEqual(Repo.get_collection().find({'id': 'dest-repo'})[0]['content_unit_counts'],
                        {'package_group': 1})

    def test_migrate_duplicates_doesnt_delete_from_source_repo(self):
        """
        This tests the correct behavior when we try to change the repo_id on an object, and end up causing
        a duplicate error due to our uniqueness constraint. It also makes sure the units are not deleted from
        the source repository if they are in the source repository.
        """
        # Let's put two units here with the same IDs with two different repo_ids, and the run the
        # migration.
        source_repo_group_id = add_unit('group', self.source_repo_id, ids.TYPE_ID_PKG_GROUP)
        dest_repo_group_id = add_unit('group', self.dest_repo_id, ids.TYPE_ID_PKG_GROUP)

        # Associate the source_repo_group_id with both source and destination repos
        associate_unit(source_repo_group_id, self.source_repo_id, ids.TYPE_ID_PKG_GROUP)
        associate_unit(source_repo_group_id, self.dest_repo_id, ids.TYPE_ID_PKG_GROUP)
        associate_unit(dest_repo_group_id, self.dest_repo_id, ids.TYPE_ID_PKG_GROUP)

        # Migrate should not cause a DuplicateKeyError
        self.migration.migrate()

        # Verify that both groups remain, because the migration should not have removed either
        group_collection = types_db.type_units_collection(ids.TYPE_ID_PKG_GROUP)
        all_groups = list(group_collection.find())
        self.assertEqual(len(all_groups), 2)
        self.assertEqual(group_collection.find({'id': 'group', 'repo_id': self.dest_repo_id}).count(), 1)
        self.assertEqual(group_collection.find({'id': 'group', 'repo_id': self.source_repo_id}).count(), 1)

        # Let's make sure that there are two associations, and that they are correct.
        query_manager = factory.repo_unit_association_query_manager()
        dest_units = query_manager.get_units(self.dest_repo_id)
        self.assertEqual(len(dest_units), 1)
        dest_unit = dest_units[0]
        self.assertEqual(dest_unit['unit_type_id'], ids.TYPE_ID_PKG_GROUP)
        self.assertEqual(dest_unit['unit_id'], dest_repo_group_id)
        source_units = query_manager.get_units(self.source_repo_id)
        self.assertEqual(len(source_units), 1)
        source_unit = source_units[0]
        self.assertEqual(source_unit['unit_type_id'], ids.TYPE_ID_PKG_GROUP)
        self.assertEqual(source_unit['unit_id'], source_repo_group_id)

        # Verify the repo counts
        self.assertEqual(Repo.get_collection().find({'id': 'source-repo'})[0]['content_unit_counts'],
                         {'package_group': 1})
        self.assertEqual(Repo.get_collection().find({'id': 'dest-repo'})[0]['content_unit_counts'],
                        {'package_group': 1})

    def test_migrate_groups(self):
        # Setup
        orig_group_id = add_unit('g1', self.source_repo_id, ids.TYPE_ID_PKG_GROUP)

        associate_unit(orig_group_id, self.source_repo_id, ids.TYPE_ID_PKG_GROUP)
        associate_unit(orig_group_id, self.dest_repo_id, ids.TYPE_ID_PKG_GROUP)

        # Test
        self.migration.migrate()

        # Verify

        # Verify a new group was created with the correct metadata
        group_coll = types_db.type_units_collection(ids.TYPE_ID_PKG_GROUP)
        all_groups = group_coll.find({}).sort('repo_id', 1)
        self.assertEqual(2, all_groups.count())

        dest_group = all_groups[0] # ordered by ID, this will be first
        self.assertEqual(dest_group['id'], 'g1')
        self.assertEqual(dest_group['repo_id'], self.dest_repo_id)

        source_group = all_groups[1]
        self.assertEqual(source_group['id'], 'g1')
        self.assertEqual(source_group['repo_id'], self.source_repo_id)

        # Verify the associations
        query_manager = factory.repo_unit_association_query_manager()

        source_units = query_manager.get_units(self.source_repo_id)
        self.assertEqual(1, len(source_units))
        self.assertEqual(source_units[0]['unit_type_id'], ids.TYPE_ID_PKG_GROUP)
        self.assertEqual(source_units[0]['unit_id'], source_group['_id'])

        dest_units = query_manager.get_units(self.dest_repo_id)
        self.assertEqual(1, len(dest_units))
        self.assertEqual(dest_units[0]['unit_type_id'], ids.TYPE_ID_PKG_GROUP)
        self.assertEqual(dest_units[0]['unit_id'], dest_group['_id'])

    def test_migrate_category(self):
        # Setup
        orig_cat_id = add_unit('c1', self.source_repo_id, ids.TYPE_ID_PKG_CATEGORY)

        associate_unit(orig_cat_id, self.source_repo_id, ids.TYPE_ID_PKG_CATEGORY)
        associate_unit(orig_cat_id, self.dest_repo_id, ids.TYPE_ID_PKG_CATEGORY)

        # Test
        self.migration.migrate()

        group_coll = types_db.type_units_collection(ids.TYPE_ID_PKG_CATEGORY)
        all_cats = group_coll.find({}).sort('repo_id', 1)
        self.assertEqual(2, all_cats.count())

        dest_cat = all_cats[0] # ordered by ID, this will be first
        self.assertEqual(dest_cat['id'], 'c1')
        self.assertEqual(dest_cat['repo_id'], self.dest_repo_id)

        source_cat = all_cats[1]
        self.assertEqual(source_cat['id'], 'c1')
        self.assertEqual(source_cat['repo_id'], self.source_repo_id)

        # Verify the associations
        query_manager = factory.repo_unit_association_query_manager()

        source_units = query_manager.get_units(self.source_repo_id)
        self.assertEqual(1, len(source_units))
        self.assertEqual(source_units[0]['unit_type_id'], ids.TYPE_ID_PKG_CATEGORY)
        self.assertEqual(source_units[0]['unit_id'], source_cat['_id'])

        dest_units = query_manager.get_units(self.dest_repo_id)
        self.assertEqual(1, len(dest_units))
        self.assertEqual(dest_units[0]['unit_type_id'], ids.TYPE_ID_PKG_CATEGORY)
        self.assertEqual(dest_units[0]['unit_id'], dest_cat['_id'])


def add_unit(id, repo_id, type_id):
    metadata = {'id' : id, 'repo_id' : repo_id,}

    unit_id = factory.content_manager().add_content_unit(
        type_id, None, metadata)

    return unit_id

def associate_unit(mongo_id, to_repo_id, type_id):
    manager = factory.repo_unit_association_manager()
    manager.associate_unit_by_id(to_repo_id, type_id, mongo_id, 'importer',
                                 'yum_importer', update_unit_count=True)

def generate_unit(unit_id, repo_id):
    # generate a package group or category unit
    return {'id' : unit_id,
            'repo_id' : repo_id,}
