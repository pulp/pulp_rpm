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

from collections import namedtuple
import csv
from gettext import gettext as _
import hashlib
import logging
import os
from urlparse import urljoin

from pulp_rpm.common import constants, version_utils

_LOGGER = logging.getLogger(__name__)


class Package(object):
    UNIT_KEY_NAMES = tuple()
    TYPE = None
    NAMEDTUPLE = None
    def __init__(self, local_vars):
        self.metadata = local_vars.get('metadata', {})
        for name in self.UNIT_KEY_NAMES:
            setattr(self, name, local_vars[name])
            # Add the serialized version and release if available
            if name == 'version':
                self.metadata['version_sort_index'] = version_utils.encode(local_vars[name])
            elif name == 'release':
                self.metadata['release_sort_index'] = version_utils.encode(local_vars[name])

    @property
    def unit_key(self):
        key = {}
        for name in self.UNIT_KEY_NAMES:
            key[name] = getattr(self, name)
        return key

    @property
    def as_named_tuple(self):
        """

        :return:
        :rtype collections.namedtuple
        """
        return self.NAMEDTUPLE(**self.unit_key)

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

    def clean_metadata(self):
        """
        Iterate through each key in the "metadata" dict, and if it starts with
        a "_", delete it. This is to clean out mongo-specific and platform-specific
        data. In the future, this will likely go away if we more strongly define
        which fields each model will hold.
        """
        for key in self.metadata.keys():
            if key.startswith('_'):
                del self.metadata[key]

    def __str__(self):
        return '%s: %s' % (self.TYPE, '-'.join(getattr(self, name) for name in self.UNIT_KEY_NAMES))


class VersionedPackage(Package):
    @property
    def key_string_without_version(self):
        keys = [getattr(self, key) for key in self.UNIT_KEY_NAMES if key not in ['epoch', 'version', 'release', 'checksum', 'checksumtype']]
        keys.append(self.TYPE)
        return '-'.join(keys)

    @property
    def complete_version(self):
        values = []
        for name in ('epoch', 'version', 'release'):
            if name in self.UNIT_KEY_NAMES:
                values.append(getattr(self, name))
        return tuple(values)

    @property
    def complete_version_serialized(self):
        return tuple(version_utils.encode(field) for field in self.complete_version)

    def __cmp__(self, other):
        return cmp(
            self.complete_version_serialized,
            other.complete_version_serialized
        )


class Distribution(Package):
    UNIT_KEY_NAMES = ('id', 'family', 'variant', 'version', 'arch')
    TYPE = 'distribution'

    def __init__(self, family, variant, version, arch, metadata, id=None):
        kwargs = locals()
        # I don't know why this is the "id", but am following the pattern of the
        # original importer
        if kwargs['id'] is None:
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
        # TODO: maybe this shouldn't be in common
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
                'item_type': self.TYPE,
                'pkgpath': os.path.join(
                    constants.DISTRIBUTION_STORAGE_PATH,
                    self.id,
                    os.path.dirname(report.data['relativepath']),
                ),
                'relativepath': report.data['relativepath'],
                'savepath': report.destination,
                'size': report.total_bytes,
            })


class DRPM(VersionedPackage):
    UNIT_KEY_NAMES = ('epoch',  'version', 'release', 'filename', 'checksumtype', 'checksum')
    TYPE = 'drpm'

    def __init__(self, epoch, version, release, filename, checksumtype, checksum, metadata):
        Package.__init__(self, locals())

    @property
    def relative_path(self):
        return self.filename

    @property
    def download_path(self):
        return self.filename


class RPM(VersionedPackage):
    UNIT_KEY_NAMES = ('name', 'epoch', 'version', 'release', 'arch', 'checksumtype', 'checksum')
    TYPE = 'rpm'

    def __init__(self, name, epoch, version, release, arch, checksumtype, checksum, metadata):
        Package.__init__(self, locals())
        self.raw_xml = ''

    @property
    def relative_path(self):
        unit_key = self.unit_key
        return os.path.join(
            unit_key['name'], unit_key['version'], unit_key['release'],
            unit_key['arch'], unit_key['checksum'], self.metadata['relativepath']
        )

    @property
    def download_path(self):
        return self.metadata['relativepath']


class SRPM(RPM):
    TYPE = 'srpm'


