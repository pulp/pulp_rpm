# -*- coding: utf-8 -*-

from copy import deepcopy
import gdbm
import bz2
import gzip
import hashlib
import logging
import lzma
import os
from urlparse import urljoin
from xml.etree import ElementTree
from xml.etree.cElementTree import iterparse

from nectar.listener import AggregatingEventListener
from nectar.request import DownloadRequest
from pulp.plugins.util import verification

from pulp_rpm.plugins.importers.yum import utils
from pulp_rpm.plugins.importers.yum.parse.rpm import change_location_tag
from pulp_rpm.plugins.importers.yum.repomd import filelists, nectar_factory, other
from pulp_rpm.plugins.importers.yum.repomd.packages import package_list_generator


_LOGGER = logging.getLogger(__name__)

# repomd.xml element tags ------------------------------------------------------

REPOMD_FILE_NAME = 'repomd.xml'
REPOMD_URL_RELATIVE_PATH = 'repodata/%s' % REPOMD_FILE_NAME

SPEC_URL = 'http://linux.duke.edu/metadata/repo'

REVISION_TAG = '{%s}revision' % SPEC_URL

DATA_TAG = '{%s}data' % SPEC_URL

LOCATION_TAG = '{%s}location' % SPEC_URL
CHECKSUM_TAG = '{%s}checksum' % SPEC_URL
SIZE_TAG = '{%s}size' % SPEC_URL
TIMESTAMP_TAG = '{%s}timestamp' % SPEC_URL
OPEN_CHECKSUM_TAG = '{%s}open-checksum' % SPEC_URL
OPEN_SIZE_TAG = '{%s}open-size' % SPEC_URL

# metadata file information skeleton -------------------------------------------

FILE_INFO_SKEL = {'name': None,
                  'relative_path': None,
                  'checksum': {'algorithm': None, 'hex_digest': None},
                  'size': None,
                  'timestamp': None,
                  'open_checksum': {'algorithm': None, 'hex_digest': None},
                  'open_size': None}

# metadata files downloader, parser, and validator -----------------------------


