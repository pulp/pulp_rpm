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
from gettext import gettext as _
import csv
import logging
import os
import shutil

from pulp_rpm.common import constants
from pulp_rpm.common.publish_progress import PublishProgressReport


logger = logging.getLogger(__name__)


BUILD_DIRNAME = 'build'
PULP_MANIFEST_FILENAME = 'PULP_MANIFEST'


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
    logger.info(_('Beginning publish for repository <%(repo)s>')%{'repo': repo.id})

    try:
        units = publish_conduit.get_units()
        _symlink_units(repo, units)
        # TODO: Remove any symlinks from previous units that are now deleted
        _build_metadata(repo, units)
        _copy_to_hosted_location(repo, config)
        progress_report.update_progress()
        return progress_report.build_final_report()
    except Exception, e:
        # TODO: Revisit this and figure out a better way to communicate specific failure
        progress_report.publish_http = constants.STATE_FAILED
        report = progress_report.build_final_report()
        # TODO: Don't raise here
        raise
        return report


def _build_metadata(repo, units):
    build_dir = _get_build_dir(repo)
    metadata_filename = os.path.join(build_dir, PULP_MANIFEST_FILENAME)
    try:
        metadata = open(metadata_filename, 'w')
        metadata_csv = csv.writer(metadata)
        for unit in units:
            metadata_csv.writerow([unit.unit_key['name'], unit.unit_key['checksum'],
                                   unit.metadata['size']])
    finally:
        # Only try to close metadata if we were able to open it successfully
        if 'metadata' in dir():
            metadata.close()


def _get_build_dir(repo):
    return os.path.join(repo.working_dir, BUILD_DIRNAME, repo.id)


def _copy_to_hosted_location(repo, config):
    build_dir = _get_build_dir(repo)

    http_dest_dir = os.path.join(constants.HTTP_ISO_PUBLISH_DIR, repo.id)
    _rmtree_if_exists(http_dest_dir)
    if config.get_boolean(constants.CONFIG_SERVE_HTTP):
        shutil.copytree(build_dir, http_dest_dir, symlinks=True)

    https_dest_dir = os.path.join(constants.HTTPS_ISO_PUBLISH_DIR, repo.id)
    _rmtree_if_exists(https_dest_dir)
    if config.get_boolean(constants.CONFIG_SERVE_HTTPS):
        shutil.copytree(build_dir, https_dest_dir, symlinks=True)


def _symlink_units(repo, units):
    for unit in units:
        build_dir = _get_build_dir(repo)
        if not os.path.exists(build_dir):
            try:
                os.makedirs(build_dir)
            except OSError, e:
                if e.errno != errno.EEXIST:
                    raise
        symlink_filename = os.path.join(build_dir, unit.unit_key['name'])
        if os.path.exists(symlink_filename):
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
    if os.path.exists(path):
        shutil.rmtree(path)
