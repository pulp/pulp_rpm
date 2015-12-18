"""
Logic methods for handling repo bind, unbind, and update operations. This module
is independent of how the requests for these operations are received. In other words,
this module does not care if the required information for these commands is received
through API calls or the message bus. The logic is still the same and occurs
entirely on the consumer.
"""

from logging import getLogger
import os

from pulp.common.constants import DEFAULT_CA_PATH
from pulp.common.lock import Lock
from pulp.common.util import decode_unicode

from pulp_rpm.handlers.repo_file import Repo, RepoFile, MirrorListFile, RepoKeyFiles, CertFiles


log = getLogger(__name__)

LOCK_FILE = '/var/run/subsys/pulp/repolib.pid'


def bind(repo_filename,
         mirror_list_filename,
         keys_root_dir,
         cert_root_dir,
         repo_id,
         repo_name,
         url_list,
         gpg_keys,
         clientcert,
         enabled,
         lock=None,
         verify_ssl=True,
         ca_path=DEFAULT_CA_PATH):
    """
    Uses the given data to safely bind a repo to a repo file. This call will
    determine the best method for representing the repo given the data in the
    repo object as well as the list of URLs where the repo can be found.

    The default lock is defined at the module level and is
    used to ensure that concurrent access to the give files is prevented. Specific
    locks can be passed in for testing purposes to circumvent the default
    location of the lock which requires root access.

    :param repo_filename:        full path to the location of the repo file in which
                                 the repo will be bound; this file does not need to
                                 exist prior to this call
    :type  repo_filename:        string
    :param mirror_list_filename: full path to the location of the mirror list file
                                 that should be written for the given repo if
                                 necessary; this should be unique for the given repo
    :type  mirror_list_filename: string
    :param keys_root_dir:        absolute path to the root directory in which the keys for
                                 all repos will be stored
    :type  keys_root_dir:        string
    :param cert_root_dir:        absolute path to the root directory in which the certs for
                                 all repos will be stored
    :type  cert_root_dir:        string
    :param repo_id:              uniquely identifies the repo being updated
    :type  repo_id:              string
    :param repo_name:            the repo name
    :type  repo_name:            str
    :param url_list:             list of URLs that will be used to access the repo; this call
                                 will determine the best way to represent the URL list in
                                 the repo definition
    :type  url_list:             list of strings
    :param gpg_keys:             mapping of key name to contents for GPG keys to be used when
                                 verifying packages from this repo
    :type  gpg_keys:             dict {string: string}
    :param clientcert:           The client certificate (PEM).
    :type  clientcert:           str
    :param enabled:              Whether or not the repository is set to 'enabled'
    :type  enabled:              bool
    :param lock:                 if the default lock is unacceptble, it may be overridden in this
                                 variable
    :type  lock:                 L{Lock}
    :param verify_ssl:           Whether the repo file should be configured to validate CA trust.
                                 Defaults to True.
    :type  verify_ssl:           bool
    :param ca_path:              Absolute path to a directory that contains trusted CA certificates.
                                 Defaults to pulp.bindings.server.DEFAULT_CA_PATH.
    :type  ca_path:              basestring
    """

    if not lock:
        lock = Lock(LOCK_FILE)

    lock.acquire()
    try:
        log.info('Binding repo [%s]' % repo_id)

        repo_file = RepoFile(repo_filename)
        repo_file.load()

        # In the case of an update, only the changed values will have been sent.
        # Therefore, any of the major data components (repo data, url list, keys)
        # may be None.

        repo = repo_file.get_repo(repo_id)
        if not repo:
            # if no repo name is provided for a new repo, use the id for the name
            repo = Repo(repo_id)
            if repo_name is None:
                repo['name'] = repo_id
            else:
                repo['name'] = repo_name

        repo['enabled'] = str(int(enabled))

        if repo_name:
            repo['name'] = repo_name

        if gpg_keys is not None:
            _handle_gpg_keys(repo, gpg_keys, keys_root_dir)

        _handle_client_cert(repo, cert_root_dir, clientcert)

        if verify_ssl:
            repo['sslverify'] = '1'
            repo['sslcacert'] = ca_path
        else:
            repo['sslverify'] = '0'

        if url_list is not None:
            _handle_host_urls(repo, url_list, mirror_list_filename)

        if repo_file.get_repo(repo.id):
            log.info('Updating existing repo [%s]' % repo.id)
            repo_file.update_repo(repo)
        else:
            log.info('Adding new repo [%s]' % repo.id)
            repo_file.add_repo(repo)

        repo_file.save()
    finally:
        lock.release()