class MetadataFiles(object):
    """
    Stateful downloader, parser, and validator of the metadata files of a Yum
    repository.

    Given a Yum repository URL, this class presents a clean work flow for
    fetching and validating the metadata files of that repo. The workflow is as
    follows:

    1. instantiate MetadataFiles instance with repository URL
    2. call `download_repomd` method
    3. call `parse_repomd` method
    4. call `download_metadata_files` method
    5. optionally call `validate_metadata_files` method

    If all goes well, the instance will have have populated its `metadata` dict
    with `key` -> file path information

    Keys of interest:

     * `primary`: path the primary.xml file containing the metadata of all packages in the
     repository
     * `filelists`: path the filelists.xml file containing the files provided by all of the
     packages in the repository
     * `other`
     * `group`
     * `group_gz`
     * `updateinfo`

    :ivar repo_url: Yum repository URL
    :ivar dst_dir: Directory to store downloaded metadata files in
    :ivar event_listener: nectar.listener.DownloadEventListener instance
    :ivar downloader: nectar.downloaders.base.DownloaderBackend instance
    :ivar revision: revision number of the metadata, set during the `parse_repomd` call
    :ivar metadata: dictionary of the main metadata type keys to the corresponding file paths
    """

    # These are metadata file types listed in "repomd" that we do not want to store as units.
    # deltainfo and susedata are SUSE specific files that we need to ignore for now, as there's no
    # handling yet and copying them creates broken SUSE repos.
    KNOWN_TYPES = set(['group', 'group_gz',
                       'filelists', 'filelists_db',
                       'other', 'other_db',
                       'primary', 'primary_db',
                       'deltainfo', 'susedata',
                       'prestodelta',
                       'updateinfo', 'updateinfo_db'])

    def __init__(self, repo_url, dst_dir, nectar_config):
        """
        :param repo_url:        URL for the base of a yum repository
        :type  repo_url:        basestring
        :param dst_dir:         full path to a destination to which files
                                should be downloaded
        :type  dst_dir:         basestring
        :param nectar_config:   download config for nectar
        :type  nectar_config:   nectar.config.DownloaderConfig
        """
        super(MetadataFiles, self).__init__()
        self.repo_url = repo_url
        self.dst_dir = dst_dir
        self.event_listener = AggregatingEventListener()

        self.downloader = nectar_factory.create_downloader(repo_url, nectar_config,
                                                           self.event_listener)

        self.revision = None
        self.metadata = {}
        self.dbs = {}

    def download_repomd(self):
        """
        Download the main repomd.xml file.
        """
        repomd_dst_path = os.path.join(self.dst_dir, REPOMD_FILE_NAME)
        repomd_url = urljoin(self.repo_url, REPOMD_URL_RELATIVE_PATH)
        repomd_request = DownloadRequest(repomd_url, repomd_dst_path)
        self.downloader.download([repomd_request])
        if self.event_listener.failed_reports:
            error_report = self.event_listener.failed_reports[0]
            raise IOError(error_report.error_msg)

    # TODO (jconnonr 2013-03-07) add a method to validate/verify the repomd.xml file

    def parse_repomd(self):
        """
        Parse the downloaded repomd.xml file and populate the metadata dictionary.
        """
        repomd_file_path = os.path.join(self.dst_dir, REPOMD_FILE_NAME)

        if not os.access(repomd_file_path, os.F_OK | os.R_OK):
            raise RuntimeError('%s has not been downloaded' % REPOMD_FILE_NAME)

        parser = iterparse(repomd_file_path, events=('start', 'end'))
        xml_iterator = iter(parser)

        # get a hold of the root element so that we can clear it
        # this prevents the entire parsed document from building up in memory
        try:
            root_element = xml_iterator.next()[1]
        except SyntaxError:
            raise ValueError('could not parse repo metadata')

        for event, element in xml_iterator:
            if event != 'end':
                continue

            root_element.clear()

            if element.tag == REVISION_TAG:
                self.revision = element.text

            if element.tag == DATA_TAG:
                file_info = process_repomd_data_element(element)
                self.metadata[file_info['name']] = file_info

    def download_metadata_files(self):
        """
        Download the remaining metadata files.
        """
        if not self.metadata:
            raise RuntimeError('%s has not been parsed' % REPOMD_FILE_NAME)

        download_request_list = []

        for file_name, file_info in self.metadata.iteritems():
            # we don't care about the sqlite files
            if file_name.endswith('_db') and file_name in self.KNOWN_TYPES:
                continue
            url = urljoin(self.repo_url, file_info['relative_path'])
            dst = os.path.join(self.dst_dir, file_info['relative_path'].rsplit('/', 1)[-1])

            file_info['local_path'] = dst

            request = DownloadRequest(url, dst)
            download_request_list.append(request)

        self.downloader.download(download_request_list)

    def verify_metadata_files(self):
        """
        Optionally verify the metadata files using both reported size and checksum.
        """
        # TODO: vet this method and determine if it should be used
        for md in self.metadata.values():
            if 'local_path' not in md:
                raise RuntimeError('%s has not been downloaded' % md['relative_path'].rsplit('/', 1)[-1])

            if md['size'] is None:
                raise RuntimeError('%s cannot be verified, no file size' % md['local_path'])

            local_file_size = os.path.getsize(md['local_path'])
            # prevents the rounding errors better than: md['size'] * 1024
            if local_file_size / 1024 != md['size']:
                raise RuntimeError('%s failed verification, file size mismatch' % md['local_path'])

            if md['checksum']['algorithm'] is None:
                raise RuntimeError('%s cannot be verified, no checksum' % md['local_path'])

            hash_constructor = getattr(hashlib, md['checksum']['algorithm'], None)
            if hash_constructor is None:
                raise RuntimeError('%s failed verification, unsupported hash algorithm: %s' % (md['local_path'], md['checksum']['algorithm']))

            hash_obj = hash_constructor()
            with open(md['local_path'], 'rb') as file_handle:
                hash_obj.update(file_handle.read())
            if hash_obj.hexdigest() != md['checksum']['hex_digest']:
                raise RuntimeError('%s failed verification, checksum mismatch' % md['local_path'])

    def get_metadata_file_handle(self, name):
        """
        Given a standard name for a metadata file, as appears in a repomd.xml file
        as a "data" element's "type", return an open file handle in read mode for
        that file.

        :param name:    name of a metadata file as would be found in the
                        repomd.xml file as a "type" attribute of a "data" block.
        :type  name:    basestring

        :return: open file handle to a file containing XML
        :rtype:  file
        """
        try:
            file_path = self.metadata[name]['local_path']
        except KeyError:
            return

        if file_path.endswith('.gz'):
            file_handle = gzip.open(file_path, 'r')
        elif file_path.endswith('.xz'):
            file_handle = lzma.LZMAFile(file_path, 'r')
        elif file_path.endswith('.bz2'):
            file_handle = bz2.BZ2File(file_path, 'r')
        else:
            file_handle = open(file_path, 'r')
        return file_handle

    def get_group_file_handle(self):
        """
        return an open file handle from which the group XML can be read.

        :return:    open file handle to the file containing group XML
        :rtype:     file
        """
        group_file_handle = self.get_metadata_file_handle('group_gz')
        if group_file_handle is None:
            group_file_handle = self.get_metadata_file_handle('group')
        return group_file_handle

    def generate_dbs(self):
        """
        For repo data files that contain data we need to access later for each
        unit in the repo, generate a local db file that gives us quick read
        access to each unit's data.
        """
        for filename, tag, process_func in (
            (filelists.METADATA_FILE_NAME, filelists.PACKAGE_TAG, filelists.process_package_element),
            (other.METADATA_FILE_NAME, other.PACKAGE_TAG, other.process_package_element),
        ):
            xml_file_handle = self.get_metadata_file_handle(filename)
            try:
                generator = package_list_generator(xml_file_handle, tag)
                db_filename = os.path.join(self.dst_dir, '%s.db' % filename)
                # always a New file, and open with Fast writing mode.
                db_file_handle = gdbm.open(db_filename, 'nf')
                try:
                    for element in generator:
                        utils.strip_ns(element)
                        raw_xml = utils.element_to_raw_xml(element)
                        unit_key, _ = process_func(element)
                        db_key = self.generate_db_key(unit_key)
                        db_file_handle[db_key] = raw_xml
                    db_file_handle.sync()
                finally:
                    db_file_handle.close()
            finally:
                xml_file_handle.close()
            self.dbs[filename] = db_filename

    @staticmethod
    def generate_db_key(unit_key):
        """
        :param unit_key:    dictionary of key:value pairs that make a unique
                            entry in the given database.
        :type  unit_key:    dict

        :return:    a string that is a suitable unit key for the database
        :rtype:     basestring
        """
        unit_key = unit_key.copy()
        # clean out these entries if they exist, because they won't be in the
        # XML files we're indexing.
        unit_key.pop('checksum', None)
        unit_key.pop('checksumtype', None)
        sorted_key_names = sorted(unit_key.keys())
        return '::'.join('%s:%s' % (name, unit_key[name]) for name in sorted_key_names)

    def add_repodata(self, model):
        """
        Given a model, add the "repodata" attribute to it (which includes raw
        XML used for publishing), and add the "files" and "changelog" attributes
        based on data obtained in the raw XML snippets.

        :param model:   model instance to manipulate
        :type  model:   pulp_rpm.plugins.db.models.RPM
        """
        repodata = model.metadata.setdefault('repodata',{})
        db_key = self.generate_db_key(model.unit_key)
        for filename, metadata_key, process_func in (
            (filelists.METADATA_FILE_NAME, 'files', filelists.process_package_element),
            (other.METADATA_FILE_NAME, 'changelog', other.process_package_element)
        ):
            try:
                db_file = gdbm.open(self.dbs[filename], 'r')
                raw_xml = db_file[db_key]
            finally:
                db_file.close()
            repodata[filename] = raw_xml
            element = ElementTree.fromstring(raw_xml)
            unit_key, items = process_func(element)
            model.metadata[metadata_key] = items

        raw_xml = model.raw_xml
        repodata['primary'] = change_location_tag(raw_xml, model.relative_path)

