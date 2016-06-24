from __future__ import absolute_import
import logging
import os
import rpm as rpm_module

from createrepo import yumbased
from pulp.server import util
import rpmUtils
from pulp.server.exceptions import PulpCodedException
from pulp_rpm.common import constants
from pulp_rpm.plugins import error_codes


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
    ts = rpmUtils.transaction.initReadOnlyTransaction()
    try:
        # createrepo raises an exception if sumtype is unicode
        # https://bugzilla.redhat.com/show_bug.cgi?id=1290021
        sumtype_as_str = str(sumtype)
        po = yumbased.CreateRepoPackage(ts, pkg_path, sumtype=sumtype_as_str)
    except Exception, e:
        # I hate this, but yum doesn't use reasonable exceptions like IOError
        # and ValueError.
        _LOGGER.error(str(e))
        return {}
    # RHEL6 createrepo throws a ValueError if _cachedir is not set
    po._cachedir = None
    primary_xml_snippet = change_location_tag(po.xml_dump_primary_metadata(), pkg_path)
    metadata = {
        'primary': primary_xml_snippet,
        'filelists': po.xml_dump_filelists_metadata(),
        'other': po.xml_dump_other_metadata(),
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

    :return: short key id the package was signed with
             (short key id is the 8 character abbreviated fingerprint)
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


def signature_enabled(config):
    """
    Check if the signature policy is enabled.

    :param config: configuration instance passed to the importer
    :type  config: pulp.plugins.config.PluginCallConfiguration

    :return: true if enabled, false otherwise
    :rtype: boolean
    """

    require_signature = config.get(constants.CONFIG_REQUIRE_SIGNATURE, False)
    allowed_keys = config.get(constants.CONFIG_ALLOWED_KEYS)
    if require_signature or allowed_keys:
        return True
    return False


def verify_signature(unit, config):
    """
    Verify package signature.

    :param unit: model instance of the package
    :type  unit: pulp_rpm.plugins.db.models.RPM/DRPM/SRPM

    :param config: configuration instance passed to the importer
    :type  config: pulp.plugins.config.PluginCallConfiguration

    :raise: PulpCodedException if the signature check did not pass
    """

    signing_key = unit.signing_key
    require_signature = config.get(constants.CONFIG_REQUIRE_SIGNATURE, False)
    allowed_keys = config.get(constants.CONFIG_ALLOWED_KEYS, [])
    if require_signature and not signing_key:
        raise PulpCodedException(error_code=error_codes.RPM1013, package=unit.filename)
    if allowed_keys:
        allowed_keys = [key.lower() for key in allowed_keys]
        if signing_key and signing_key not in allowed_keys:
                raise PulpCodedException(error_code=error_codes.RPM1014, key=signing_key,
                                         package=unit.filename, allowed=allowed_keys)
