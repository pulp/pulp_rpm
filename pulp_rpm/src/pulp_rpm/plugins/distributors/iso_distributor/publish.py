# -*- coding: utf-8 -*-
#
# Copyright © 2012 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

from ConfigParser import SafeConfigParser
from gettext import gettext as _
import csv
import errno
import logging
import os
import shutil
import traceback

from pulp_rpm.common import constants, models
from pulp_rpm.common.progress import PublishProgressReport
from pulp_rpm.repo_auth.protected_repo_utils import ProtectedRepoUtils
from pulp_rpm.repo_auth.repo_cert_utils import RepoCertUtils


logger = logging.getLogger(__name__)


BUILD_DIRNAME = 'build'


def publish(repo, publish_conduit, config):
    """
    Publish an ISO repo.

    :param repo:            The repo you want to publish.
    :type  repo:            pulp.plugins.model.Repository
    :param publish_conduit: The conduit for publishing
    :type  publish_conduit: pulp.plugins.conduits.repo_publish.RepoPublishConduit
    :param config:          plugin configuration
    :type  config:          pulp.plugins.config.PluginConfiguration
    :return:                report describing the publish operation
    :rtype:                 pulp.plugins.model.PublishReport
    """
    progress_report = PublishProgressReport(publish_conduit)
    logger.info(_('Beginning publish for repository <%(repo)s>') % {'repo': repo.id})

    try:
        progress_report.state = progress_report.STATE_IN_PROGRESS
        units = publish_conduit.get_units()

        # Set up an empty build_dir
        build_dir = os.path.join(repo.working_dir, BUILD_DIRNAME)
        # Let's erase the path at build_dir so we can be sure it's a clean directory
        _rmtree_if_exists(build_dir)
        os.makedirs(build_dir)

        _build_metadata(build_dir, units)
        _symlink_units(build_dir, units)

        # Let's unpublish, and then republish
        unpublish(repo)
        _copy_to_hosted_location(repo, config, build_dir)

        # Clean up our build_dir
        _rmtree_if_exists(build_dir)

        # Report that we are done
        progress_report.state = progress_report.STATE_COMPLETE
        return progress_report.build_final_report()
    except Exception, e:
        # Something failed. Let's put an error message on the report
        progress_report.error_message = str(e)
        progress_report.traceback = traceback.format_exc()
        progress_report.state = progress_report.STATE_FAILED
        report = progress_report.build_final_report()
        return report


def unpublish(repo):
    """
    This method ensures that the hosting locations for the given repository over the HTTP and HTTPS
    protocols are empty by removing anything found there, and it also removes repository protection
    for the repo.

    :param repo: The repository that we are unpublishing
    :type  repo: pulp.plugins.model.Repository
    """
    http_dest_dir, https_dest_dir = _get_hosting_locations(repo)
    _rmtree_if_exists(http_dest_dir)
    _rmtree_if_exists(https_dest_dir)
    _remove_repository_protection(repo)


def _build_metadata(build_dir, units):
    """
    Create the manifest file for the given units, and write it to the build directory.

    :param build_dir: A path on the local filesystem where the PULP_MANIFEST should be written. This
                      path should already exist.
    :type  build_dir: basestring
    :param units:     The units to be included in the manifest
    :type  units:     list
    """
    metadata_filename = os.path.join(build_dir, models.ISOManifest.FILENAME)
    with open(metadata_filename, 'w') as metadata:
        metadata_csv = csv.writer(metadata)
        for unit in units:
            metadata_csv.writerow([unit.unit_key['name'], unit.unit_key['checksum'],
                                   unit.unit_key['size']])


def _configure_repository_protection(repo, authorization_ca_cert):
    """
    Configure this repository to be protected by registering it with the repo protection
    application. Repository protection will be performed if if the CONFIG_SSL_AUTH_CA_CERT option is
    set to a certificate. Otherwise, this method removes repository protection.

    :param repo:                  The repository that is being protected
    :type  repo:                  pulp.plugins.model.Repository
    :param authorization_ca_cert: The CA certificate that should be used to protect the repository
                                  Client certificates must be signed by this certificate.
    :type  authorization_ca_cert: basestring
    """
    repo_cert_utils, protected_repo_utils = _get_repository_protection_utils()
    relative_path = _get_relative_path(repo)

    # If we want to include a valid entitlement certificate to hand to consumers, use the key
    # "cert". For now, we only support the "ca" flag for validating the client certificates.
    cert_bundle = {'ca': authorization_ca_cert}

    # This will put the certificates on the filesystem so the repo protection application can
    # use them to validate the consumers' entitlement certificates
    repo_cert_utils.write_consumer_cert_bundle(repo.id, cert_bundle)
    # Add this repository to the protected list. This will tell the repo protection application
    # that it should enforce protection on this relative path
    protected_repo_utils.add_protected_repo(relative_path, repo.id)


