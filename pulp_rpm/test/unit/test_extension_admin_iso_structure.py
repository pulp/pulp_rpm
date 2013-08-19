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

from pulp.client.commands import unit
from pulp.client.commands.repo import cudl, sync_publish, upload as pulp_upload
from pulp.client.commands.schedule import (
    DeleteScheduleCommand, ListScheduleCommand, CreateScheduleCommand,
    UpdateScheduleCommand, NextRunCommand, RepoScheduleStrategy)
from pulp.client.extensions.extensions import PulpCliSection
from pulp.client.upload.manager import UploadManager
import mock

from pulp_rpm.common import ids
from pulp_rpm.extension.admin.iso import contents, create_update, repo_list, structure, upload
import rpm_support_base


class TestAddIsoSection(rpm_support_base.PulpClientTests):
    """
    Test the add_iso_section() function.
    """
    @mock.patch('pulp_rpm.extension.admin.iso.structure._get_upload_manager')
    def test_add_iso_section(self, _get_upload_manager):
        # We don't really need to test upload managers here, so let's just fake one for now
        _get_upload_manager.return_value = 'fake_upload_manager'
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

        structure.add_publish_section(self.context, parent_section)

        publish_section = parent_section.subsections['publish']
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
    @mock.patch('pulp_rpm.extension.admin.iso.structure._get_upload_manager')
    def test_add_repo_section(self, _get_upload_manager):
        # We don't really need to test upload managers here, so let's just fake one for now
        _get_upload_manager.return_value = 'fake_upload_manager'
        parent_section = self.cli.create_section('parent', 'Test parent section.')

        structure.add_repo_section(self.context, parent_section)

        repo_section = parent_section.subsections['repo']
        # Make sure the repo section was configured appropriately
        self.assertEqual(parent_section.subsections[structure.SECTION_REPO], repo_section)
        self.assertEqual(repo_section.name, structure.SECTION_REPO)
        self.assertEqual(repo_section.description, structure.DESC_REPO)

        # The sync, publish, and uploads sections should have been added as well
        sync_section = repo_section.subsections[structure.SECTION_SYNC]
        self.assertTrue(isinstance(sync_section, PulpCliSection))
        publish_section = repo_section.subsections[structure.SECTION_PUBLISH]
        self.assertTrue(isinstance(publish_section, PulpCliSection))
        uploads_section = repo_section.subsections[structure.SECTION_UPLOADS]
        self.assertTrue(isinstance(uploads_section, PulpCliSection))

        # There should be seven commands
        self.assertEqual(len(repo_section.commands), 7)

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

        # And copy...
        copy_command = repo_section.commands['copy']
        self.assertTrue(isinstance(copy_command, unit.UnitCopyCommand))
        self.assertEqual(copy_command.context, self.context)
        self.assertEqual(copy_command.type_id, ids.TYPE_ID_ISO)

        # Remove command
        remove_command = repo_section.commands['remove']
        self.assertTrue(isinstance(remove_command, unit.UnitRemoveCommand))
        self.assertEqual(remove_command.context, self.context)
        self.assertEqual(remove_command.type_id, ids.TYPE_ID_ISO)

        # isos command
        isos_command = repo_section.commands['isos']
        self.assertTrue(isinstance(isos_command, contents.ISOSearchCommand))
        self.assertEqual(isos_command.context, self.context)


class TestAddSchedulesSection(rpm_support_base.PulpClientTests):
    """
    Test the add_schedules_section() function.
    """
    def test_add_schedules_section(self):
        parent_section = self.cli.create_section('parent', 'Test parent section.')

        structure.add_schedules_section(self.context, parent_section)

        schedules_section = parent_section.subsections['schedules']
        self.assertEqual(schedules_section.name, structure.SECTION_SCHEDULES)
        self.assertEqual(schedules_section.description, structure.DESC_SCHEDULES)

        # Assert that the correct schedules commands are present
        self.assertEqual(len(schedules_section.commands), 5)

        create_command = schedules_section.commands['create']
        self.assertTrue(isinstance(create_command, CreateScheduleCommand))
        self.assertEqual(create_command.context, self.context)
        self.assertEqual(create_command.description, structure.DESC_SYNC_CREATE)

        # Inspect the strategy. We will inspect it once, and then assert that the other commands
        # have the same strategy
        strategy = create_command.strategy
        self.assertTrue(isinstance(strategy, RepoScheduleStrategy))
        self.assertEqual(strategy.type_id, ids.TYPE_ID_IMPORTER_ISO)
        self.assertEqual(strategy.api, self.context.server.repo_sync_schedules)

        delete_command = schedules_section.commands['delete']
        self.assertTrue(isinstance(delete_command, DeleteScheduleCommand))
        self.assertEqual(delete_command.context, self.context)
        self.assertEqual(delete_command.description, structure.DESC_SYNC_DELETE)
        self.assertEqual(delete_command.strategy, strategy)

        list_command = schedules_section.commands['list']
        self.assertTrue(isinstance(list_command, ListScheduleCommand))
        self.assertEqual(list_command.context, self.context)
        self.assertEqual(list_command.description, structure.DESC_SYNC_LIST)
        self.assertEqual(list_command.strategy, strategy)

        next_command = schedules_section.commands['next']
        self.assertTrue(isinstance(next_command, NextRunCommand))
        self.assertEqual(next_command.context, self.context)
        self.assertEqual(next_command.description, structure.DESC_SYNC_NEXT_RUN)
        self.assertEqual(next_command.strategy, strategy)

        update_command = schedules_section.commands['update']
        self.assertTrue(isinstance(update_command, UpdateScheduleCommand))
        self.assertEqual(update_command.context, self.context)
        self.assertEqual(update_command.description, structure.DESC_SYNC_UPDATE)
        self.assertEqual(update_command.strategy, strategy)