class Errata(Package):
    UNIT_KEY_NAMES = ('id',)
    TYPE = 'erratum'

    def __init__(self, id, metadata):
        Package.__init__(self, locals())

    @property
    def rpm_search_dicts(self):
        ret = []
        for collection in self.metadata.get('pkglist', []):
            for package in collection.get('packages', []):
                if len(package.get('sum') or []) == 2:
                    checksum = package['sum'][1]
                    checksumtype = package['sum'][0]
                elif 'sums' in package and 'type' in package:
                    # these are the field names we get from an erratum upload.
                    # I have no idea why they are different.
                    checksum = package['sums']
                    checksumtype = package['type']
                else:
                    checksum = None
                    checksumtype = None
                rpm = RPM(name=package['name'], epoch=package['epoch'],
                           version=package['version'], release=package['release'],
                           arch=package['arch'], checksum=checksum,
                           checksumtype=checksumtype, metadata={},
                )
                unit_key = rpm.unit_key
                for key in ['checksum', 'checksumtype']:
                    if unit_key[key] is None:
                        del unit_key[key]
                ret.append(unit_key)
        return ret


class PackageGroup(Package):
    UNIT_KEY_NAMES = ('id', 'repo_id')
    TYPE = 'package_group'

    def __init__(self, id, repo_id, metadata):
        Package.__init__(self, locals())
        # these attributes should default to False based on yum.comps.Group.parse
        for name in ('default', 'user_visible'):
            if self.metadata.get(name) is None:
                self.metadata[name] = False

    @property
    def all_package_names(self):
        names = []
        for list_name in [
            'mandatory_package_names',
            'default_package_names',
            'optional_package_names',
            # TODO: conditional package names
        ]:
            names.extend(self.metadata.get(list_name, []))
        return names


class PackageCategory(Package):
    UNIT_KEY_NAMES = ('id', 'repo_id')
    TYPE = 'package_category'

    def __init__(self, id, repo_id, metadata):
        Package.__init__(self, locals())

    @property
    def group_names(self):
        return self.metadata.get('packagegroupids', [])


class YumMetadataFile(Package):
    UNIT_KEY_NAMES = ('data_type', 'repo_id')
    TYPE = 'yum_repo_metadata_file'

    def __init__(self, data_type, repo_id, metadata):
        Package.__init__(self, locals())

    @property
    def relative_dir(self):
        """
        returns the relative path to the directory where the file should be
        stored. Since we don't have the filename in the metadata, we can't
        derive the full path here.
        """
        return self.repo_id


TYPE_MAP = {
    Distribution.TYPE: Distribution,
    DRPM.TYPE: DRPM,
    Errata.TYPE: Errata,
    PackageCategory.TYPE: PackageCategory,
    PackageGroup.TYPE: PackageGroup,
    RPM.TYPE: RPM,
    SRPM.TYPE: SRPM,
    YumMetadataFile.TYPE: YumMetadataFile,
}

# put the NAMEDTUPLE attribute on each model class
for model_class in TYPE_MAP.values():
    model_class.NAMEDTUPLE = namedtuple(model_class.TYPE, model_class.UNIT_KEY_NAMES)


def from_typed_unit_key_tuple(typed_tuple):
    """
    This assumes that the __init__ method takes unit key arguments in order
    followed by a dictionary for other metadata.

    :param typed_tuple:
    :return:
    """
    package_class = TYPE_MAP[typed_tuple[0]]
    args = typed_tuple[1:]
    return package_class.from_package_info(*args, metadata={})


# ------------ ISO Models --------------- #

# How many bytes we want to read into RAM at a time when calculating an ISO checksum
CHECKSUM_CHUNK_SIZE = 32 * 1024 * 1024


