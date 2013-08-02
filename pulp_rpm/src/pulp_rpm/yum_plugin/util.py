# -*- coding: utf-8 -*-
#
# Copyright © 2011 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.
import commands
import hashlib
import shutil
import traceback
import urlparse
import yum
import time
import os
import logging
import gettext
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

def get_repomd_filetype_dump(repomd_path):
    """
    @param repomd_path: path to repomd.xml
    @return: dump of metadata information
    """
    rmd = yum.repoMDObject.RepoMD("temp_pulp", repomd_path)
    ft_data = {}
    if rmd:
        for ft in rmd.fileTypes():
            ft_obj = rmd.repoData[ft]
            try:
                size = ft_obj.size
            except:
                # RHEL5 doesnt have this field
                size = None
            ft_data[ft_obj.type] = {'location'  : ft_obj.location[1],
                                    'timestamp' : ft_obj.timestamp,
                                    'size'      : size,
                                    'checksum'  : ft_obj.checksum,
                                    'dbversion' : ft_obj.dbversion}
    return ft_data


def _get_yum_repomd(path, temp_path=None):
    """
    @param path: path to repo
    @param temp_path: optional parameter to specify temporary path
    @return yum.yumRepo.YumRepository object initialized for querying repodata
    """
    if not temp_path:
        temp_path = "/tmp/temp_repo-%s" % (time.time())
    r = yum.yumRepo.YumRepository(temp_path)
    try:
        r.baseurl = "file://%s" % (path.encode("ascii", "ignore"))
    except UnicodeDecodeError:
        r.baseurl = "file://%s" % (path)
    try:
        r.basecachedir = path.encode("ascii", "ignore")
    except UnicodeDecodeError:
        r.basecachedir = path
    r.baseurlSetup()
    return r

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

def validate_feed(feed_url):
    """
    @param feed_url: feed url to validate
    @type feed_url str
    @return: True if valid, else False
    @rtype bool
    """
    proto, netloc, path, params, query, frag = urlparse.urlparse(feed_url)
    if proto not in ['http', 'https', 'ftp', 'file']:
        return False
    return True

def get_file_checksum(filename=None, fd=None, file=None, buffer_size=None, hashtype="sha256"):
    """
    Compute a file's checksum.
    """
    if hashtype in ['sha', 'SHA']:
        hashtype = 'sha1'

    if buffer_size is None:
        buffer_size = 65536

    if filename is None and fd is None and file is None:
        raise Exception("no file specified")
    if file:
        f = file
    elif fd is not None:
        f = os.fdopen(os.dup(fd), "r")
    else:
        f = open(filename, "r")
    # Rewind it
    f.seek(0, 0)
    m = hashlib.new(hashtype)
    while 1:
        buffer = f.read(buffer_size)
        if not buffer:
            break
        m.update(buffer)

    # cleanup time
    if file is not None:
        file.seek(0, 0)
    else:
        f.close()
    return m.hexdigest()

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

def verify_exists(file_path, checksum=None, checksum_type="sha256", size=None, verify_options={}):
    """
    Verify if the rpm existence; checks include
     - exists on the filesystem
     - size match
     - checksums match

    @param file_path rpm file path on filesystem
    @type missing_rpms str

    @param checksum checksum value of the rpm
    @type checksum str

    @param checksum_type type used to calculate checksum
    @type checksum_type str

    @param size size of the file
    @type size int

    @param verify_options dict of checksum of size verify options
    @type size dict

    @return True if all checks pass; else False
    @rtype bool
    """
    _LOG.debug("Verify path [%s] exists" % file_path)
    if not os.path.exists(file_path):
        # file path not found
        return False
    verify_size = verify_options.get("size") or False
    # compute the size
    if verify_size and size is not None:
        f_stat = os.stat(file_path)
        if int(size) and f_stat.st_size != int(size):
            cleanup_file(file_path)
            return False
    verify_checksum = verify_options.get("checksum") or False
    # compute checksum
    if verify_checksum and checksum is not None:
        computed_checksum = get_file_checksum(filename=file_path, hashtype=checksum_type)
        if computed_checksum != checksum:
            cleanup_file(file_path)
            return False
    return True

def cleanup_file(file_path):
    try:
        os.remove(file_path)
    except (OSError, IOError), e:
        _LOG.info("Error [%s] trying to clean up file path [%s]" % (e, file_path))

