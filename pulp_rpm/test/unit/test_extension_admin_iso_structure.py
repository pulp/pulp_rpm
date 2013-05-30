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

from pulp.client.commands.repo import cudl, sync_publish

from pulp_rpm.extension.admin.iso import create_update, repo_list, structure
import rpm_support_base


class TestAddIsoSection(rpm_support_base.PulpClientTests):
    """
    Test the add_iso_section() function.
    """
    def test_add_iso_section(self):
        structure.add_iso_section(self.context)

        # A root section should have been added for ISOs
        root_section = self.cli.find_section(structure.SECTION_ROOT)
        self.assertTrue(root_section is not None)
        self.assertEqual(root_section.name, structure.SECTION_ROOT)
        self.assertEqual(root_section.description, structure.DESC_ROOT)

        # There should now be a repo section added
        repo_section = root_section.subsections[structure.SECTION_REPO]
        self.assertTrue(repo_section is not None)
        self.assertEqual(repo_section.name, structure.SECTION_REPO)


class TestAddPublishSection(rpm_support_base.PulpClientTests):
    """
    Test the add_publish_section() function.
    """
    def test_add_publish_section(self):
        parent_section = self.cli.create_section('parent', 'Test parent section.')

        publish_section = structure.add_publish_section(self.context, parent_section)

        # Check the sync_section properties
        self.assertEqual(publish_section.name, structure.SECTION_PUBLISH)
        self.assertEqual(publish_section.description, structure.DESC_PUBLISH)

        # The run command should have been added to the sync_section
        run_command = publish_section.commands['run']
        self.assertTrue(isinstance(run_command, sync_publish.RunPublishRepositoryCommand))


class TestAddRepoSection(rpm_support_base.PulpClientTests):
    """
    Test the add_repo_section() function.
    """
    def test_add_repo_section(self):
        parent_section = self.cli.create_section('parent', 'Test parent section.')

        repo_section = structure.add_repo_section(self.context, parent_section)

        # Make sure the repo section was configured appropriately
        self.assertEqual(parent_section.subsections[structure.SECTION_REPO], repo_section)
        self.assertEqual(repo_section.name, structure.SECTION_REPO)
        self.assertEqual(repo_section.description, structure.DESC_REPO)

        # The sync and publish sections should have been added as well
        sync_section = repo_section.subsections[structure.SECTION_SYNC]
        self.assertTrue(sync_section is not None)
        publish_section = repo_section.subsections[structure.SECTION_PUBLISH]
        self.assertTrue(publish_section is not None)

        # There should be two commands, create and update
        self.assertEqual(len(repo_section.commands), 4)

        # The create command should have been added
        mixin = repo_section.commands['create']
        self.assertTrue(isinstance(mixin, create_update.ISORepoCreateCommand))
        self.assertEqual(mixin.context, self.context)

        # The update command should also have been added
        update_command = repo_section.commands['update']
        self.assertTrue(isinstance(update_command, create_update.ISORepoUpdateCommand))
        self.assertEqual(update_command.context, self.context)

        # And a delete command!
        delete_command = repo_section.commands['delete']
        self.assertTrue(isinstance(delete_command, cudl.DeleteRepositoryCommand))
        self.assertEqual(delete_command.context, self.context)

        # ...and a list command...
        list_command = repo_section.commands['list']
        self.assertTrue(isinstance(list_command, repo_list.ISORepoListCommand))
        self.assertEqual(list_command.context, self.context)


class TestAddSyncSection(rpm_support_base.PulpClientTests):
    """
    Test the add_sync_section() function.
    """
    def test_add_sync_section(self):
        parent_section = self.cli.create_section('parent', 'Test parent section.')

        sync_section = structure.add_sync_section(self.context, parent_section)

        # Check the sync_section properties
        self.assertEqual(sync_section.name, structure.SECTION_SYNC)
        self.assertEqual(sync_section.description, structure.DESC_SYNC)

        # The run command should have been added to the sync_section
        run_command = sync_section.commands['run']
        self.assertTrue(isinstance(run_command, sync_publish.RunSyncRepositoryCommand))