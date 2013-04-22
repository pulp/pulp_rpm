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
from urlparse import urljoin
import csv
import hashlib
import os

from pulp_rpm.common import ids


# How many bytes we want to read into RAM at a time when validating a download checksum
VALIDATION_CHUNK_SIZE = 32 * 1024 * 1024


class ISO(object):
    """
    This is a handy way to model an ISO unit, with some related utilities.
    """
    def __init__(self, name, size, checksum):
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

        self.unit_key = {'name': self.name, 'size': self.size, 'checksum': self.checksum}
        self.metadata = {}
        # This is the path on disk where the ISO is stored. This is set to None until the ISO is told otherwise.
        self.storage_path = None
        self.unit = None

    @classmethod
    def from_unit(cls, unit):
        """
        Construct an ISO out of a Unit.
        """
        return ISO(unit.unit_key['name'], unit.unit_key['size'], unit.unit_key['checksum'])

    def init_unit(self, conduit):
        """
        Use the given conduit's init_unit() call to initialize a unit, and store the unit as self.unit.

        :param conduit: The conduit to call init_unit() to get a Unit.
        :type  conduit: pulp.plugins.conduits.mixins.AddUnitMixin
        """
        relative_path = os.path.join(self.name, self.checksum, str(self.size), self.name)
        self.unit = conduit.init_unit(ids.TYPE_ID_ISO, self.unit_key, self.metadata, relative_path)
        self.storage_path = self.unit.storage_path

    def save_unit(self, conduit):
        """
        Use the given conduit's save_unit() call to save self.unit.

        :param conduit: The conduit to call save_unit() with.
        :type  conduit: pulp.plugins.conduits.mixins.AddUnitMixin
        """
        conduit.save_unit(self.unit)

    def validate(self):
        """
        Validate that the file found at self.storage_path matches the size and checksum of self. A ValueError
        will be raised if the validation fails.
        """
        with open(self.storage_path) as destination_file:
            # Validate the size by seeking to the end to find the file size with tell()
            destination_file.seek(0, 2)
            size = destination_file.tell()
            if size != self.size:
                raise ValueError(_('Downloading <%(name)s> failed validation. '
                    'The manifest specified that the file should be %(expected)s bytes, but '
                    'the downloaded file is %(found)s bytes.') % {'name': self.name,
                        'expected': self.size, 'found': size})

            # Validate the checksum
            destination_file.seek(0)
            hasher = hashlib.sha256()
            bits = destination_file.read(VALIDATION_CHUNK_SIZE)
            while bits:
                hasher.update(bits)
                bits = destination_file.read(VALIDATION_CHUNK_SIZE)
            # Verify that, son!
            if hasher.hexdigest() != self.checksum:
                raise ValueError(
                    _('Downloading <%(name)s> failed checksum validation. The manifest '
                      'specified the checksum to be %(c)s, but it was %(f)s.') % {
                        'name': self.name, 'c': self.checksum,
                        'f': hasher.hexdigest()})


class ISOManifest(object):
    """
    This class provides an API that is a handy way to interact with a PULP_MANIFEST file. It automatically
    instantiates ISOs out of the items found in the manifest.
    """
    def __init__(self, manifest_file, repo_url):
        """
        Instantiate a new ISOManifest from the open manifest_file.
        
        :param manifest_file: An open file-like handle to a PULP_MANIFEST file
        :type  manifest_file: An open file-like object
        :param repo_url:      The URL to the repository that this manifest came from. This is used to determine
                              a url attribute for each ISO in the manifest.
        :type  repo_url:      str
        """
        # Now let's process the manifest and return a list of resources that we'd like to download
        manifest_csv = csv.reader(manifest_file)
        self._isos = []
        for unit in manifest_csv:
            name, checksum, size = unit
            iso = ISO(name, int(size), checksum)
            iso.url = urljoin(repo_url, name)
            self._isos.append(iso)

    def __len__(self):
        """
        Return the number of ISOs in the manifest.
        """
        return len(self._isos)

    def __iter__(self):
        """
        Return an iterator for the ISOs in the manifest.
        """
        return iter(self._isos)
