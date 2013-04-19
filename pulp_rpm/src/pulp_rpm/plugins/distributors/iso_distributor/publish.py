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

from pulp_rpm.common import constants
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
        units = publish_conduit.get_units()
        _symlink_units(repo, units, progress_report)
        _build_metadata(repo, units, progress_report)
        _copy_to_hosted_location(repo, config, progress_report)
        progress_report.update_progress()
        return progress_report.build_final_report()
    except Exception:
        progress_report.publish_http  = constants.STATE_FAILED
        progress_report.publish_https = constants.STATE_FAILED
        report = progress_report.build_final_report()
        return report


def _build_metadata(repo, units, progress_report):
    """
    Create the manifest file for the given units, and write it to the build directory.

    :param repo:  The repo that we are creating the manifest for
    :type  repo:  pulp.plugins.model.Repository
    :param units: The units to be included in the manifest
    :type  units: list
    :param progress_report: The progress report that should be updated with progress
    :type  progress_report: pulp_rpm.common.publish_progress.PublishProgressReport
    """
    progress_report.manifest_state = constants.STATE_RUNNING
    progress_report.update_progress()

    try:
        build_dir = _get_or_create_build_dir(repo)
        metadata_filename = os.path.join(build_dir, constants.ISO_MANIFEST_FILENAME)
        metadata = open(metadata_filename, 'w')
        metadata_csv = csv.writer(metadata)
        for unit in units:
            metadata_csv.writerow([unit.unit_key['name'], unit.unit_key['checksum'],
                                   unit.unit_key['size']])
        progress_report.manifest_state = constants.STATE_COMPLETE
    except Exception, e:
        progress_report.manifest_state = constants.STATE_FAILED
        progress_report.manifest_error_message = str(e)
        raise
    finally:
        # Only try to close metadata if we were able to open it successfully
        if 'metadata' in dir():
            metadata.close()
        progress_report.update_progress()


def _copy_to_hosted_location(repo, config, progress_report):
    """
    Copy the contents of the build directory to the publishing directories. The config will be used
    to determine whether we are supposed to publish to HTTP and HTTPS.

    :param repo:            The repo you want to publish.
    :type  repo:            pulp.plugins.model.Repository
    :param config:          plugin configuration
    :type  config:          pulp.plugins.config.PluginConfiguration
    :param progress_report: The progress report that should be updated with progress
    :type  progress_report: pulp_rpm.common.publish_progress.PublishProgressReport
    """
    build_dir = _get_or_create_build_dir(repo)

    # Publish the HTTP portion, if applicable
    if config.get_boolean(constants.CONFIG_SERVE_HTTP):
        try:
            progress_report.publish_http = constants.STATE_RUNNING
            progress_report.update_progress()

            http_dest_dir = os.path.join(constants.ISO_HTTP_DIR, repo.id)
            _rmtree_if_exists(http_dest_dir)
            shutil.copytree(build_dir, http_dest_dir, symlinks=True)
            progress_report.publish_http = constants.STATE_COMPLETE
        except Exception:
            progress_report.publish_http = constants.STATE_FAILED
            raise
        finally:
            progress_report.update_progress()

    # Publish the HTTPs portion, if applicable
    if config.get_boolean(constants.CONFIG_SERVE_HTTPS):
        try:
            progress_report.publish_https = constants.STATE_RUNNING
            progress_report.update_progress()

            https_dest_dir = os.path.join(constants.ISO_HTTPS_DIR, repo.id)
            _protect_repository(repo.id, repo, config)
            _rmtree_if_exists(https_dest_dir)
            shutil.copytree(build_dir, https_dest_dir, symlinks=True)
            progress_report.publish_https = constants.STATE_COMPLETE
        except Exception, e:
            progress_report.publish_https = constants.STATE_FAILED
            raise
        finally:
            progress_report.update_progress()


def _protect_repository(relative_path, repo, config):
    """
    Configure this repository to be protected by registering it with the repo protection application. Repository
    protection will only be performed if if the CONFIG_SSL_AUTH_CA_CERT option is set to a certificate.
    Otherwise, this method passes.
    """
    authorization_ca_cert = config.get(constants.CONFIG_SSL_AUTH_CA_CERT)

    # Instantiate our repository protection utilities with the config file
    repo_auth_config = SafeConfigParser()
    repo_auth_config.read(constants.REPO_AUTH_CONFIG_FILE)
    repo_cert_utils = RepoCertUtils(repo_auth_config)
    protected_repo_utils = ProtectedRepoUtils(repo_auth_config)

    if authorization_ca_cert:
        # If we want to include a valid entitlement certificate to hand to consumers, use the key "cert". For
        # now, we only support the "ca" flag for validating the client certificates.
        cert_bundle = {'ca': authorization_ca_cert}

        # This will put the certificates on the filesystem so the repo protection application can use them to
        # validate the consumers' entitlement certificates
        repo_cert_utils.write_consumer_cert_bundle(repo.id, cert_bundle)
        # Add this repository to the protected list. This will tell the repo protection application that it
        # should enforce protection on this relative path
        protected_repo_utils.add_protected_repo(relative_path, repo.id)
    else:
        # Ensure that we aren't protecting this path
        protected_repo_utils.delete_protected_repo(relative_path)


def _get_or_create_build_dir(repo):
    """
    This will generate a path for a build directory for the given repository. If the path doesn't
    exist, it will create it.

    :param repo: The repository you need the build directory for
    :type  repo: pulp.plugins.model.Repository
    :return:     The build path
    :rtype:      basestring
    """
    build_dir = os.path.join(repo.working_dir, BUILD_DIRNAME)
    if not os.path.exists(build_dir):
        try:
            os.makedirs(build_dir)
        except OSError, e:
            # If the path already exists, it's because it was somehow created between us checking if
            # it existed before and creating it. This is OK, so let's only raise if it was a
            # different error.
            if e.errno != errno.EEXIST:
                raise
    return build_dir


def _symlink_units(repo, units, progress_report):
    """
    For each unit, put a symlink in the build dir that points to its canonical location on disk.

    :param repo:  The repo that we are creating the symlinks for
    :type  repo:  pulp.plugins.model.Repository
    :param units: The units to be symlinked
    :type  units: list
    :param progress_report: The progress report that should be updated with progress
    :type  progress_report: pulp_rpm.common.publish_progress.PublishProgressReport
    """
    progress_report.isos_state = constants.STATE_RUNNING
    progress_report.isos_total_count = len(units)
    progress_report.update_progress()

    try:
        build_dir = _get_or_create_build_dir(repo)
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

            # Update the progress report
            progress_report.isos_finished_count += 1
            progress_report.update_progress()
        progress_report.isos_state = constants.STATE_COMPLETE
    except Exception, e:
        progress_report.isos_state = constants.STATE_FAILED
        progress_report.isos_error_message = str(e)
        raise
    finally:
        progress_report.update_progress()


def _rmtree_if_exists(path):
    """
    If the given path exists, remove it recursively. Else, do nothing.

    :param path: The path you want to recursively delete.
    :type  path: basestring
    """
    if os.path.exists(path):
        shutil.rmtree(path)
