# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the License
# (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied, including the
# implied warranties of MERCHANTABILITY, NON-INFRINGEMENT, or FITNESS FOR A
# PARTICULAR PURPOSE.
# You should have received a copy of GPLv2 along with this software; if not,
# see http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt

from pulp_rpm.common import constants, models

type_done_map = {
    models.RPM.TYPE: 'rpm_done',
    models.SRPM.TYPE: 'rpm_done',
    models.DRPM.TYPE: 'drpm_done',
}

type_total_map = {
    'rpm_total' : models.RPM.TYPE,
    'drpm_total' : models.DRPM.TYPE,
}


class DistributionReport(dict):
    def __init__(self):
        self['error_details'] = []
        self['items_total'] = 0
        self['items_left'] = 0
        self['state'] = constants.STATE_NOT_STARTED

    def set_initial_values(self, items_total):
        self['items_total'] = items_total
        self['items_left'] = items_total


class ContentReport(dict):
    def __init__(self):
        self['error_details'] = []
        self['items_total'] = 0
        self['items_left'] = 0
        self['size_total'] = 0
        self['size_left'] = 0
        self['state'] = constants.STATE_NOT_STARTED
        self['details'] = {
            'rpm_done' : 0,
            'rpm_total': 0,
            'drpm_done' : 0,
            'drpm_total': 0,
        }

    def set_initial_values(self, counts, total_size):
        self['size_total'] = total_size
        self['size_left'] = total_size
        self['items_total'] = sum(counts.values())
        self['items_left'] = sum(counts.values())
        for total_name, total_type in type_total_map.iteritems():
            self['details'][total_name] = counts[total_type]

    def success(self, model):
        self['items_left'] -= 1
        self['size_left'] -= model.metadata['size']
        done_attribute = type_done_map[model.TYPE]
        self['details'][done_attribute] += 1
        return self

    def failure(self, model, error_report):
        self['items_left'] -= 1
        self['size_left'] -= model.metadata['size']
        done_attribute = type_done_map[model.TYPE]
        self['details'][done_attribute] += 1
        self['error_details'].append(error_report)
        return self
