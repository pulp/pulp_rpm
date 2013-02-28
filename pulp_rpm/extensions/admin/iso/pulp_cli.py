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

from pulp.client.extensions.decorator import priority


@priority()
def initialize(context):
    """
    :param context: The client context that we can use to advertise our abilities
    :type  context: pulp.client.extensions.core.ClientContext
    """
    iso_section = context.cli.create_section('iso', 'manage ISO related content and features')
    _create_repo_subsection(iso_section)


def _create_repo_create_command(repo_section):
    """
    Add the create command to the iso repo subsection.

    :param repo_section: The repo section that we want to add the create command to
    :type  repo_section: pulp.client.extensions.extensions.PulpCliSection
    """
    create_command = repo_section.create_command('create', 'create an ISO repository', _repo_create)


def _create_repo_subsection(iso_section):
    """
    Add the repo subsection to the iso_section.

    :param iso_section: The section that we want to add the repo subsection to
    :type  iso_section: pulp.client.extensions.extensions.PulpCliSection
    """
    repo_section = iso_section.create_subsection('repo', 'repository lifecycle commands')
    _create_repo_create_command(repo_section)


def _repo_create(**kwargs):
    """
    Create an ISO repository.
    """
    pass