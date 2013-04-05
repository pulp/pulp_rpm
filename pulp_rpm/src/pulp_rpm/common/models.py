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
import shutil
from pulp_rpm.common import ids, constants

_LOGGER = logging.getLogger(__name__)


class Package(object):
    UNIT_KEY_NAMES = tuple()
    TYPE = None
    def __init__(self, local_vars):
        for name in self.UNIT_KEY_NAMES:
            setattr(self, name, local_vars[name])
        self.metadata = local_vars.get('metadata', {})

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
            if key in cls.UNIT_KEY_NAMES:
                unit_key[key] = value
            elif key == 'type' and cls != Errata:
                continue
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
    def complete_version(self):
        values = []
        for name in ('epoch', 'version', 'release'):
            if name in self.UNIT_KEY_NAMES:
                values.append(getattr(self, name))
        return ''.join(values)


class Distribution(Package):
    UNIT_KEY_NAMES = ('id', 'family', 'variant', 'version', 'arch')
    TYPE = 'distribution'

    def __init__(self, family, variant, version, arch):
        kwargs = locals()
        # I don't know why this is the "id", but am following the pattern of the
        # original importer
        kwargs['id'] = '-'.join(('ks', family, variant, version, arch))
        super(Distribution, self).__init__(kwargs)

    @property
    def relative_path(self):
        """
        For this model, the relative path will be a directory in which all
        related files get stored. For most unit types, this path is to one
        file.
        """
        return self.id

    def process_download_reports(self, reports):
        """
        Once downloading is complete, add information about each file to this
        model instance. This is required before saving the new unit.

        :param reports: list of successful download reports
        :type  reports: list(pulp.common.download.report.DownloadReport)
        """
        _LOGGER.info([r.data for r in reports])
        metadata_files = self.metadata.setdefault('files', [])
        for report in reports:
            # the following data model is mostly intended to match what the
            # previous importer generated.
            metadata_files.append({
                'checksum': report.data['checksum'],
                'checksumtype': report.data['checksumtype'],
                'downloadurl': report.url,
                'filename': os.path.basename(report.data['relativepath']),
                'fileName': os.path.basename(report.data['relativepath']),
                'item_type': ids.TYPE_ID_DISTRO,
                'pkgpath': os.path.join(
                    constants.DISTRIBUTION_STORAGE_PATH,
                    self.id,
                    os.path.dirname(report.data['relativepath']),
                ),
                'relativepath': report.data['relativepath'],
                'savepath': report.destination,
                'size': report.total_bytes,
            })


class DRPM(Package):
    UNIT_KEY_NAMES = ('epoch',  'version', 'release', 'filename', 'checksumtype', 'checksum')
    TYPE = 'drpm'

    def __init__(self, epoch, version, release, filename, checksumtype, checksum, metadata):
        Package.__init__(self, locals())

    @property
    def relative_path(self):
        return self.filename


class RPM(Package):
    UNIT_KEY_NAMES = ('name', 'epoch', 'version', 'release', 'arch', 'checksumtype', 'checksum')
    TYPE = 'rpm'

    def __init__(self, name, epoch, version, release, arch, checksumtype, checksum, metadata):
        Package.__init__(self, locals())

    @property
    def relative_path(self):
        unit_key = self.unit_key
        return os.path.join(
            unit_key['name'], unit_key['version'], unit_key['release'],
            unit_key['arch'], unit_key['checksum'], self.metadata['relative_url_path']
        )


class Errata(Package):
    UNIT_KEY_NAMES = ('id',)
    TYPE = 'erratum'

    def __init__(self, id, metadata):
        Package.__init__(self, locals())


class PackageGroup(Package):
    UNIT_KEY_NAMES = ('id', 'repo_id')
    TYPE = 'package_group'
