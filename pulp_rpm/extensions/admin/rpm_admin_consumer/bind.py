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
    ConsumerBindCommand, ConsumerUnbindCommand, OPTION_DISTRIBUTOR_ID)


YUM_DISTRIBUTOR_ID = 'yum_distributor'


class YumConsumerBindCommand(ConsumerBindCommand):
    def __init__(self, context):
        super(self.__class__, self).__init__(context)
        # don't need this as an option because we'll hard code its passing
        self.options.remove(OPTION_DISTRIBUTOR_ID)

    def bind(self, **kwargs):
        kwargs[OPTION_DISTRIBUTOR_ID.keyword] = YUM_DISTRIBUTOR_ID
        super(self.__class__, self).bind(**kwargs)


class YumConsumerUnbindCommand(ConsumerUnbindCommand):
    def __init__(self, context):
        super(self.__class__, self).__init__(context)
        # don't need this as an option because we'll hard code its passing
        self.options.remove(OPTION_DISTRIBUTOR_ID)

    def unbind(self, **kwargs):
        kwargs[OPTION_DISTRIBUTOR_ID.keyword] = YUM_DISTRIBUTOR_ID
        super(self.__class__, self).unbind(**kwargs)

