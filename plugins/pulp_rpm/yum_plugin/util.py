import hashlib
import shutil
import traceback
import urlparse
import time
import uuid
import os
import logging
import gettext

import yum
import rpmUtils
from M2Crypto import X509

_ = gettext.gettext

LOG_PREFIX_NAME="pulp.plugins"
def getLogger(name):
    log_name = LOG_PREFIX_NAME + "." + name
    return logging.getLogger(log_name)
_LOG = getLogger(__name__)


def get_repomd_filetypes(repomd_path):
    """
    @param repomd_path: path to repomd.xml
    @return: List of available metadata types
    """
    rmd = yum.repoMDObject.RepoMD("temp_pulp", repomd_path)
    if rmd:
        return rmd.fileTypes()


def get_repomd_filetype_path(path, filetype):
    """
    @param path: path to repomd.xml
    @param filetype: metadata type to query, example "group", "primary", etc
    @return: Path for filetype, or None
    """
    rmd = yum.repoMDObject.RepoMD("temp_pulp", path)
    if rmd:
        try:
            data = rmd.getData(filetype)
            return data.location[1]
        except:
            return None
    return None


def is_valid_checksum_type(checksum_type):
    """
    @param checksum_type: checksum type to validate
    @type checksum_type str
    @return: True if valid, else False
    @rtype bool
    """
    VALID_TYPES = ['sha256', 'sha', 'sha1', 'md5', 'sha512']
    if checksum_type not in VALID_TYPES:
        return False
    return True


def validate_cert(cert_pem):
    """
    @param cert_pem: certificate pem to verify
    @type cert_pem str
    @return: True if valid, else False
    @rtype bool
    """
    try:
        cert = X509.load_cert_string(cert_pem)
    except X509.X509Error:
        return False
    return True


def get_relpath_from_unit(unit):
    """
    @param unit
    @type AssociatedUnit

    @return relative path
    @rtype str
    """
    if "filename" in unit.metadata:
        relpath = unit.metadata["filename"]
    elif "fileName" in unit.unit_key:
        relpath = unit.unit_key["fileName"]
    elif "filename" in unit.unit_key:
        relpath = unit.unit_key["filename"]
    else:
        relpath = os.path.basename(unit.storage_path)
    return relpath


def is_rpm_newer(a, b):
    """
    @var a: represents rpm metadata
    @type a: dict with keywords: name, arch, epoch, version, release

    @var b: represents rpm metadata
    @type b: dict with keywords: name, arch, epoch, version, release

    @return true if RPM is a newer, false if it's not
    @rtype: bool
    """
    if a["name"] != b["name"]:
        return False
    if a["arch"] != b["arch"]:
        return False
    value = rpmUtils.miscutils.compareEVR(
            (a["epoch"], a["version"], a["release"]),
            (b["epoch"], b["version"], b["release"]))
    if value > 0:
        return True
    return False


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


LISTING_FILE_NAME = 'listing'


def generate_listing_files(root_publish_dir, repo_publish_dir):
    """
    (Re) Generate listing files along the path from the repo publish dir to the
    root publish dir.

    :param root_publish_dir: root directory
    :type  root_publish_dir: str
    :param repo_publish_dir: the repository's publish directory, as a descendant of the root directory
    :type  repo_publish_dir: str
    """
    # normalize the paths for use with os.path.dirname by removing any trailing '/'s
    root_publish_dir = root_publish_dir.rstrip('/')
    repo_publish_dir = repo_publish_dir.rstrip('/')

    # the repo_publish_dir *must* be a descendant of the root_publish_dir
    if not repo_publish_dir.startswith(root_publish_dir):
        raise ValueError('repository publish directory must be a descendant of the root publish directory')

    # this is a weird case that handles a distinct difference between actual
    # Pulp behavior and the way unit tests against publish have been written
    if root_publish_dir == repo_publish_dir:
        working_dir = repo_publish_dir
    else:
        # start at the parent of the repo publish dir and work up to the publish dir
        working_dir = os.path.dirname(repo_publish_dir)

    while True:
        listing_file_path = os.path.join(working_dir, LISTING_FILE_NAME)
        tmp_file_path = os.path.join(working_dir, '.%s' % uuid.uuid4())

        directories = [d for d in os.listdir(working_dir) if os.path.isdir(os.path.join(working_dir, d))]
        directories.sort()

        # write the new listing file
        with open(tmp_file_path, 'w') as listing_handle:
            listing_handle.write('\n'.join(directories))

        # move it into place, over-writing any pre-existing listing file
        shutil.move(tmp_file_path, listing_file_path)

        if working_dir == root_publish_dir:
            break

        # work up the directory structure
        working_dir = os.path.dirname(working_dir)
