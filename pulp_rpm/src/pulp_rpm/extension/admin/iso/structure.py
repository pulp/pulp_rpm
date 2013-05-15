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

from pulp.client.commands.repo import sync_publish

from pulp_rpm.common import ids
from pulp_rpm.extension.admin.iso import status


SECTION_PUBLISH = 'publish'
DESC_PUBLISH = 'run or view the status of publish tasks'

SECTION_REPO = 'repo'
DESC_REPO = _('repository lifecycle commands')

SECTION_ROOT = 'iso'
DESC_ROOT = _('manage ISO-related content and features')

SECTION_SYNC = 'sync'
DESC_SYNC = _('run, schedule, or view the status of sync tasks')


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
    :param repo_section: The parent repo section that we wish to add the publish subsection to.
    :type  repo_section: pulp.client.extensions.extensions.PulpCliSection
    """
    publish_section = repo_section.create_subsection(SECTION_PUBLISH, DESC_PUBLISH)

    renderer = status.ISOStatusRenderer(context)

    publish_section.add_command(
        sync_publish.RunPublishRepositoryCommand(
            context, renderer, distributor_id=ids.TYPE_ID_DISTRIBUTOR_ISO))

    return publish_section


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

    return repo_section


def add_sync_section(context, repo_section):
    """
    Add the sync subsection and all of its children to the repo section.
    
    :param context: ClientContext containing the CLI instance being configured
    :type  context: pulp.client.extensions.core.ClientContext
    :param repo_section: The parent repo section that we wish to add the sync subsection to.
    :type  repo_section: pulp.client.extensions.extensions.PulpCliSection
    """
    sync_section = repo_section.create_subsection(SECTION_SYNC, DESC_SYNC)

    renderer = status.ISOStatusRenderer(context)

    sync_section.add_command(sync_publish.RunSyncRepositoryCommand(context, renderer))

    return sync_section