def unbind(repo_filename, mirror_list_filename, keys_root_dir, cert_root_dir, repo_id, lock=None):
    """
    Removes the repo identified by repo_id from the given repo file. If the repo is
    not bound, this call has no effect. If the mirror list file exists, it will be
    deleted.

    The default lock is defined at the module level and is
    used to ensure that concurrent access to the give files is prevented. Specific
    locks can be passed in for testing purposes to circumvent the default
    location of the lock which requires root access.

    @param repo_filename: full path to the location of the repo file in which
                          the repo will be removed; if this file does not exist
                          this call has no effect
    @type  repo_filename: string

    @param mirror_list_filename: full path to the location of the mirror list file
                                 that may exist for the given repo; if the file does
                                 not exist this field will be ignored
    @type  mirror_list_filename: string

    @param keys_root_dir: absolute path to the root directory in which the keys for
                          all repos will be stored
    @type  keys_root_dir: string

    @param cert_root_dir: absolute path to the root directory in which the certs for
                          all repos will be stored
    @type  cert_root_dir: string

    @param repo_id: identifies the repo in the repo file to delete
    @type  repo_id: string

    @param lock: if the default lock is unacceptable, it may be overridden in this variable
    @type  lock: L{Lock}
    """

    if not lock:
        lock = Lock(LOCK_FILE)

    lock.acquire()
    try:
        log.info('Unbinding repo [%s]' % repo_id)

        if not os.path.exists(repo_filename):
            return

        # Repo file changes
        repo_file = RepoFile(repo_filename)
        repo_file.load()
        repo_file.remove_repo_by_name(repo_id)  # will not throw an error if repo doesn't exist
        repo_file.save()

        # Mirror list removal
        if os.path.exists(mirror_list_filename):
            os.remove(mirror_list_filename)

        # Keys removal
        repo_keys = RepoKeyFiles(keys_root_dir, repo_id)
        repo_keys.update_filesystem()

        # cert removal
        certificates = CertFiles(cert_root_dir, repo_id)
        certificates.apply()

    finally:
        lock.release()


def delete_repo_file(repo_filename, lock=None):
    """
    Delete the repo file.

    @param repo_filename: full path to the location of the repo file which
                          will be deleted; if this file does not exist
                          this call has no effect
    @type  repo_filename: string

    @param lock: if the default lock is unacceptable, it may be overridden in this variable
    @type  lock: L{Lock}
    """
    if not lock:
        lock = Lock(LOCK_FILE)

    lock.acquire()
    try:
        repo_file = RepoFile(repo_filename)
        repo_file.delete()
    finally:
        lock.release()


def mirror_list_filename(dir, repo_id):
    """
    Generates the full path to a unique mirror list file for the given repo.

    @param dir: directory in which mirror list files are stored
    @type  dir: string

    @param repo_id: id of the repo the mirror list will belong to
    @type  repo_id: string
    """
    return os.path.join(dir, repo_id + '.mirrorlist')


def _handle_gpg_keys(repo, gpg_keys, keys_root_dir):
    """
    Handles the processing of any GPG keys that were specified with the repo. The key
    files will be written to disk, deleting any existing key files that were there. The
    repo object will be updated with any values related to GPG key information.
    """

    repo_keys = RepoKeyFiles(keys_root_dir, repo.id)

    if gpg_keys is not None and len(gpg_keys) > 0:
        repo['gpgcheck'] = '1'

        for key_name in gpg_keys:
            repo_keys.add_key(key_name, gpg_keys[key_name])

        key_urls = ['file:' + kfn for kfn in repo_keys.key_filenames()]
        repo['gpgkey'] = '\n'.join(key_urls)
    else:
        repo['gpgcheck'] = '0'
        repo['gpgkey'] = None

    # Call this in either case to make sure any existing keys were deleted
    repo_keys.update_filesystem()


def _handle_client_cert(repo, rootdir, clientcert):
    """
    Handle the x.509 client certificate that was specified with the repo.
    The cert file will be written to disk, deleting any existing
    files that were there. The repo object will be updated with the
    sslclientcert setting related to the stored certificates.
    """
    certificates = CertFiles(rootdir, repo.id)
    certificates.update(clientcert)
    clientpath = certificates.apply()
    # client certificate
    if clientcert:
        repo['sslclientcert'] = clientpath


def _handle_host_urls(repo, url_list, mirror_list_filename):
    """
    Handles the processing of the host URLs sent for a repo. If a mirror list file is
    needed, it will be created and saved to disk as part of this call. The repo
    object will be updated with the appropriate parameter for the repo URL.
    """

    if len(url_list) > 1:

        # The mirror list file isn't loaded; if this call was made as part of a
        # repo update the file should be written new given the URLs passed in
        mirror_list_file = MirrorListFile(mirror_list_filename)
        mirror_list_file.add_entries(url_list)
        mirror_list_file.save()

        repo['mirrorlist'] = 'file:' + mirror_list_filename
        repo['baseurl'] = None  # make sure to zero this out in case of an update

        log.info('Created mirrorlist for repo [%s] at [%s]' % (repo.id, mirror_list_filename))
    else:

        # On a repo update, the mirror list may have existed but is no longer used.
        # If we're in this block there shouldn't be a mirror list file for the repo,
        # so delete it if it's there.
        if os.path.exists(mirror_list_filename):
            os.remove(mirror_list_filename)

        repo['baseurl'] = url_list[0]
        repo['mirrorlist'] = None  # make sure to zero this out in case of an update

        log.info(
            'Configuring repo [%s] to use baseurl [%s]' % (decode_unicode(repo.id), url_list[0]))
