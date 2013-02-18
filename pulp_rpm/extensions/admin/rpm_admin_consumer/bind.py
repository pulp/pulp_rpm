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

from pulp.client.commands.consumer.bind import (
    ConsumerBindCommand, ConsumerUnbindCommand)


YUM_DISTRIBUTOR_ID = 'yum_distributor'


class YumConsumerBindCommand(ConsumerBindCommand):

    def add_distributor_option(self):
        pass

    def get_distributor_id(self, kwargs):
        return YUM_DISTRIBUTOR_ID


class YumConsumerUnbindCommand(ConsumerUnbindCommand):

    def add_distributor_option(self):
        pass

    def get_distributor_id(self, kwargs):
        return YUM_DISTRIBUTOR_ID

