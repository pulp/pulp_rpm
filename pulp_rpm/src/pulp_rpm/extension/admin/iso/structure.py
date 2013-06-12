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
from pulp.client.commands.repo import cudl, sync_publish, upload as pulp_upload
from pulp.client.upload import manager as upload_lib

from pulp_rpm.common import ids
from pulp_rpm.extension.admin.iso import (contents, create_update, repo_list, status,
                                          sync_schedules, upload)


SECTION_PUBLISH = 'publish'
DESC_PUBLISH = 'run or view the status of publish tasks'

SECTION_REPO = 'repo'
DESC_REPO = _('repository lifecycle commands')

SECTION_ROOT = 'iso'
DESC_ROOT = _('manage ISO-related content and features')

SECTION_SCHEDULES = 'schedules'
DESC_SCHEDULES = _('manage repository sync schedules')

SECTION_SYNC = 'sync'
DESC_SYNC = _('run, schedule, or view the status of sync tasks')

SECTION_UPLOADS = 'uploads'
DESC_UPLOADS = _('upload ISOs into a repository')


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
    repo_section.add_command(contents.ISOSearchCommand(context, name='content'))


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

    schedules_section.add_command(sync_schedules.ISOCreateScheduleCommand(context))
    schedules_section.add_command(sync_schedules.ISODeleteScheduleCommand(context))
    schedules_section.add_command(sync_schedules.ISOListScheduleCommand(context))
    schedules_section.add_command(sync_schedules.ISONextRunCommand(context))
    schedules_section.add_command(sync_schedules.ISOUpdateScheduleCommand(context))


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
    upload_working_dir = context.config['filesystem']['upload_working_dir']
    upload_working_dir = os.path.expanduser(upload_working_dir)
    chunk_size = int(context.config['server']['upload_chunk_size'])
    upload_manager = upload_lib.UploadManager(upload_working_dir, context.server, chunk_size)
    upload_manager.initialize()
    return upload_manager
