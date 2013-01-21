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
from copy import copy
from cStringIO import StringIO
from gettext import gettext as _
from urlparse import urljoin
import csv
import hashlib
import logging
import os
import signal

import pycurl

# According to the libcurl documentation, we want to ignore SIGPIPE when using NOSIGNAL, which we
# want to do to improve threading:
# http://curl.haxx.se/libcurl/c/curl_easy_setopt.html#CURLOPTNOSIGNAL
signal.signal(signal.SIGPIPE, signal.SIG_IGN)

# TODO: Uh, do some science to determine what the ideal default is here
DEFAULT_NUM_THREADS = 2
ISO_METADATA_FILENAME = 'PULP_MANIFEST'
# How long we want to wait between loops on the MultiCurl select() method
SELECT_TIMEOUT = 1.0
# How many bytes we want to read into RAM at a time when validating a download checksum
VALIDATION_CHUNK_SIZE = 32*1024*1024


logger = logging.getLogger(__name__)


class CACertError(Exception):
    """
    This Exception is raised when PycURL doesn't have a CA certificate that can authenticate the
    remote server.
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
    This is a wrapper around pycurl. It has basic facilities for retrieving files from the Interweb.
    """
    def __init__(self, working_path, max_speed=None, num_threads=DEFAULT_NUM_THREADS,
                 proxy_url=None, proxy_port=None, proxy_user=None, proxy_password=None):
        """
        Configure a new Bumper to use the given parameters. working_path tells Bumper where it can
        store temporary working files, such as SSL certificates. All other parameters are
        optional. max_speed is currently unused.

        :param working_path:      The path on the local disk where the downloaded files should be
                                  saved.
        :type  working_path:      basestring
        :param max_speed:         The maximum speed that the download should happen at. This
                                  parameter is currently ignored, but is here for future expansion.
        :type  max_speed:         float
        :param num_threads:       How many threads should be used during download.
        :type  num_threads:       int
        :param proxy_url:         The hostname for a proxy server to use to download content. An
                                  optional http:// is allowed on the beginning of the string, but
                                  will be ignored.
        :type  proxy_url:         str
        :param proxy_port:        The port for the proxy server.
        :type  proxy_port:        int
        :param proxy_user:        The username to use to authenticate to the proxy server.
        :type  proxy_user:        str
        :param proxy_password:    The password to use to authenticate to the proxy server.
        :type  proxy_password:    str
        """
        self.working_path       = working_path
        self.max_speed          = max_speed
        self.num_threads        = int(num_threads)
        self.proxy_url          = proxy_url
        self.proxy_port         = proxy_port
        # TODO: Raise an exception if we have a proxy username but no password
        self.proxy_user         = proxy_user
        self.proxy_password     = proxy_password
        self._download_canceled = False

        # A list of paths that we have created while messing around that should be removed when we
        # are done doing stuff. It is a LIFO, and the paths will be removed in reverse order.
        self._paths_to_cleanup = []
        # A list of methods that should be called after download is finished
        self._post_download_hooks = [self._cleanup_paths]

    def cancel_download(self):
        self._download_canceled = True

    def _configure_curl(self, curl, resource):
        """
        Configure the given Curl object to download the resource described by resource.

        :param curl:     The Curl we need to configure
        :type  curl:     pycurl.Curl
        :param resource: The resource that this curl will be used to download. The resource should
                         be a dictionary that has at least 'url' and 'destination' keys. The url
                         should be the location that the Curl will be used to retrieve the resource
                         from. destination can be a string or a filelike object. If it is a string,
                         it will be interpreted as a local filesystem path at which the resource
                         should be stored. If it is a file-like object, it's write() method will be
                         used to store the resource. The resource may also optionally include
                         'ssl_ca_cert', 'ssl_client_cert', or 'ssl_client_key' keys, used to include
                         CA certificates, client certificates, or client keys that should be used to
                         retrieve this resource over SSL.
        :type  resource: dict
        """
        curl.setopt(pycurl.VERBOSE, 0)
        # Set the NOSIGNAL option, which is necessary for multi-threaded operation
        curl.setopt(pycurl.NOSIGNAL, 1)
        # Close out the connection on our end in the event the remote host
        # stops responding. This is interpretted as "If less than 1000 bytes are
        # sent in a 5 minute interval, abort the connection."
        curl.setopt(pycurl.LOW_SPEED_LIMIT, 1000)
        curl.setopt(pycurl.LOW_SPEED_TIME, 5 * 60)
        curl.setopt(pycurl.PROGRESSFUNCTION, self._progress_report)

        curl.setopt(pycurl.URL, resource['url'])
        if (hasattr(resource, 'ssl_ca_cert') and resource['ssl_ca_cert']) \
                or (hasattr(resource, 'ssl_client_cert') and resource['ssl_client_cert']) \
                or (hasattr(resource, 'ssl_client_key') and resource['ssl_client_key']):
            self._configure_curl_ssl_parameters(curl, resource)
        if self.proxy_url:
            self._configure_curl_proxy_parameters(curl)

        # Configure the Curl to store the bits at resource['destination']
        if isinstance(resource['destination'], basestring):
            curl.destination_file = open(resource['destination'], 'w+b')
        else:
            curl.destination_file = resource['destination']
        curl.setopt(pycurl.WRITEFUNCTION, curl.destination_file.write)

        # It's handy to be able to determine which resource this curl is currently configured for
        curl.resource = resource

    def _build_multi_curl(self):
        multi_curl = pycurl.CurlMulti()
        multi_curl.handles = []
        for i in range(self.num_threads):
            curl = pycurl.Curl()
            multi_curl.handles.append(curl)
        return multi_curl

    # TODO: Add a way to communicate errors in the return from this method. Perhaps a DownloadReport
    #       sort of object, or something along those lines.
    def download_resources(self, resources):
        """
        This method will fetch the given resources. resources should be a list of dictionaries, each
        of which must contain the keys 'url' and 'destination'. The url should be the location from
        which the resource should be fetched. destination can be a string or a filelike object. If
        it is a string, it will be interpreted as a local filesystem path at which the resource
        should be stored. If it is a file-like object, it's write() method will be used to store the
        resource. A copy of the list of the resources will be returned.

        :param resources: A list of dictionaries keyed by at least 'url' and 'destination'.
        :type  resources: list
        :return:          The resources that were downloaded, each with the 'path' key set to the
                          absolute path on disk where the resource was stored.
        :rtype:           list
        """
        downloaded_resources = []
        failed_resources = []
        multi_curl = self._build_multi_curl()

        # This indexes the position in the resources list of the next resource that we need to
        # retrieve. When it equals the number of resources in the list, we are done.
        next_resource_index = 0
        # We should copy these, so we can keep the references to all the handles in the multi_curl
        free_curls = copy(multi_curl.handles)
        multi_curl.busy_handles = []
        while len(downloaded_resources) + len(failed_resources) < len(resources) \
                and not self._download_canceled:
            while next_resource_index < len(resources) and free_curls:
                resource = resources[next_resource_index]
                curl = free_curls.pop()
                self._configure_curl(curl, resource)
                multi_curl.add_handle(curl)
                multi_curl.busy_handles.append(curl)
                multi_curl.select(SELECT_TIMEOUT)
                next_resource_index += 1
            multi_curl.select(SELECT_TIMEOUT)
            while True:
                return_code, num_handles = multi_curl.perform()
                # curl can return a code telling you that you must call perform() again immediately.
                if return_code != pycurl.E_CALL_MULTI_PERFORM:
                    break
            while True:
                num_queued_messages, finished_curls, error_list = multi_curl.info_read()
                # Handle the finished curls
                for curl in finished_curls:
                    logger.info(_('Successfully retrieved %(url)s')%{'url': curl.resource['url']})
                    # We should only close the destination file if the caller gave us a path to a
                    # file and not a file object.
                    if isinstance(curl.resource['destination'], basestring):
                        curl.destination_file.close()
                    downloaded_resources.append(curl.resource)
                    del curl.destination_file
                    del curl.resource
                    multi_curl.remove_handle(curl)
                    free_curls.append(curl)
                # Handle the error'd curls
                # TODO: uh, actually do something more useful than just logging it
                for curl, error_code, error_message in error_list:
                    logger.error(_('Error while retrieving %(url)s: %(m)s.')%{
                        'url': curl.resource['url'], 'm': error_message})
                    # TODO: Figure out which pycurl exceptions we want to handle. They are all
                    #       listed in /usr/include/curl/curl.h
                    if error_code == pycurl.E_SSL_CACERT:
                        raise CACertError(e.message)
                    else:
                        raise e
                    status = curl.getinfo(curl.HTTP_CODE)
                    curl.close()
                    # TODO: Make Exception handling here awesome
                    if status == 401:
                        raise exceptions.UnauthorizedException(url)
                    elif status == 403:
                        raise HTTPForbiddenException(resource['url'])
                    elif status == 404:
                        raise exceptions.FileNotFoundException(url)
                    elif status == 407:
                        # This happens if Squid gets mad at you for failing to auth
                        raise ProxyExceptionThatWeNeedToCreate(url)
                    elif status != 200:
                        raise exceptions.FileRetrievalException(url, status)

                    self._validate_download(resource, curl.destination_file)

                    # We should only close the destination file if the caller gave us a path to a
                    # file and not a file object.
                    if isinstance(curl.resource['destination'], basestring):
                        curl.destination_file.close()
                    failed_resources.append(curl.resource)
                    del curl.destination_file
                    del curl.resource
                    multi_curl.remove_handle(curl)
                    free_curls.append(curl)
                # If there aren't any more messages to process, let's break the loop
                if num_queued_messages == 0:
                    break

        # Close the Curls and the MultiCurl, and run the post download hooks
        for curl in multi_curl.handles:
            if hasattr(curl, 'destination_file'):
                curl.destination_file.close()
            curl.close()
        multi_curl.close()
        for hook in self._post_download_hooks:
            hook()

        return downloaded_resources

    def _cleanup_paths(self):
        """
        Calls os.unlink() or os.rmdir on all paths in self._paths_to_cleanup in reverse order, and
        removes them from that list.
        """
        while self._paths_to_cleanup:
            path = self._paths_to_cleanup.pop()
            if os.path.isdir(path):
                os.rmdir(path)
            else:
                os.unlink(path)

    def _configure_curl_proxy_parameters(self, curl):
        """
        Configure the given curl object to use our proxy settings.
        :param curl: The Curl instance we want to configure for proxy support
        :type  curl: pycurl.Curl
        """
        curl.setopt(pycurl.PROXY, str(self.proxy_url))
        curl.setopt(pycurl.PROXYPORT, int(self.proxy_port))
        curl.setopt(pycurl.PROXYTYPE, pycurl.PROXYTYPE_HTTP)
        if self.proxy_user:
            curl.setopt(pycurl.PROXYAUTH, pycurl.HTTPAUTH_BASIC)
            curl.setopt(pycurl.PROXYUSERPWD, '%s:%s'%(str(self.proxy_user),
                                                      str(self.proxy_password)))

    def _configure_curl_ssl_parameters(self, curl, resource):
        """
        Configure our curl for SSL. This method will write the ssl data given in the resource
        dictionary to temporary files, and then will configure the Curl object to use those files
        when retrieving the resource.

        :param curl:     The Curl instance we want to configure for SSL
        :type  curl:     pycurl.Curl
        :param resource: The resource we are configuring this Curl for. It should be a dictionary
                         containing at least one of these keys: 'ssl_ca_cert', 'ssl_client_cert', or
                         'ssl_client_key'.
        :type  resource: dict
        """
        # This will make sure we don't download content from any peer unless their SSL cert checks
        # out against a CA
        # We could make this an option, but it doesn't seem wise.
        curl.setopt(pycurl.SSL_VERIFYPEER, True)
        # Unfortunately, pycurl doesn't accept the bits for SSL keys or certificates, but instead
        # insists on being handed a path. We must use a file to hand the bits to pycurl.
        _ssl_working_path = os.path.join(self.working_path, 'SSL_CERTIFICATES')
        if not os.path.exists(_ssl_working_path):
            os.mkdir(_ssl_working_path, 0700)
            self._paths_to_cleanup.append(_ssl_working_path)

        pycurl_ssl_option_paths = {}
        if hasattr(resource['ssl_ca_cert']) and resource['ssl_ca_cert']:
            pycurl_ssl_option_paths[pycurl.CAINFO] = \
                {'path': os.path.join(_ssl_working_path, '%(u)s-ca.pem'%{'u': resource['url']}),
                 'data': resource['ssl_ca_cert']}
        if hasattr(resource['ssl_client_cert']) and resource['ssl_client_cert']:
            pycurl_ssl_option_paths[pycurl.SSLCERT] = \
                {'path': os.path.join(_ssl_working_path, '%(u)s-cert.pem'%{'u': resource['url']}),
                 'data': resource['ssl_client_cert']}
        if hasattr(resource['ssl_client_key']) and resource['ssl_client_key']:
            pycurl_ssl_option_paths[pycurl.SSLKEY] = \
                {'path': os.path.join(_ssl_working_path,'%(u)s-key.pem'%{'u': resource['url']}),
                 'data': resource['ssl_client_key']}

        for pycurl_setting, ssl_data in pycurl_ssl_option_paths.items():
            # We don't want to do anything if the user didn't pass us any certs or keys
            if ssl_data['data']:
                path = ssl_data['path']
                if os.path.exists(path):
                    os.unlink(path)
                self._paths_to_cleanup.append(path)
                with open(path, 'w') as ssl_file:
                    ssl_file.write(ssl_data['data'])
                curl.setopt(pycurl_setting, str(path))

    # TODO: Support this progress report callback
    def _progress_report(self, dltotal, dlnow, ultotal, ulnow):
        """
        This is the callback that we give to pycurl to report back to us about the download
        progress.

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


class RepoBumper(Bumper):
    """
    A RepoBumper is an Abstract base class that has an interface that is useful for retrieving files
    from a repository. The difference between a RepoBumper and a Bumper lies mostly in the ability
    to process some sort of manifest to provide a list of available resources in the repository, and
    also in the assumption that SSL connection settings will be used consistently for all files that
    need to be retrieved. A RepoBumper will automatically inject these SSL settings into each
    resource that is returned in the manifest.
    """
    def __init__(self, working_path, repo_url, max_speed=None, num_threads=DEFAULT_NUM_THREADS,
                 proxy_url=None, proxy_port=None, proxy_user=None, proxy_password=None,
                 ssl_client_cert=None, ssl_client_key=None, ssl_ca_cert=None):
        """
        Configure the Bumper for the repository specified by repo_url. All parameters except
        working_path and repo_url are optional.

        :param working_path:      The path on the local disk where the downloaded files should be
                                  saved. It is also where SSL certificates and keys will be stored
                                  if they are specified.
        :type  working_path:      basestring
        :param repo_url:          The URL of the repository from which we will download content.
        :type  repo_url:          str
        :param max_speed:         The maximum speed that the download should happen at. This
                                  parameter is currently ignored, but is here for future expansion.
        :type  max_speed:         float
        :param num_threads:       How many threads should be used during download.
        :type  num_threads:       int
        :param proxy_url:         The hostname for a proxy server to use to download content. An
                                  optional http:// is allowed on the beginning of the string, but
                                  will be ignored.
        :type  proxy_url:         str
        :param proxy_port:        The port for the proxy server.
        :type  proxy_port:        int
        :param proxy_user:        The username to use to authenticate to the proxy server.
        :type  proxy_user:        str
        :param proxy_password:    The password to use to authenticate to the proxy server.
        :type  proxy_password:    str
        :param ssl_client_cert:   The ssl cert that should be passed to the repository server when
                                  downloading files.
        :type  ssl_client_cert:   str
        :param ssl_client_key:    The key for the SSL client certificate
        :type  ssl_client_key:    str
        :param ssl_ca_cert:       A certificate authority certificate that we will use to
                                  authenticate the repository.
        :type  ssl_ca_cert:       str
        """
        super(RepoBumper, self).__init__(
            working_path=working_path, max_speed=max_speed, num_threads=num_threads,
            proxy_url=proxy_url, proxy_port=proxy_port, proxy_user=proxy_user,
            proxy_password=proxy_password)

        # It's very important that repo_url end with a trailing slash due to our use of urljoin.
        self.repo_url          = repo_url
        if self.repo_url[-1] != '/':
            self.repo_url = '%s/'%self.repo_url

        self.ssl_client_cert   = ssl_client_cert
        self.ssl_client_key    = ssl_client_key
        self.ssl_ca_cert       = ssl_ca_cert

    def _add_ssl_parameters_to_resource(self, resource):
        """
        This method will add SSL CA certificates, client certificates, and keys to the resource, if
        this RepoBumper was configured with any of those parameters.

        :param resource: The resource that may need SSL information
        :type  resource: dict
        """
        if self.ssl_client_cert:
            resource['ssl_client_cert'] = self.ssl_client_cert
        if self.ssl_client_key:
            resource['ssl_client_key'] = self.ssl_client_key
        if self.ssl_ca_cert:
            resource['ssl_ca_cert'] = self.ssl_ca_cert


class ISOBumper(RepoBumper):
    """
    An ISOBumper is capable of retrieving ISOs from an RPM repository for you, if that repository
    provides the expected PULP_MANIFEST file at the given URL. The Bumper provides a friendly
    manifest interface for you to inspect the available units, and also provides facilities for you
    to specify which units you would like it to retrieve and where you would like it to place them.
    """
    def get_manifest(self):
        """
        This handy property returns an ISOManifest object to you, which has a handy interface for
        inspecting which ISO units are available at the repo URL. The manifest will be a list of
        dictionaries the each specify an ISO, with the following keys:

        name:          The name of the ISO
        checksum:      The checksum for the resource
        checksum_type: The type of the checksum (e.g., sha256)
        size:          The size of the ISO, in bytes
        url:           An absolute URL to the ISO

        These dictionaries are in the format that self._download_resource() expects for its resource
        parameter, isn't that handy?

        :return: A list of dictionaries that describe the available ISOs at the repo_url. They will
                 have the following keys: name, checksum, checksum_type, size, and url.
        :rtype:  dict
        """
        # Let's store the manifest in memory.
        manifest_resource = {'url': urljoin(self.repo_url, ISO_METADATA_FILENAME),
                             'destination': StringIO()}
        self._add_ssl_parameters_to_resource(manifest_resource)
        self.download_resources([manifest_resource])

        # Interpret the manifest as a CSV
        manifest_resource['destination'].seek(0)
        manifest_csv = csv.reader(manifest_resource['destination'])
        manifest = []
        for unit in manifest_csv:
            name, checksum, size = unit
            resource = {'name': name, 'checksum': checksum, 'size': int(size),
                        'url': urljoin(self.repo_url, name),
                        'destination': os.path.join(self.working_path, name)}
            self._add_ssl_parameters_to_resource(resource)
            manifest.append(resource)
        return manifest

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
        # Validate the size, if we know what it should be
        if 'size' in resource:
            # seek to the end to find the file size with tell()
            destination_file.seek(0, 2)
            size = destination_file.tell()
            if size != resource['size']:
                raise DownloadValidationError(_('Downloading <%(name)s> failed validation. '
                    'The manifest specified that the file should be %(expected)s bytes, but '
                    'the downloaded file is %(found)s bytes.')%{'name': resource['name'],
                        'expected': resource['size'], 'found': size})

        # Validate the checksum, if we know what it should be
        if 'checksum' in resource:
            destination_file.seek(0)
            hasher = hashlib.sha256()
            bits = destination_file.read(VALIDATION_CHUNK_SIZE)
            while bits:
                hasher.update(bits)
                bits = destination_file.read(VALIDATION_CHUNK_SIZE)
            # Verify that, son!
            if hasher.hexdigest() != resource['checksum']:
                raise DownloadValidationError(
                    _('Downloading <%(name)s failed checksum validation.')%{
                        'name': resource['name']})