class TestAddSyncSection(rpm_support_base.PulpClientTests):
    """
    Test the add_sync_section() function.
    """
    @mock.patch('pulp_rpm.extension.admin.iso.structure.add_schedules_section',
                side_effect=structure.add_schedules_section, autospec=True)
    def test_add_sync_section(self, add_schedules_section):
        parent_section = self.cli.create_section('parent', 'Test parent section.')

        structure.add_sync_section(self.context, parent_section)

        sync_section = parent_section.subsections['sync']
        # Check the sync_section properties
        self.assertEqual(sync_section.name, structure.SECTION_SYNC)
        self.assertEqual(sync_section.description, structure.DESC_SYNC)

        # The run command should have been added to the sync_section
        run_command = sync_section.commands['run']
        self.assertTrue(isinstance(run_command, sync_publish.RunSyncRepositoryCommand))

        # The schedules subsection should have been added as well
        add_schedules_section.assert_called_once_with(self.context, sync_section)


class TestAddUploadsSection(rpm_support_base.PulpClientTests):
    """
    Test the add_uploads_section() function.
    """
    @mock.patch('pulp_rpm.extension.admin.iso.structure._get_upload_manager', autospec=True)
    def test_add_uploads_section(self, _get_upload_manager):
        parent_section = self.cli.create_section('parent', 'Test parent section.')

        structure.add_uploads_section(self.context, parent_section)

        uploads_section = parent_section.subsections['uploads']
        self.assertEqual(uploads_section.name, structure.SECTION_UPLOADS)
        self.assertEqual(uploads_section.description, structure.DESC_UPLOADS)

        # Check out the upload commands
        self.assertEqual(len(uploads_section.commands), 4)
        fake_upload_manager = _get_upload_manager.return_value

        upload_command = uploads_section.commands['upload']
        self.assertTrue(isinstance(upload_command, upload.UploadISOCommand))
        self.assertEqual(upload_command.context, self.context)
        self.assertEqual(upload_command.upload_manager, fake_upload_manager)

        resume_command = uploads_section.commands['resume']
        self.assertTrue(isinstance(resume_command, pulp_upload.ResumeCommand))
        self.assertEqual(resume_command.context, self.context)
        self.assertEqual(resume_command.upload_manager, fake_upload_manager)

        cancel_command = uploads_section.commands['cancel']
        self.assertTrue(isinstance(cancel_command, pulp_upload.CancelCommand))
        self.assertEqual(cancel_command.context, self.context)
        self.assertEqual(cancel_command.upload_manager, fake_upload_manager)

        list_command = uploads_section.commands['list']
        self.assertTrue(isinstance(list_command, pulp_upload.ListCommand))
        self.assertEqual(list_command.context, self.context)
        self.assertEqual(list_command.upload_manager, fake_upload_manager)


class TestGetUploadManager(rpm_support_base.PulpClientTests):
    """
    Test the _get_upload_manager() function.
    """
    @mock.patch('pulp.client.upload.manager.UploadManager.initialize', autospec=True)
    def test__get_upload_manager(self, initialize):
        self.context.config['filesystem'] = {'upload_working_dir': '/path/to/nowhere'}
        self.context.config['server'] = {'upload_chunk_size': 42}

        upload_manager = structure._get_upload_manager(self.context)

        initialize.assert_called_once_with(upload_manager)
        self.assertTrue(isinstance(upload_manager, UploadManager))
        self.assertEqual(upload_manager.upload_working_dir, '/path/to/nowhere')
        self.assertEqual(upload_manager.bindings, self.context.server)
        self.assertEqual(upload_manager.chunk_size, 42)
