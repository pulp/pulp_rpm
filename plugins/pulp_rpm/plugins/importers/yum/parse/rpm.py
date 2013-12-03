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

import logging
import os

from createrepo import yumbased
import rpmUtils
from pulp.plugins.util import verification

_LOGGER = logging.getLogger(__name__)

# TODO: OMG so sorry, we should replace this at the earliest opportunity. This
# uses createrepo and yum to generate some of the repo metadata


def get_package_xml(pkg_path, sumtype=verification.TYPE_SHA256):
    """
    Method to generate repo xmls - primary, filelists and other
    for a given rpm.

    :param pkg_path: rpm package path on the filesystem
    :type  pkg_path: str

    :param sumtype: The type of checksum to use for creating the package xml
    :type  sumtype: str

    :return:    rpm metadata dictionary or empty if rpm path doesnt exist
    :rtype:     dict
    """
    ts = rpmUtils.transaction.initReadOnlyTransaction()
    try:
        po = yumbased.CreateRepoPackage(ts, pkg_path, sumtype=sumtype)
    except Exception, e:
        # I hate this, but yum doesn't use reasonable exceptions like IOError
        # and ValueError.
        _LOGGER.error(str(e))
        return {}
    # RHEL6 createrepo throws a ValueError if _cachedir is not set
    po._cachedir = None
    primary_xml_snippet = change_location_tag(po.xml_dump_primary_metadata(), pkg_path)
    metadata = {
        'primary' : primary_xml_snippet,
        'filelists': po.xml_dump_filelists_metadata(),
        'other'   : po.xml_dump_other_metadata(),
    }
    return metadata


def change_location_tag(primary_xml_snippet, relpath):
    """
    Transform the <location> tag to strip out leading directories so it
    puts all rpms in same the directory as 'repodata'

    :param primary_xml_snippet: snippet of primary xml text for a single package
    :type  primary_xml_snippet: str

    :param relpath: Package's 'relativepath'
    :type  relpath: str
    """

    basename = os.path.basename(relpath)
    start_index = primary_xml_snippet.find("<location ")
    end_index = primary_xml_snippet.find("/>", start_index) + 2 # adjust to end of closing tag

    first_portion = string_to_unicode(primary_xml_snippet[:start_index])
    end_portion = string_to_unicode(primary_xml_snippet[end_index:])
    location = string_to_unicode("""<location href="%s"/>""" % (basename))
    return first_portion + location + end_portion


ENCODING_LIST = ('utf8', 'iso-8859-1')


def string_to_unicode(data):
    """
    Make a best effort to decode a string, trying encodings in a sensible order
    based on unscientific expectations of each one's probability of use.
    ISO 8859-1 (aka latin1) will never fail, so this will always return some
    unicode object. Lack of decoding error does not mean decoding was correct
    though.

    :param data:        string to decode
    :type  data:        str

    :return: data as a unicode object
    :rtype:  unicode
    """
    for code in ENCODING_LIST:
        try:
            return data.decode(code)
        except UnicodeError:
            # try others
            continue