def create_symlink(source_path, symlink_path):
    """
    @param source_path source path
    @type source_path str

    @param symlink_path path of where we want the symlink to reside
    @type symlink_path str

    @return True on success, False on error
    @rtype bool
    """
    if symlink_path.endswith("/"):
        symlink_path = symlink_path[:-1]
    if os.path.lexists(symlink_path):
        if not os.path.islink(symlink_path):
            _LOG.error("%s is not a symbolic link as expected." % (symlink_path))
            return False
        existing_link_target = os.readlink(symlink_path)
        if existing_link_target == source_path:
            return True
        _LOG.warning("Removing <%s> since it was pointing to <%s> and not <%s>"\
        % (symlink_path, existing_link_target, source_path))
        os.unlink(symlink_path)
        # Account for when the relativepath consists of subdirectories
    if not create_dirs(os.path.dirname(symlink_path)):
        return False
    _LOG.debug("creating symlink %s pointing to %s" % (symlink_path, source_path))
    os.symlink(source_path, symlink_path)
    return True


def create_copy(source_path, target_path):
    """
    @param source_path source path
    @type source_path str

    @param target_path path of where we want the copy the file
    @type target_path str

    @return True on success, False on error
    @rtype bool
    """
    if not os.path.isdir(os.path.dirname(target_path)):
        os.makedirs(os.path.dirname(target_path))
    if os.path.isfile(source_path):
        _LOG.debug("Copying file from source %s to target path %s" % (source_path, target_path))
        shutil.copy(source_path, target_path)
        return True
    if os.path.isdir(source_path):
        _LOG.debug("Copying directory from source %s to target path %s" % (source_path, target_path))
        shutil.copytree(source_path, target_path)
        return True
    return False


def create_dirs(target):
    """
    @param target path
    @type target str

    @return True - success, False - error
    @rtype bool
    """
    try:
        os.makedirs(target)
    except OSError, e:
        # Another thread may have created the dir since we checked,
        # if that's the case we'll see errno=17, so ignore that exception
        if e.errno != 17:
            _LOG.error("Unable to create directories for: %s" % (target))
            tb_info = traceback.format_exc()
            _LOG.error("%s" % (tb_info))
            return False
    return True

def get_relpath_from_unit(unit):
    """
    @param unit
    @type AssociatedUnit

    @return relative path
    @rtype str
    """
    filename = ""
    if unit.metadata.has_key("relativepath"):
        relpath = unit.metadata["relativepath"]
    elif unit.metadata.has_key("filename"):
        relpath = unit.metadata["filename"]
    elif unit.unit_key.has_key("fileName"):
        relpath = unit.unit_key["fileName"]
    elif unit.unit_key.has_key("filename"):
        relpath = unit.unit_key["filename"]
    else:
        relpath = os.path.basename(unit.storage_path)
    return relpath


def remove_repo_publish_dir(publish_dir, repo_publish_dir):
    """
    Remove the published symbolic link and as much of the relative path that is
    not shared with other published repositories.

    :param publish_dir: root directory for published repositories
    :type  publish_dir: str
    :param repo_publish_dir: full path of the repository's published directory
                             (must be a descendant of the publish directory)
    :type  repo_publish_dir: str
    """

    # normalize for use with os.path.dirname
    publish_dir = publish_dir.rstrip('/')
    repo_publish_dir = repo_publish_dir.rstrip('/')

    if not os.path.exists(repo_publish_dir):
        raise ValueError('repository publish directory must exist')

    # the repository publish dir must be a descendant of the publish dir
    if not repo_publish_dir.startswith(publish_dir):
        raise ValueError('repository publish directory must be a descendant of the publish directory')

    # the full path should point to a symbolic link
    if not os.path.islink(repo_publish_dir):
        raise ValueError('repository publish directory must be a symbolic link')

    os.unlink(repo_publish_dir)

    working_dir = os.path.dirname(repo_publish_dir)

    while working_dir != publish_dir:

        files = os.listdir(working_dir)

        if files and files != [LISTING_FILE_NAME]:
            break

        # directory is empty or only contains a listing file, so remove it
        shutil.rmtree(working_dir)
        working_dir = os.path.dirname(working_dir)

    # regenerate the listing file in the last directory
    generate_listing_files(working_dir, working_dir)


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

        # remove any existing listing file before generating a new one
        if os.path.exists(listing_file_path):
            os.unlink(listing_file_path)

        directories = [d for d in os.listdir(working_dir) if os.path.isdir(os.path.join(working_dir, d))]

        # write the new listing file
        with open(listing_file_path, 'w') as listing_handle:
            listing_handle.write('\n'.join(directories))

        if working_dir == root_publish_dir:
            break

        # work up the directory structure
        working_dir = os.path.dirname(working_dir)