class ISO(object):
    """
    This is a handy way to model an ISO unit, with some related utilities.
    """
    TYPE = 'iso'

    def __init__(self, name, size, checksum, unit=None):
        """
        Initialize an ISO, with its name, size, and checksum.

        :param name:     The name of the ISO
        :type  name:     basestring
        :param size:     The size of the ISO, in bytes
        :type  size:     int
        :param checksum: The SHA-256 checksum of the ISO
        :type  checksum: basestring
        """
        self.name = name
        self.size = size
        self.checksum = checksum

        # This is the Unit that the ISO represents. An ISO doesn't always have a Unit backing it,
        # particularly during repository synchronization or ISO uploads when the ISOs are being
        # initialized.
        self._unit = unit

    @classmethod
    def from_unit(cls, unit):
        """
        Construct an ISO out of a Unit.
        """
        return cls(unit.unit_key['name'], unit.unit_key['size'], unit.unit_key['checksum'], unit)

    def init_unit(self, conduit):
        """
        Use the given conduit's init_unit() call to initialize a unit, and store the unit as self._unit.

        :param conduit: The conduit to call init_unit() to get a Unit.
        :type  conduit: pulp.plugins.conduits.mixins.AddUnitMixin
        """
        relative_path = os.path.join(self.name, self.checksum, str(self.size), self.name)
        unit_key = {'name': self.name, 'size': self.size, 'checksum': self.checksum}
        metadata = {}
        self._unit = conduit.init_unit(self.TYPE, unit_key, metadata, relative_path)

    def save_unit(self, conduit):
        """
        Use the given conduit's save_unit() call to save self._unit.

        :param conduit: The conduit to call save_unit() with.
        :type  conduit: pulp.plugins.conduits.mixins.AddUnitMixin
        """
        conduit.save_unit(self._unit)

    @property
    def storage_path(self):
        """
        Return the storage path of the Unit that underlies this ISO.
        """
        return self._unit.storage_path

    def validate(self):
        """
        Validate that the file found at self.storage_path matches the size and checksum of self. A ValueError
        will be raised if the validation fails.
        """
        with open(self.storage_path) as destination_file:
            # Validate the size
            actual_size = self.calculate_size(destination_file)
            if actual_size != self.size:
                raise ValueError(_('Downloading <%(name)s> failed validation. '
                    'The manifest specified that the file should be %(expected)s bytes, but '
                    'the downloaded file is %(found)s bytes.') % {'name': self.name,
                        'expected': self.size, 'found': actual_size})

            # Validate the checksum
            actual_checksum = self.calculate_checksum(destination_file)
            if actual_checksum != self.checksum:
                raise ValueError(
                    _('Downloading <%(name)s> failed checksum validation. The manifest '
                      'specified the checksum to be %(c)s, but it was %(f)s.') % {
                        'name': self.name, 'c': self.checksum,
                        'f': actual_checksum})

    @staticmethod
    def calculate_checksum(file_handle):
        """
        Return the sha256 checksum of the given file-like object.

        :param file_handle: A handle to an open file-like object
        :type  file_handle: file-like object
        :return:            The file's checksum
        :rtype:             string
        """
        file_handle.seek(0)
        hasher = hashlib.sha256()
        bits = file_handle.read(CHECKSUM_CHUNK_SIZE)
        while bits:
            hasher.update(bits)
            bits = file_handle.read(CHECKSUM_CHUNK_SIZE)
        return hasher.hexdigest()

    @staticmethod
    def calculate_size(file_handle):
        """
        Return the size of the given file-like object in Bytes.

        :param file_handle: A handle to an open file-like object
        :type  file_handle: file-like object
        :return:            The file's size, in Bytes
        :rtype:             int
        """
        # Calculate the size by seeking to the end to find the file size with tell()
        file_handle.seek(0, 2)
        size = file_handle.tell()
        return size


class ISOManifest(object):
    """
    This class provides an API that is a handy way to interact with a PULP_MANIFEST file. It automatically
    instantiates ISOs out of the items found in the manifest.
    """
    # This is the filename that the manifest is published to
    FILENAME = 'PULP_MANIFEST'

    def __init__(self, manifest_file, repo_url):
        """
        Instantiate a new ISOManifest from the open manifest_file.

        :param manifest_file: An open file-like handle to a PULP_MANIFEST file
        :type  manifest_file: An open file-like object
        :param repo_url:      The URL to the repository that this manifest came from. This is used
                              to determine a url attribute for each ISO in the manifest.
        :type  repo_url:      str
        """
        # Make sure we are reading from the beginning of the file
        manifest_file.seek(0)
        # Now let's process the manifest and return a list of resources that we'd like to download
        manifest_csv = csv.reader(manifest_file)
        self._isos = []
        for unit in manifest_csv:
            name, checksum, size = unit
            iso = ISO(name, int(size), checksum)
            # Take a URL onto the ISO so we know where we can get it
            iso.url = urljoin(repo_url, name)
            self._isos.append(iso)

    def __iter__(self):
        """
        Return an iterator for the ISOs in the manifest.
        """
        return iter(self._isos)

    def __len__(self):
        """
        Return the number of ISOs in the manifest.
        """
        return len(self._isos)
