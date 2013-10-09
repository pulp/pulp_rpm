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

from gettext import gettext as _
import os

from pulp.client.commands import unit
from pulp.client.commands.options import OPTION_REPO_ID
from pulp.client.commands.repo import cudl, sync_publish, upload as pulp_upload
from pulp.client.commands.schedule import (
    DeleteScheduleCommand, ListScheduleCommand, CreateScheduleCommand,
    UpdateScheduleCommand, NextRunCommand, RepoScheduleStrategy)
from pulp.client.upload import manager as upload_lib

from pulp_rpm.common import ids
from pulp_rpm.extension.admin.iso import contents, create_update, repo_list, status, upload


SECTION_PUBLISH = 'publish'
DESC_PUBLISH = 'run publish tasks'

SECTION_REPO = 'repo'
DESC_REPO = _('repository lifecycle commands')

SECTION_ROOT = 'iso'
DESC_ROOT = _('manage ISO-related content and features')

SECTION_SCHEDULES = 'schedules'
DESC_SCHEDULES = _('manage repository sync schedules')

SECTION_SYNC = 'sync'
DESC_SYNC = _('run or schedule sync tasks')

DESC_SYNC_LIST = _('list scheduled sync operations')
DESC_SYNC_CREATE = _('add new scheduled sync operations')
DESC_SYNC_DELETE = _('delete sync schedules')
DESC_SYNC_UPDATE = _('update existing schedules')
DESC_SYNC_NEXT_RUN = _('display the next scheduled sync run for a repository')

SECTION_UPLOADS = 'uploads'
DESC_UPLOADS = _('upload ISOs into a repository')

ISO_UPLOAD_SUBDIR = 'iso'

def add_iso_section(context):
    """
    Adds the ISO root section to the cli, and all of its children sections.

    :param context: ClientContext containing the CLI instance being configured
    :type  context: pulp.client.extensions.core.ClientContext
    """
    root_section = context.cli.create_section(SECTION_ROOT, DESC_ROOT)

    add_repo_section(context, root_section)


def add_publish_section(context, repo_section):
    """
    Add the publish subsection and all of its children to the repo section.

    :param context: ClientContext containing the CLI instance being configured
    :type  context: pulp.client.extensions.core.ClientContext
    :param repo_section: The parent repo section that we wish to add the publish subsection
                         to.
    :type  repo_section: pulp.client.extensions.extensions.PulpCliSection
    """
    publish_section = repo_section.create_subsection(SECTION_PUBLISH, DESC_PUBLISH)

    renderer = status.ISOStatusRenderer(context)

    publish_section.add_command(
        sync_publish.RunPublishRepositoryCommand(
            context, renderer, distributor_id=ids.TYPE_ID_DISTRIBUTOR_ISO))
    publish_section.add_command(
        sync_publish.PublishStatusCommand(context, renderer))


def add_repo_section(context, parent_section):
    """
    Add the repo section and all of its children to the parent section.

    :param context: ClientContext containing the CLI instance being configured
    :type  context: pulp.client.extensions.core.ClientContext
    :param parent_section: The parent CLI section that we wish to add the repo subsection to.
    :type  parent_section: pulp.client.extensions.extensions.PulpCliSection
    """
    repo_section = parent_section.create_subsection(SECTION_REPO, DESC_REPO)

    add_publish_section(context, repo_section)
    add_sync_section(context, repo_section)
    add_uploads_section(context, repo_section)

    repo_section.add_command(create_update.ISORepoCreateCommand(context))
    repo_section.add_command(create_update.ISORepoUpdateCommand(context))
    repo_section.add_command(cudl.DeleteRepositoryCommand(context))
    repo_section.add_command(repo_list.ISORepoListCommand(context))
    repo_section.add_command(unit.UnitCopyCommand(context, type_id=ids.TYPE_ID_ISO))
    repo_section.add_command(unit.UnitRemoveCommand(context, type_id=ids.TYPE_ID_ISO))
    repo_section.add_command(contents.ISOSearchCommand(context, name='isos'))


