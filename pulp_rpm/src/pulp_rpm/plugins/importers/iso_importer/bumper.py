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


class DownloadValidationError(Exception):
    """
    This Exception is raised when a download fails validation.
    """
    pass


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
        optional, and currently many of them are unused. The unused parameters are in place to
        specify the method signature for the future when we are able to implement the features. The
        unused parameters are: max_speed, num_threads, ssl_client_cert, ssl_ca_cert, proxy_url,
        proxy_port, proxy_user, and proxy_password.

        :param feed_url:          The URL of the feed from which we will download content.
        :type  feed_url:          str
        :param working_directory: The path on the local disk where the downloaded files should be
                                  saved.
        :type  working_directory: basestring
        :param max_speed:         The maximum speed that the download should happen at. This
                                  parameter is currently ignored, but is here for future expansion.
        :type  max_speed:         float
        :param num_threads:       How many threads should be used during download. This parameter is
                                  currently ignored, but is here for future expansion.
        :type  num_threads:       int
        :param ssl_client_cert:   The ssl cert that should be passed to the feed server when
                                  downloading files. This parameter is currently ignored, but is
                                  here for future expansion.
        :type  ssl_client_cert:   str
        :param ssl_ca_cert:       A certificate authority certificate that we will use to
                                  authenticate the feed. This parameter is currently ignored, but is
                                  here for future expansion.
        :type  ssl_ca_cert:       str
        :param proxy_url:         The URL for a proxy server to use to download content. This
                                  parameter is currently ignored, but is here for future expansion.
        :type  proxy_url:         str
        :param proxy_port:        The port for the proxy server. This parameter is currently
                                  ignored, but is here for future expansion.
        :type  proxy_port:        int
        :param proxy_user:        The username to use to authenticate to the proxy server. This
                                  parameter is currently ignored, but is here for future expansion.
        :param proxy_password:    The password to use to authenticate to the proxy server. This
                                  parameter is currently ignored, but is here for future expansion.
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

    def download_resources(self, resources):
        """
        This method will fetch the given resources to self.working_directory. resources should be a
        list of dictionaries, each of which must contain the keys 'name' and 'url'. A list of
        the resources that were downloaded will be returned, which is essentially the same as the
        resources list (in the case of no errors), each with an additional 'path' key that specifies
        an absolute path on disk where the resource was saved.

        :param resources: A list of dictionaries keyed by 'name' and 'url'.
        :type  resources: list
        :return:          The resources that were downloaded, each with the 'path' key set to the
                          absolute path on disk where the resource was stored.
        :rtype:           list
        """
        downloaded_resources = []
        for resource in resources:
            destination_path = os.path.join(self.working_directory, resource['name'])
            with open(destination_path, 'wb') as destination_file:
                self._download_resource(resource, destination_file)
            downloaded_resource = resource
            downloaded_resource['path'] = destination_path
            downloaded_resources.append(downloaded_resource)
        return downloaded_resources

    # TODO: Figure out how to cancel a download
    # http://curl.haxx.se/mail/curlpython-2009-02/0003.html
    # This details a way we might be able to cancel and also achieve multiple simultaneous
    # downloads:
    # http://pycurl.cvs.sourceforge.net/viewvc/pycurl/pycurl/examples/retriever-multi.py?revision=1.29&view=markup
    def _download_resource(self, resource, destination_file):
        """
        Download the given resource and save it to the destination_file. The resource should be a
        dictionary with a 'url' key that specifies the location of the resource.
        destination_file should be an opened file-like object that must have a write() method.

        :param resource:         A dictionary with a 'url' key that specifies the URL to the
                                 resource to be downloaded
        :type  resource:         dict
        :param destination_file: A file-like object in which to store the resource.
        :type  destination_file: object
        """
        curl = pycurl.Curl()
        curl.setopt(pycurl.VERBOSE, 0)
        # Close out the connection on our end in the event the remote host
        # stops responding. This is interpretted as "If less than 1000 bytes are
        # sent in a 5 minute interval, abort the connection."
        curl.setopt(pycurl.LOW_SPEED_LIMIT, 1000)
        curl.setopt(pycurl.LOW_SPEED_TIME, 5 * 60)
        curl.setopt(pycurl.URL, resource['url'])
        curl.setopt(pycurl.WRITEFUNCTION, destination_file.write)

        # get the file
        curl.perform()
        status = curl.getinfo(curl.HTTP_CODE)
        curl.close()
        if status == 401:
            raise exceptions.UnauthorizedException(url)
        elif status == 404:
            raise exceptions.FileNotFoundException(url)
        elif status != 200:
            raise exceptions.FileRetrievalException(url)
        _validate_download(resource, destination_file)


    def _validate_download(self, resource, destination_file):
        """
        This method can be overridden by subclasses to validate the download, if desired. This
        implementation just passes.
        """
        pass


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
        inspecting which ISO units are available at the feed URL. The manifest will be a list of
        dictionaries the each specify an ISO, with the following keys:

        name:          The name of the ISO
        checksum:      The checksum for the resource
        checksum_type: The type of the checksum (e.g., sha256)
        size:          The size of the ISO, in bytes
        url:           An absolute URL to the ISO

        These dictionaries are in the format that self._download_resource() expects for its resource
        parameter, isn't that handy?

        :return: A list of dictionaries that describe the available ISOs at the feed_url. They will
                 have the following keys: name, checksum, checksum_type, size, and url.
        :rtype:  dict
        """
        # We don't want to retrieve the manifest more than once when callers use this property, so
        # if we already have the manifest return it.
        if hasattr(self, '_manifest'):
            return self._manifest
        manifest_resource = {'url': urljoin(self.feed_url, ISO_METADATA_FILENAME)}
        # Let's just store the manifest in memory.
        manifest_bits = StringIO()
        self._download_resource(manifest_resource, manifest_bits)

        # Interpret the manifest as a CSV
        manifest_bits.seek(0)
        manifest_csv = csv.reader(manifest_bits)
        self._manifest = []
        for unit in manifest_csv:
            name, checksum, size = unit
            # TODO: Is the checksum type correct?
            self._manifest.append({'name': name, 'checksum': checksum, 'checksum_type': 'sha256',
                                   'size': size, 'url': urljoin(self.feed_url, name)})

        return self._manifest

    def _validate_download(self, resource, destination_file):
        """
        The PULP_MANIFEST file gives us a checksum for each ISO and its size, which we have access
        to through the resource parameter. This method validates the destination_file to ensure that
        the checksum and size match. This method only performs validation if the resource has
        'checksum' or 'size' attributes. destination_file must be a file-like object, and contains
        the data to be validated. This method will raise a DownloadValidationException if there is a
        problem, otherwise it returns silently.

        :param resource:         A dictionary describing the resource that we have downloaded. In
                                 order for validation to be performed, this must contain 'checksum'
                                 and/or size attributes.
        :type  resource:         dict
        :param destination_file: The file-like object to be validated.
        :type  destination_file: object
        """
        try:
            starting_position = destination_file.tell()

            # Validate the size, if we know what it should be
            if hasattr(resource, 'size'):
                # seek to the end to find the file size with tell()
                destination_file.seek(0, 2)
                size = destination_file.tell()
                if size != resource['size']:
                    raise DownloadValidationException(_('Downloading <%(name)s> failed validation. '
                        'The manifest specified that the file should be %(expected)s bytes, but '
                        'the downloaded file is %(found)s bytes.')%{'name': resource['name'],
                            'expected': resource['size'], 'found': size})

            # Validate the checksum, if we know what it should be
            # TODO: Actually do validation with chunking and stuff
            if hasattr(resource, 'checksum'):
                hasher = hashlib.sha256()
                hasher.update()
                hasher.hexdigest()
        finally:
            # be kind, rewind
            destination_file.seek(starting_position)
