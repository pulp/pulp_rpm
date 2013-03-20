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

import os.path
import logging

_LOGGER = logging.getLogger(__name__)



class Package(object):
    UNIT_KEY_NAMES = tuple()

    @property
    def unit_key(self):
        key = {}
        for name in self.UNIT_KEY_NAMES:
            key[name] = getattr(self, name)
        return key

    @classmethod
    def from_package_info(cls, package_info):
        unit_key = {}
        metadata = {}
        for key, value in package_info.iteritems():
            if key == 'checksum':
                unit_key['checksum'] = value['hex_digest']
                unit_key['checksumtype'] = value['algorithm']
            elif key in cls.UNIT_KEY_NAMES:
                unit_key[key] = value
            else:
                metadata[key] = value
        unit_key['metadata'] = metadata

        return cls(**unit_key)

    @property
    def key_string_without_version(self):
        keys = [key for key in self.UNIT_KEY_NAMES if key not in ['epoch', 'version', 'release']]
        keys.append(self.TYPE)
        return '-'.join(keys)

    @property
    def version(self):
        values = []
        for name in ('epoch', 'version', 'release'):
            if name in self.UNIT_KEY_NAMES:
                values.append(getattr(self, name))
        return ''.join(values)


class DRPM(Package):
    UNIT_KEY_NAMES = ('epoch',  'version', 'release', 'filename', 'checksumtype', 'checksum')
    TYPE = 'drpm'

    def __init__(self, name, epoch, version, release, arch, checksumtype, checksum, metadata):
        for name in self.UNIT_KEY_NAMES:
            setattr(self, name, locals()[name])
        self.metadata = metadata


class RPM(Package):
    UNIT_KEY_NAMES = ('name', 'epoch', 'version', 'release', 'arch', 'checksumtype', 'checksum')
    TYPE = 'rpm'

    def __init__(self, name, epoch, version, release, arch, checksumtype, checksum, metadata):
        for name in self.UNIT_KEY_NAMES:
            setattr(self, name, locals()[name])
        self.metadata = metadata

    @property
    def relative_path(self):
        unit_key = self.unit_key
        return os.path.join(
            unit_key['name'], unit_key['version'], unit_key['release'],
            unit_key['arch'], unit_key['checksum'], self.metadata['relative_url_path']
        )


class SRPM(RPM):
    TYPE = 'srpm'


class PackageGroup(Package):
    UNIT_KEY_NAMES = ('id', 'repo_id')
    TYPE = 'package_group'


type_map = {
    RPM.TYPE: RPM,
    SRPM.TYPE: SRPM,
    DRPM.TYPE: DRPM,
}


def from_package_info(package_info):
    package_type = package_info['type']

    if package_type in type_map:
        return type_map[package_type].from_package_info(package_info)

