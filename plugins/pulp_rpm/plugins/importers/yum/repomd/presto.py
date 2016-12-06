# -*- coding: utf-8 -*-

from pulp.server import util

from pulp_rpm.plugins.db import models

# rhel/centos based distributions use 'prestodelta', suse based distributions use 'deltainfo'
METADATA_FILE_NAMES = ['prestodelta', 'deltainfo']

PACKAGE_TAG = 'newpackage'


def process_package_element(element):
    """
    Process one XML block from prestodelta.xml and return a models.DRPM instance

    :param element: object representing one "DRPM" block from the XML file
    :type  element: xml.etree.ElementTree.Element

    :return:    models.DRPM instance for the XML block
    :rtype:     pulp_rpm.plugins.db.models.DRPM
    """
    delta = element.find('delta')
    filename = delta.find('filename')
    sequence = delta.find('sequence')
    size = delta.find('size')
    checksum = delta.find('checksum')
    checksum_type = util.sanitize_checksum_type(checksum.attrib['type'])

    return models.DRPM(
        new_package=element.attrib['name'],
        epoch=element.attrib['epoch'],
        version=element.attrib['version'],
        release=element.attrib['release'],
        arch=element.attrib['arch'],
        oldepoch=delta.attrib['oldepoch'],
        oldversion=delta.attrib['oldversion'],
        oldrelease=delta.attrib['oldrelease'],
        filename=filename.text,
        sequence=sequence.text,
        size=int(size.text),
        checksum=checksum.text,
        checksumtype=checksum_type)
