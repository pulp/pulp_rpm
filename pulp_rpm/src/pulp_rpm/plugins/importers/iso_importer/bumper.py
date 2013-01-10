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
from gettext import gettext as _
from urlparse import urljoin
import csv
import hashlib
import logging
import os

import pycurl


ISO_METADATA_FILENAME = 'PULP_MANIFEST'
# How many bytes we want to read into RAM at a time when validating a download checksum
VALIDATION_CHUNK_SIZE = 32*1024*1024


logger = logging.getLogger(__name__)


class CACertError(Exception):
    """
    This Exception is raised when PycURL doesn't have a CA certificate that can authenticate the remote server.
    """
    pass


class DownloadValidationError(Exception):
    """
    This Exception is raised when a download fails validation.
    """
    pass


class HTTPForbiddenException(Exception):
    """
    This Exception is raised when the remote server returns a 403 status.
    """
    pass


class Bumper(object):
    """
    This is the superclass that type specific Bumpers should subclass. It has basic facilities for
    retrieving files from the Interweb.
    """
    def __init__(self, feed_url, working_path, max_speed=None, num_threads=5,
                 ssl_client_cert=None, ssl_client_key=None, ssl_ca_cert=None, proxy_url=None,
                 proxy_port=None, proxy_user=None, proxy_password=None):
        """
        Configure the Bumper for the feed specified by feed_url. All other parameters are
        optional, and currently many of them are unused. The unused parameters are in place to
        specify the method signature for the future when we are able to implement the features. The
        unused parameters are: max_speed, num_threads, ssl_client_cert, ssl_ca_cert, proxy_url,
        proxy_port, proxy_user, and proxy_password.

        :param feed_url:          The URL of the feed from which we will download content.
        :type  feed_url:          str
        :param working_path:      The path on the local disk where the downloaded files should be
                                  saved.
        :type  working_path:      basestring
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
        :param ssl_client_key:    The key for the SSL client certificate
        :type  ssl_client_key:    str
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
        # It's very important that feed_url end with a trailing slash due to our use of urljoin.
        if self.feed_url[-1] != '/':
            self.feed_url = '%s/'%self.feed_url
        self.working_path      = working_path
        self.max_speed         = max_speed
        self.num_threads       = num_threads
        self.proxy_url         = proxy_url
        self.proxy_port        = proxy_port
        self.proxy_user        = proxy_user
        self.proxy_password    = proxy_password
        self.ssl_client_cert   = ssl_client_cert
        self.ssl_client_key    = ssl_client_key
        self.ssl_ca_cert       = ssl_ca_cert

        # A list of paths that we have created while messing around that should be removed when we are done doing stuff
        # It is a LIFO, and the paths will be removed in reverse order
        self._paths_to_cleanup = []
        # A list of methods that should be called after download is finished
        self._post_download_hooks = [self._cleanup_paths]

    def download_resources(self, resources):
        """
        This method will fetch the given resources to self.working_path. resources should be a
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
            # Make this overridable by being it's own method
            destination_path = os.path.join(self.working_path, resource['name'])
            with open(destination_path, 'w+b') as destination_file:
                self._download_resource(resource, destination_file)
            downloaded_resource = resource
            downloaded_resource['path'] = destination_path
            downloaded_resources.append(downloaded_resource)
        return downloaded_resources

    def _cleanup_paths(self):
        """
        Calls os.unlink() or os.rmdir on all paths in self._paths_to_cleanup in reverse order, and removes them from
        that list.
        """
        while self._paths_to_cleanup:
            path = self._paths_to_cleanup.pop()
            if os.path.isdir(path):
                os.rmdir(path)
            else:
                os.unlink(path)

    def _configure_curl_ssl_parameters(self, curl):
        """
        Configure our curl for SSL.

        :param curl: The Curl instance we want to configure for SSL
        :type  curl: pycurl.Curl
        """
        # This will make sure we don't download content from any peer unless their SSL cert checks
        # out against a CA
        # We could make this an option, but it doesn't seem wise.
        logger.debug('setting SSL_VERIFYPEER')
        logger.debug('os.getuid(): %s'%os.getuid())
        curl.setopt(pycurl.SSL_VERIFYPEER, True)
        # Unfortunately, pycurl doesn't accept the bits for SSL keys or certificates, but instead
        # insists on being handed a path. We must use a file to hand the bits to pycurl.
        _ssl_working_path = os.path.join(self.working_path, 'SSL_CERTIFICATES')
        if not os.path.exists(_ssl_working_path):
            logger.debug('Making %s'%_ssl_working_path)
            os.mkdir(_ssl_working_path, 0700)
            self._paths_to_cleanup.append(_ssl_working_path)
        pycurl_ssl_option_paths = {
            pycurl.CAINFO:  {'path': os.path.join(_ssl_working_path, 'ca.pem'),
                             'data': self.ssl_ca_cert},
            pycurl.SSLCERT: {'path': os.path.join(_ssl_working_path, 'client.pem'),
                             'data': self.ssl_client_cert},
            pycurl.SSLKEY:  {'path': os.path.join(_ssl_working_path, 'client-key.pem'),
                             'data': self.ssl_client_key}}
        for pycurl_setting, ssl_data in pycurl_ssl_option_paths.items():
            # We don't want to do anything if the user didn't pass us any certs or keys
            if ssl_data['data']:
                path = ssl_data['path']
                if os.path.exists(path):
                    os.unlink(path)
                logger.debug("Adding %s to cleaup"%path)
                self._paths_to_cleanup.append(path)
                with open(path, 'w') as ssl_file:
                    logger.debug('Writing to the file')
                    ssl_file.write(ssl_data['data'])
                logger.debug('Telling pycurl about the file')
                logger.debug('pycurl.CAINFO: %s'%pycurl.CAINFO)
                logger.debug('pycurl.SSLCERT: %s'%pycurl.SSLCERT)
                logger.debug('pycurl.SSLKEY: %s'%pycurl.SSLKEY)
                logger.debug('pycurl_setting: %s'%pycurl_setting)
                logger.debug('path: %s'%path)
                curl.setopt(pycurl_setting, str(path))
        logger.debug('DONE')

    # TODO: Figure out how to cancel a download
    # http://curl.haxx.se/mail/curlpython-2009-02/0003.html
    # This details a way we might be able to cancel and also achieve multiple simultaneous
    # downloads:
    # http://pycurl.cvs.sourceforge.net/viewvc/pycurl/pycurl/examples/retriever-multi.py?revision=1.29&view=markup
    # TODO: Split Curl creation out into another method
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
        logger.debug(_('Retrieving %(url)s')%{'url': resource['url']})
        curl = pycurl.Curl()
        curl.setopt(pycurl.VERBOSE, 0)
        # Close out the connection on our end in the event the remote host
        # stops responding. This is interpretted as "If less than 1000 bytes are
        # sent in a 5 minute interval, abort the connection."
        curl.setopt(pycurl.LOW_SPEED_LIMIT, 1000)
        curl.setopt(pycurl.LOW_SPEED_TIME, 5 * 60)
        curl.setopt(pycurl.URL, resource['url'])
        curl.setopt(pycurl.WRITEFUNCTION, destination_file.write)
        curl.setopt(pycurl.PROGRESSFUNCTION, self._progress_report)
        logger.debug('About to _configure_curl_ssl_parameters()')
        if self.ssl_ca_cert or self.ssl_client_cert or self.ssl_client_key:
            self._configure_curl_ssl_parameters(curl)
        logger.debug('Done!')

        # get the file
        logger.debug('curl.perform()')
        try:
            curl.perform()
        except pycurl.error, e:
            # TODO: Figure out which pycurl exceptions we want to handle. They are all listed in
            #       /usr/include/curl/curl.h
            if e[0] == pycurl.E_SSL_CACERT:
                raise CACertError(e.message)
            else:
                raise e
        logger.debug('Done!')
        status = curl.getinfo(curl.HTTP_CODE)
        curl.close()
        logger.debug('cURL status: %s'%status)
        # TODO: Make Exception handling here awesome
        if status == 401:
            raise exceptions.UnauthorizedException(url)
        elif status == 403:
            raise HTTPForbiddenException(resource['url'])
        elif status == 404:
            raise exceptions.FileNotFoundException(url)
        elif status != 200:
            raise exceptions.FileRetrievalException(url, status)
        # TODO: add pre/post hooks stuff
        for hook in self._post_download_hooks:
            hook()
        self._validate_download(resource, destination_file)

    # TODO: Support this progress report callback
    def _progress_report(self, dltotal, dlnow, ultotal, ulnow):
        """
        This is the callback that we give to pycurl to report back to us about the download progress.

        :param dltotal: How much there is to download
        :type  dltotal: float
        :param dlnow:   How much we have already downloaded
        :type  dlnow:   float
        :param ultotal: How much there is to upload
        :type  ultotal: float
        :param ulnow:   How much we have already uploaded
        :type  ulnow:   float:
        """
        pass

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
    # TODO: Make this not a property
    # TODO: Remove caching
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
                                   'size': int(size), 'url': urljoin(self.feed_url, name)})

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
        logger.debug('Validating %s'%resource)
        # Validate the size, if we know what it should be
        if 'size' in resource:
            # seek to the end to find the file size with tell()
            destination_file.seek(0, 2)
            size = destination_file.tell()
            logger.debug('Validating that the download size is %s'%resource['size'])
            if size != resource['size']:
                raise DownloadValidationError(_('Downloading <%(name)s> failed validation. '
                    'The manifest specified that the file should be %(expected)s bytes, but '
                    'the downloaded file is %(found)s bytes.')%{'name': resource['name'],
                        'expected': resource['size'], 'found': size})

        # Validate the checksum, if we know what it should be
        # TODO: Actually do validation with chunking and stuff
        if 'checksum' in resource:
            logger.debug('Validating that the checksum is %s'%resource['checksum'])
            destination_file.seek(0)
            hasher = hashlib.sha256()
            logger.debug("destination_file.closed: %s"%destination_file.closed)
            bits = destination_file.read(VALIDATION_CHUNK_SIZE)
            while bits:
                hasher.update(bits)
                bits = destination_file.read(VALIDATION_CHUNK_SIZE)
            # Verify that, son!
            if hasher.hexdigest() != resource['checksum']:
                raise DownloadValidationError(_('Downloading <%(name)s failed checksum validation.')%{
                                                    'name': resource['name']})