# utilities --------------------------------------------------------------------

def process_repomd_data_element(data_element):
    """
    Process the data elements of the repomd.xml file.

    This returns a file information dictionary with the following keys:

     * `name`: name of the element
     * `relative_path`: the path of the metadata file, relative to the repository URL
     * `checksum`: dictionary of `algorithm` and `hex_digest` keys and values
     * `size`: size of the metadata file, in bytes
     * `timestamp`: unix timestamp of the file's creation, as a float
     * `open_checksum`: optional checksum dictionary of uncompressed metadata file
     * `open_size`: optional size of the uncompressed metadata file, in bytes

    :param data_element: XML data element parsed from the repomd.xml file
    :return: file_info dictionary
    :rtype: dict
    """

    file_info = deepcopy(FILE_INFO_SKEL)

    file_info['name'] = data_element.attrib['type']

    location_element = data_element.find(LOCATION_TAG)
    if location_element is not None:
        file_info['relative_path'] = location_element.attrib['href']

    checksum_element = data_element.find(CHECKSUM_TAG)
    if checksum_element is not None:
        checksum_type = verification.sanitize_checksum_type(checksum_element.attrib['type'])
        file_info['checksum']['algorithm'] = checksum_type
        file_info['checksum']['hex_digest'] = checksum_element.text

    size_element = data_element.find(SIZE_TAG)
    if size_element is not None:
        file_info['size'] = int(size_element.text)

    timestamp_element = data_element.find(TIMESTAMP_TAG)
    if timestamp_element is not None:
        file_info['timestamp'] = float(timestamp_element.text)

    open_checksum_element = data_element.find(OPEN_CHECKSUM_TAG)
    if open_checksum_element is not None:
        checksum_type = verification.sanitize_checksum_type(open_checksum_element.attrib['type'])
        file_info['open_checksum']['algorithm'] = checksum_type
        file_info['open_checksum']['hex_digest'] = open_checksum_element.text

    open_size_element = data_element.find(OPEN_SIZE_TAG)
    if open_size_element is not None:
        file_info['open_size'] = int(open_size_element.text)

    for child in data_element.getchildren():
        child.clear()
    data_element.clear()

    return file_info
