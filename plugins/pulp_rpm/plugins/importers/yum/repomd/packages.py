# -*- coding: utf-8 -*-

import logging
import os
import re
from urlparse import urljoin
from xml.etree.cElementTree import iterparse

from nectar.request import DownloadRequest

from pulp_rpm.plugins.importers.yum.repomd import nectar_factory


_LOGGER = logging.getLogger(__name__)

NS_STRIP_RE = re.compile('{.*?}')


def package_list_generator(xml_handle, package_tag, process_func=None):
    """
    Parser for primary.xml file that is implemented as a generator.

    This generator reads enough of the primary.xml file into memory to parse a
    single package's information. It then yields a corresponding package
    information dictionary. Then repeats.

    :param xml_handle:      open file handle pointing to the beginning of a primary.xml file
    :type  xml_handle:      file-like object
    :param process_func:    function that takes one argument, of type
                            xml.etree.ElementTree.Element, or the cElementTree
                            equivalent, and returns a dictionary containing
                            metadata about the unit. Default is to return the
                            Element object.
    :type  process_func:    function

    :return: generator of package information; the object type depends on the processor
    :rtype: generator
    """
    if process_func is None:
        def process_func(x):
            return x
    parser = iterparse(xml_handle, events=('start', 'end'))
    xml_iterator = iter(parser)

    # get a hold of the root element so we can clear it
    # this prevents the entire parsed document from building up in memory
    try:
        root_element = xml_iterator.next()[1]
    # I know. This is a terrible misuse of SyntaxError. Don't blame the messenger.
    except SyntaxError:
        _LOGGER.error('failed to parse XML metadata file')
        raise

    for event, element in xml_iterator:
        # if we're not at a fully parsed package element, keep going
        if event != 'end':
            continue
        # make this work whether the file has namespace as part of the tag or not
        if not (element.tag == package_tag or re.sub(NS_STRIP_RE, '', element.tag) == package_tag):
            continue

        root_element.clear()  # clear all previously parsed ancestors of the root

        package_info = process_func(element)
        yield package_info


# TODO: maybe this class shouldn't be a class
class Packages(object):
    """
    Stateful downloader for a Yum repository's packages.

    Given an iterator of package information dictionaries, download the packages
    to a given destination directory.

    :ivar repo_url: Yum repository's URL
    :ivar packages_information_iterator: iterator of package information dictionaries
    :ivar dst_dir: Directory to store downloaded packages in
    :ivar event_listener: nectar.listener.DownloadEventListener instance
    :ivar downloader: nectar.downloaders.base.Downloader instance
    """

    def __init__(self, repo_url, nectar_config, package_model_iterator, dst_dir,
                 event_listener=None):
        self.repo_url = repo_url
        self.package_model_iterator = package_model_iterator
        self.dst_dir = dst_dir

        self.downloader = nectar_factory.create_downloader(repo_url, nectar_config,
                                                           event_listener)

    def download_packages(self):
        """
        Download the repository's packages to the destination directory.
        """
        self.downloader.download(self._request_generator())

    def _request_generator(self):
        """
        Request generator to convert package information dictionaries to
        download request on demand.

        :return: download request generator
        :rtype: generator
        """
        for model in self.package_model_iterator:
            url = urljoin(self.repo_url, model.download_path)

            file_name = model.relative_path.rsplit('/', 1)[-1]
            destination = os.path.join(self.dst_dir, file_name)

            request = DownloadRequest(url, destination, model)
            yield request