def _copy_to_hosted_location(repo, config, build_dir):
    """
    Copy the contents of the build directory to the publishing directories. The config will be used
    to determine whether we are supposed to publish to HTTP and HTTPS.

    :param repo:      The repo you want to publish.
    :type  repo:      pulp.plugins.model.Repository
    :param config:    plugin configuration
    :type  config:    pulp.plugins.config.PluginConfiguration
    :param build_dir: The path on the local filesystem that has the files we wish to copy to the
                      hosted location
    :type  build_dir: basestring
    """
    http_dest_dir, https_dest_dir = _get_hosting_locations(repo)

    # Publish the HTTP portion, if applicable
    serve_http = config.get_boolean(constants.CONFIG_SERVE_HTTP)
    serve_http = serve_http if serve_http is not None else constants.CONFIG_SERVE_HTTP_DEFAULT
    if serve_http:
        shutil.copytree(build_dir, http_dest_dir, symlinks=True)

    # Publish the HTTPs portion, if applicable
    serve_https = config.get_boolean(constants.CONFIG_SERVE_HTTPS)
    serve_https = serve_https if serve_https is not None else constants.CONFIG_SERVE_HTTPS_DEFAULT
    if serve_https:
        authorization_ca_cert = config.get(constants.CONFIG_SSL_AUTH_CA_CERT)
        if authorization_ca_cert:
            _configure_repository_protection(repo, authorization_ca_cert)
        shutil.copytree(build_dir, https_dest_dir, symlinks=True)


def _get_hosting_locations(repo):
    """
    This function generates hosting paths for HTTP and HTTPS, and then returns a 2-tuple containing
    the two paths.

    :param repo: The repo we need hosting locations for
    :type  repo: pulp.plugins.model.Repository
    :return:     2-tuple of (http_dir, https_dir)
    :rtype:      tuple
    """
    http_dest_dir = os.path.join(constants.ISO_HTTP_DIR, repo.id)
    https_dest_dir = os.path.join(constants.ISO_HTTPS_DIR, repo.id)
    return http_dest_dir, https_dest_dir


def _get_relative_path(repo):
    """
    Return the relative path for a particular repository.

    :param repo: The repo we need hosting locations for
    :type  repo: pulp.plugins.model.Repository
    :return:     relative path for the repo
    :rtype:      basestring
    """
    return repo.id


def _get_repository_protection_utils():
    """
    Instantiate our repository protection utilities with the config file.

    :return: A 2-tuple of repo_cert_utils and protected_repo_utils
    :rtype:  tuple
    """
    repo_auth_config = SafeConfigParser()
    repo_auth_config.read(constants.REPO_AUTH_CONFIG_FILE)
    repo_cert_utils = RepoCertUtils(repo_auth_config)
    protected_repo_utils = ProtectedRepoUtils(repo_auth_config)

    return repo_cert_utils, protected_repo_utils


def _remove_repository_protection(repo):
    """
    Remove repository protection from the given repository.

    :param repo: The repository to remove protection from
    :type  repo: pulp.plugins.model.Repository
    """
    protected_repo_utils = _get_repository_protection_utils()[1]
    relative_path = _get_relative_path(repo)
    # Ensure that we aren't protecting this path
    protected_repo_utils.delete_protected_repo(relative_path)


def _symlink_units(build_dir, units):
    """
    For each unit, put a symlink in the build dir that points to its canonical location on disk.

    :param build_dir: The path on the local filesystem that we want to symlink the units into. This
                      path should already exist.
    :type  build_dir: basestring
    :param units:     The units to be symlinked
    :type  units:     list
    """
    for unit in units:
        symlink_filename = os.path.join(build_dir, unit.unit_key['name'])
        if os.path.exists(symlink_filename) or os.path.islink(symlink_filename):
            # There's already something there with the desired symlink filename. Let's try and see
            # if it points at the right thing. If it does, we don't need to do anything. If it does
            # not, we should remove what's there and add the correct symlink.
            try:
                existing_link_path = os.readlink(symlink_filename)
                if existing_link_path == unit.storage_path:
                    # We don't need to do anything more for this unit, so move on to the next one
                    continue
                # The existing symlink is incorrect, so let's remove it
                os.remove(symlink_filename)
            except OSError, e:
                # This will happen if we attempt to call readlink() on a file that wasn't a symlink.
                # We should remove the file and add the symlink. There error code should be EINVAL.
                # If it isn't, something else is wrong and we should raise.
                if e.errno != errno.EINVAL:
                    raise e
                # Remove the file that's at the symlink_filename path
                os.remove(symlink_filename)
        # If we've gotten here, we've removed any existing file at the symlink_filename path, so now
        # we should recreate it.
        os.symlink(unit.storage_path, symlink_filename)


def _rmtree_if_exists(path):
    """
    If the given path exists, remove it recursively. Else, do nothing.

    :param path: The path you want to recursively delete.
    :type  path: basestring
    """
    if os.path.exists(path):
        shutil.rmtree(path)
