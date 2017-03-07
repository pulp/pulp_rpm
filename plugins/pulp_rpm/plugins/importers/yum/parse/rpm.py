from __future__ import absolute_import

import logging
import os
from gettext import gettext as _

import deltarpm
import rpm as rpm_module
import rpmUtils
from createrepo import yumbased
from pulp.server import util
from pulp.server.exceptions import PulpCodedException
from pulp_rpm.common import constants, file_utils
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
    primary_xml_snippet = po.xml_dump_primary_metadata()
    primary_xml_snippet = primary_xml_snippet.decode('utf-8', 'replace')
    primary_xml_snippet = change_location_tag(primary_xml_snippet, pkg_path)
    metadata = {
        'primary': primary_xml_snippet.encode('utf-8'),
        'filelists': po.xml_dump_filelists_metadata(),
        'other': po.xml_dump_other_metadata(),
    }
    return metadata


def change_location_tag(primary_xml_snippet, relpath):
    """
    Transform the <location> tag to strip out leading directories and add `Packages/<first_letter>`.

    :param primary_xml_snippet: snippet of primary xml text for a single package
    :type  primary_xml_snippet: unicode

    :param relpath: Package's 'relativepath'
    :type  relpath: unicode
    """
    start_index = primary_xml_snippet.find("<location ")
    end_index = primary_xml_snippet.find("/>", start_index) + 2  # adjust to end of closing tag

    first_portion = primary_xml_snippet[:start_index]
    end_portion = primary_xml_snippet[end_index:]
    location = """<location href="%s"/>""" % file_utils.make_packages_relative_path(relpath)
    return first_portion + location + end_portion


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


def drpm_package_info(filename):
    """
    Return info about delta rpm package.

    :param filename: full path to the package to analyze
    :type  filename: str

    :return: delta rpm package info
      * "nevr" - nevr of the new package
      * "seq" - seq without old_nevr
      * "old_nevr" - nevr of the old package
    :rtype: dict
    """
    try:
        return deltarpm.readDeltaRPM(filename)
    except SystemError:  # does silly exception reporting (print) => missing from tests
        msg = _('failed to load DRPM metadata on file %s error') % filename
        _LOGGER.exception(msg)
        raise


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


def filter_signature(unit, config):
    """
    Filter package based on GPG signature and allowed GPG key IDs

    :param unit: model instance of the package
    :type  unit: pulp_rpm.plugins.db.models.RPM/DRPM/SRPM

    :param config: configuration instance passed to the importer
    :type  config: pulp.plugins.config.PluginCallConfiguration

    :raise: PulpCodedException if the package signing key ID does not exist or is not allowed
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


def nevra(name):
    """Parse NEVRA.

    inspired by:
    https://github.com/rpm-software-management/hawkey/blob/d61bf52871fcc8e41c92921c8cd92abaa4dfaed5/src/util.c#L157. # NOQA
    We don't use hawkey because it is not available on all platforms we support.

    :param name: NEVRA (jay-3:3.10-4.fc3.x86_64)
    :type  name: str

    :return: parsed NEVRA (name, epoch, version, release, architecture)
                           str    int     str      str         str
    :rtype: tuple
    """
    if name.count(".") < 1:
        msg = _("failed to parse nevra '%s' not a valid nevra") % name
        _LOGGER.exception(msg)
        raise ValueError(msg)

    arch_dot_pos = name.rfind(".")
    arch = name[arch_dot_pos + 1:]

    return nevr(name[:arch_dot_pos]) + (arch, )


def nevra_to_nevr(name, epoch, version, release, architecture):
    """Convert nevra tuple to nevr.

    :param name: name
    :type  name: str

    :param epoch: epoch
    :type  epoch: int

    :param version: version
    :type  version: str

    :param release: release
    :type  release: str

    :param architecture: architecture
    :type  architecture: str

    :return: NEVR (name, epoch, version, release)
                   str    int     str      str
    :rtype: tuple
    """
    return name, epoch, version, release


def nevr(name):
    """
    Parse NEVR.

    inspired by:
    https://github.com/rpm-software-management/hawkey/blob/d61bf52871fcc8e41c92921c8cd92abaa4dfaed5/src/util.c#L157. # NOQA

    :param name: NEVR "jay-test-3:3.10-4.fc3"
    :type  name: str

    :return: parsed NEVR (name, epoch, version, release)
                          str    int     str      str
    :rtype: tuple
    """
    if name.count("-") < 2:  # release or name is missing
        msg = _("failed to parse nevr '%s' not a valid nevr") % name
        _LOGGER.exception(msg)
        raise ValueError(msg)

    release_dash_pos = name.rfind("-")
    release = name[release_dash_pos + 1:]
    name_epoch_version = name[:release_dash_pos]
    name_dash_pos = name_epoch_version.rfind("-")
    package_name = name_epoch_version[:name_dash_pos]

    epoch_version = name_epoch_version[name_dash_pos + 1:].split(":")
    if len(epoch_version) == 1:
        epoch = 0
        version = epoch_version[0]
    elif len(epoch_version) == 2:
        epoch = int(epoch_version[0])
        version = epoch_version[1]
    else:
        # more than one ':'
        msg = _("failed to parse nevr '%s' not a valid nevr") % name
        _LOGGER.exception(msg)
        raise ValueError(msg)

    return package_name, epoch, version, release


def nevr_to_evr(name, epoch, version, release):
    """Convert nevra tuple to nevr.

    :param name: name
    :type  name: str

    :param epoch: epoch
    :type  epoch: int

    :param version: version
    :type  version: str

    :param release: release
    :type  release: str


    :return: EVR (epoch, version, release)
                   int     str      str
    :rtype: tuple
    """
    return epoch, version, release


def evr_to_str(epoch, version, release):
    """Get EVR epoch:version-relese from tuple nevr.

    :param epoch: epoch
    :type  epoch: int

    :param version: version
    :type  version: str

    :param release: release
    :type  release: str

    :return: EVR "3:3.10-4.fc3"
    :rtype: str
    """
    if epoch == 0:
        return "%s-%s" % (version, release)
    else:
        return "%s:%s-%s" % (epoch, version, release)