def add_schedules_section(context, parent_section):
    """
    Add a sync schedule section to the parent_section.

    :param context: ClientContext containing the CLI instance being configured
    :type  context: pulp.client.extensions.core.ClientContext
    :param parent_section: The parent CLI section that we wish to add the schedules
                           subsection to.
    :type  parent_section: pulp.client.extensions.extensions.PulpCliSection
    """
    schedules_section = parent_section.create_subsection(SECTION_SCHEDULES, DESC_SCHEDULES)

    strategy = RepoScheduleStrategy(context.server.repo_sync_schedules, ids.TYPE_ID_IMPORTER_ISO)

    list_command = ListScheduleCommand(context, strategy, description=DESC_SYNC_LIST)
    create_command = CreateScheduleCommand(context, strategy, description=DESC_SYNC_CREATE)
    delete_command = DeleteScheduleCommand(context, strategy, description=DESC_SYNC_DELETE)
    update_command = UpdateScheduleCommand(context, strategy, description=DESC_SYNC_UPDATE)
    next_command = NextRunCommand(context, strategy, description=DESC_SYNC_NEXT_RUN)

    commands = (list_command, create_command, delete_command, update_command, next_command)
    for command in commands:
        command.add_option(OPTION_REPO_ID)
        schedules_section.add_command(command)


def add_sync_section(context, repo_section):
    """
    Add the sync subsection and all of its children to the repo section.

    :param context: ClientContext containing the CLI instance being configured
    :type  context: pulp.client.extensions.core.ClientContext
    :param repo_section: The parent repo section that we wish to add the sync subsection to.
    :type  repo_section: pulp.client.extensions.extensions.PulpCliSection
    """
    sync_section = repo_section.create_subsection(SECTION_SYNC, DESC_SYNC)

    add_schedules_section(context, sync_section)

    renderer = status.ISOStatusRenderer(context)
    sync_section.add_command(sync_publish.RunSyncRepositoryCommand(context, renderer))


def add_uploads_section(context, repo_section):
    """
    Add the uploads subsection and all of its children to the repo section.

    :param context:      ClientContext containing the CLI instance being configured
    :type  context:      pulp.client.extensions.core.ClientContext
    :param repo_section: The parent repo section that we wish to add the uploads subsection to.
    :type  repo_section: pulp.client.extensions.extensions.PulpCliSection
    """
    uploads_section = repo_section.create_subsection(SECTION_UPLOADS, DESC_UPLOADS)

    upload_manager = _get_upload_manager(context)

    uploads_section.add_command(upload.UploadISOCommand(context, upload_manager))
    uploads_section.add_command(pulp_upload.ResumeCommand(context, upload_manager))
    uploads_section.add_command(pulp_upload.CancelCommand(context, upload_manager))
    uploads_section.add_command(pulp_upload.ListCommand(context, upload_manager))


def _get_upload_manager(context):
    """
    Return a new UploadManager.

    :param context: ClientContext containing the CLI instance being configured
    :type  context: pulp.client.extensions.core.ClientContext
    :return:        An intialized UploadManager.
    :rtype:         pulp.client.upload.manager.UploadManager
    """
    # Each upload_manager needs to be associated with a unique upload working directory. 
    # Create a subdirectory for iso uploads under the main upload_working_dir 
    # to avoid interference with other types of uploads eg. rpm uploads.
    upload_working_dir = os.path.join(context.config['filesystem']['upload_working_dir'], ISO_UPLOAD_SUBDIR)
    upload_working_dir = os.path.expanduser(upload_working_dir)
    chunk_size = int(context.config['server']['upload_chunk_size'])
    upload_manager = upload_lib.UploadManager(upload_working_dir, context.server, chunk_size)
    upload_manager.initialize()
    return upload_manager
