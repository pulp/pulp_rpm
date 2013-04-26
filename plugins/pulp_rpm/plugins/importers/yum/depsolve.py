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

from pulp_rpm.common import version_utils


class Dependency(object):
    EQ = 'EQ'
    LT = 'LT'
    LE = 'LE'
    GT = 'GT'
    GE = 'GE'

    def __init__(self, name, epoch=None, version=None, release=None, flags=None):
        self.name = name
        self.epoch = epoch
        self.version = version
        self.release = release
        # no idea why this is plural, but that's how it looks in primary.xml
        self.flags = flags

    def __cmp__(self, other):
        return cmp(
            map(version_utils.encode, [self.epoch, self.version, self.release]),
            map(version_utils.encode, [other.epoch, other.version, other.release])
        )

    def __eq__(self, other):
        return cmp(
            (self.epoch, self.version, self.release),
            (other.epoch, other.version, other.release)
        )

    def __ne__(self, other):
        return not self == other



class Provide(Dependency):
    pass


class Require(Dependency):
    def fills_requirement(self, provide):
        if self.flags == self.EQ:
            return provide == self
        if self.flags == self.LT:
            return provide < self
        if self.flags == self.LE:
            return provide <= self
        if self.flags == self.GT:
            return provide > self
        if self.flags == self.GE:
            return provide >= self


def find_providing_rpms(units):

