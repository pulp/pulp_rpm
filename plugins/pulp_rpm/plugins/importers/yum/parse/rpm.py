from __future__ import absolute_import
import logging
import os
import rpm as rpm_module

import createrepo_c
from pulp.server import util
from pulp.plugins.util import verification
import rpmUtils


CHECKSUM_BY_TYPE = {
    verification.TYPE_MD5: createrepo_c.MD5,
    verification.TYPE_SHA1: createrepo_c.SHA1,
    verification.TYPE_SHA256: createrepo_c.SHA256,
}


_LOGGER = logging.getLogger(__name__)


def get_package_xml(pkg_path, sumtype=util.TYPE_SHA256):
    """
    Method to generate repo xmls - primary, filelists and other
    for a given rpm.

    :param pkg_path: package path on the filesystem
    :type  pkg_path: str

    :param sumtype: The type of checksum to use for creating the package xml
    :type  sumtype: basestring

    :return:    rpm metadata dictionary or empty if rpm path doesnt exist
    :rtype:     dict
    """
    snippet_dict = {}
    try:
        xml_snippets = createrepo_c.xml_from_rpm(pkg_path, checksum_type=CHECKSUM_BY_TYPE[sumtype],
                                                 location_href=os.path.basename(pkg_path))
        snippet_dict = {
            'primary': xml_snippets[0],
            'filelists': xml_snippets[1],
            'other': xml_snippets[2],
        }
    except IOError as e:
        _LOGGER.info(str(e))

    return snippet_dict


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
    end_index = primary_xml_snippet.find("/>", start_index) + 2  # adjust to end of closing tag

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


def package_headers(filename):
    """
    Return package header from rpm/srpm/drpm.

    :param filename: full path to the package to analyze
    :type  filename: str

    :return: package header
    :rtype: rpm.hdr
    """

    # Read the RPM header attributes for use later
    ts = rpm_module.TransactionSet()
    ts.setVSFlags(rpm_module._RPMVSF_NOSIGNATURES)
    fd = os.open(filename, os.O_RDONLY)
    try:
        headers = ts.hdrFromFdno(fd)
        os.close(fd)
    except rpm_module.error:
        # Raised if the headers cannot be read
        os.close(fd)
        raise

    return headers


def package_signature(headers):
    """
    Extract package signature from rpm/srpm/drpm.

    :param headers: package header
    :type  headers: rpm.hdr

    :return: package signature
    :rtype: str
    """

    # this expression looks up at the header that was encrypted whether with RSA or DSA algorithm,
    # then extracts all the possible signature tags, so the signature can be none, signed with a
    # gpg or pgp key.
    # this exact expression is also used in the yum code
    # https://github.com/rpm-software-management/yum/blob/master/rpmUtils/miscutils.py#L105
    signature = headers.sprintf("%|DSAHEADER?{%{DSAHEADER:pgpsig}}:"
                                "{%|RSAHEADER?{%{RSAHEADER:pgpsig}}:{%|SIGGPG?{%{SIGGPG:pgpsig}}:"
                                "{%|SIGPGP?{%{SIGPGP:pgpsig}}:{none}|}|}|}|")
    if signature == "none":
        return None
    # gpg program uses the last 8 characters of the fingerprint
    return signature.split()[-1][-8:]
