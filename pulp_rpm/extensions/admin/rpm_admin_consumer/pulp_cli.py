# -*- coding: utf-8 -*-
#
# Copyright © 2012 Red Hat, Inc.
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

from pulp.client.commands.consumer.manage import (
    ConsumerUnregisterCommand, ConsumerUpdateCommand)
from pulp.client.commands.consumer.query import (
    ConsumerListCommand, ConsumerSearchCommand, ConsumerHistoryCommand)

from pulp_rpm.extension.admin import structure

import consumer_group_cudl
import consumer_group_members
from bind import YumConsumerBindCommand, YumConsumerUnbindCommand
from consumer_group_bind import ConsumerGroupBindCommand, ConsumerGroupUnbindCommand
from consumer_group_package import ConsumerGroupPackageSection
from errata import YumConsumerErrataSection
from package import YumConsumerPackageSection
from package_group import YumConsumerPackageGroupSection

# -- framework hook -----------------------------------------------------------

def initialize(context):
    root_section = structure.ensure_root(context.cli)
    consumer_description = _('register, bind, and interact with rpm consumers')
    consumer_section = root_section.create_subsection('consumer', consumer_description)

    # Basic consumer commands
    consumer_section.add_command(ConsumerListCommand(context))
    consumer_section.add_command(ConsumerUpdateCommand(context))
    consumer_section.add_command(ConsumerUnregisterCommand(context))
    consumer_section.add_command(ConsumerSearchCommand(context))
    consumer_section.add_command(ConsumerHistoryCommand(context))

    consumer_section.add_command(YumConsumerBindCommand(context))
    consumer_section.add_command(YumConsumerUnbindCommand(context))

    # New subsections
    consumer_section.add_subsection(YumConsumerPackageSection(context))
    consumer_section.add_subsection(YumConsumerPackageGroupSection(context))
    consumer_section.add_subsection(YumConsumerErrataSection(context))

    # Consumer groups
    consumer_group_description = _('consumer group commands')
    consumer_group_section = consumer_section.create_subsection('group', consumer_group_description)

    consumer_group_section.add_command(consumer_group_cudl.CreateConsumerGroupCommand(context))
    consumer_group_section.add_command(consumer_group_cudl.UpdateConsumerGroupCommand(context))
    consumer_group_section.add_command(consumer_group_cudl.DeleteConsumerGroupCommand(context))
    consumer_group_section.add_command(consumer_group_cudl.ListConsumerGroupsCommand(context))
    consumer_group_section.add_command(consumer_group_cudl.SearchConsumerGroupsCommand(context))

    m = _('binds each consumer in a consumer group to a repository')
    consumer_group_section.add_command(
        ConsumerGroupBindCommand(context, 'bind', m))

    m = _('unbinds each consumer in a consumer group from a repository')
    consumer_group_section.add_command(
        ConsumerGroupUnbindCommand(context, 'unbind', m))

    # Consumer group membership
    members_description = _('manage members of repository groups')
    members_section = consumer_group_section.create_subsection('members', members_description)

    members_section.add_command(consumer_group_members.ListConsumerGroupMembersCommand(context))
    members_section.add_command(consumer_group_members.AddConsumerGroupMembersCommand(context))
    members_section.add_command(consumer_group_members.RemoveConsumerGroupMembersCommand(context))

    # New subsections for group subsection
    consumer_group_section.add_subsection(ConsumerGroupPackageSection(context))
