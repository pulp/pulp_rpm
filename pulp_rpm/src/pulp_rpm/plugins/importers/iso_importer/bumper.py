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
from cStringIO import StringIO
from urlparse import urljoin
import csv
import logging
import os

import pycurl


ISO_METADATA_FILENAME = 'PULP_MANIFEST'


logger = logging.getLogger(__name__)


class Bumper(object):
    """
    This is the superclass that type specific Bumpers should subclass. It has basic facilities for
    retrieving files from the Interweb.
    """
    def __init__(self, feed_url, working_directory, max_speed=None, num_threads=5,
                 ssl_client_cert=None, ssl_ca_cert=None, proxy_url=None, proxy_port=None,
                 proxy_user=None, proxy_password=None):
        """
        Configure the Bumper for the feed specified by feed_url. All other parameters are
        optional.
        """
        self.feed_url          = feed_url
        self.working_directory = working_directory
        self.max_speed         = max_speed
        self.num_threads       = num_threads
        self.proxy_url         = proxy_url
        self.proxy_port        = proxy_port
        self.proxy_user        = proxy_user
        self.proxy_password    = proxy_password
        self.ssl_client_cert   = ssl_client_cert
        self.ssl_ca_cert       = ssl_ca_cert

    def download_files(self, files):
        for resource in files:
            destination_path = os.path.join(self.working_directory, resource['name'])
            with open(destination_path, 'w') as destination_file:
                self._download_file(resource['url'], destination_file)
            resource['path'] = destination_path

    def _download_file(self, url, destination_file):
        curl = pycurl.Curl()
        curl.setopt(pycurl.VERBOSE, 0)
        # Close out the connection on our end in the event the remote host
        # stops responding. This is interpretted as "If less than 1000 bytes are
        # sent in a 5 minute interval, abort the connection."
        curl.setopt(pycurl.LOW_SPEED_LIMIT, 1000)
        curl.setopt(pycurl.LOW_SPEED_TIME, 5 * 60)
        curl.setopt(pycurl.URL, url)
        curl.setopt(pycurl.WRITEFUNCTION, destination_file.write)

        # Use curl to get the file
        curl.perform()
        status = curl.getinfo(curl.HTTP_CODE)
        curl.close()
        if status == 401:
            raise exceptions.UnauthorizedException(url)
        elif status == 404:
            raise exceptions.FileNotFoundException(url)
        elif status != 200:
            raise exceptions.FileRetrievalException(url)


class ISOBumper(Bumper):
    """
    An ISOBumper is capable of retrieving ISOs from an RPM repository for you, if that repository
    provides the expected PULP_MANIFEST file at the given URL. The Bumper provides a friendly
    manifest interface for you to inspect the available units, and also provides facilities for you
    to specify which units you would like it to retrieve and where you would like it to place them.
    """
    @property
    def manifest(self):
        """
        This handy property returns an ISOManifest object to you, which has a handy interface for
        inspecting which ISO units are available at the feed URL.
        """
        # We don't want to retrieve the manifest more than once when callers use this property, so
        # if we already have the manifest return it.
        if hasattr(self, '_manifest'):
            return self._manifest
        manifest_url = urljoin(self.feed_url, ISO_METADATA_FILENAME)
        manifest_bits = StringIO()
        self._download_file(manifest_url, manifest_bits)
        manifest_bits.seek(0)
        manifest_csv = csv.reader(manifest_bits)
        self._manifest = []
        for unit in manifest_csv:
            name, checksum, size = unit
            # TODO: Is the checksum type correct?
            self._manifest.append({'name': name, 'checksum': checksum, 'checksum_type': 'sha256',
                                   'size': size, 'url': urljoin(self.feed_url, name)})

        return self._manifest
