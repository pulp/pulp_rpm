# -*- coding: utf-8 -*-
#
# Copyright (c) 2013 Red Hat, Inc.
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
import os
import shutil

from iso_distributor import export_utils
from pulp.plugins.conduits.repo_publish import RepoPublishConduit
from pulp.plugins.distributor import GroupDistributor
from pulp.server.exceptions import PulpDataException
from pulp_rpm.common import ids, constants
from pulp_rpm.yum_plugin import util

_LOG = util.getLogger(__name__)


class GroupISODistributor(GroupDistributor):

    def __init__(self):
        super(GroupISODistributor, self).__init__()
        self.cancelled = False
        self.summary = {}
        self.details = {}

    @classmethod
    def metadata(cls):
        return {
            'id': ids.TYPE_ID_DISTRIBUTOR_GROUP_EXPORT,
            'display_name': _('Group Export Distributor'),
            'types': [ids.TYPE_ID_RPM, ids.TYPE_ID_SRPM, ids.TYPE_ID_DRPM, ids.TYPE_ID_ERRATA,
                      ids.TYPE_ID_DISTRO, ids.TYPE_ID_PKG_CATEGORY, ids.TYPE_ID_PKG_GROUP]
        }

    def validate_config(self, repo_group, config, related_repo_groups):
        return export_utils.validate_export_config(config)

    def publish_group(self, repo_group, publish_conduit, config):
        """
        Publishes the given repository group.

        :param repo_group: metadata describing the repository group
        :type  repo_group: pulp.plugins.model.RepositoryGroup
        :param publish_conduit: provides access to relevant Pulp functionality
        :type  publish_conduit: pulp.plugins.conduits.repo_publish.RepoGroupPublishConduit
        :param config: plugin configuration
        :type  config: pulp.plugins.config.PluginConfiguration
        :return: report describing the publish run
        :rtype:  pulp.plugins.model.PublishReport
        """
        # First, validate the configuration because there may be override config options, and currently,
        # validate_config is not called prior to publishing by the manager.
        valid_config, msg = export_utils.validate_export_config(config)
        if not valid_config:
            raise PulpDataException(msg)

        _LOG.info('Beginning repository group export')
        progress_status = export_utils.init_progress_report(len(repo_group.repo_ids))

        def progress_callback(type_id, status):
            progress_status[type_id] = status
            publish_conduit.set_progress(progress_status)

        # Before starting, clean out the working directory. Done to remove last published ISOs
        shutil.rmtree(repo_group.working_dir, ignore_errors=True)
        os.makedirs(repo_group.working_dir)

        # Retrieve the configuration for each repository, the skip types, and the date filter
        packed_config = export_utils.retrieve_group_export_config(repo_group, config)
        rpm_repositories, self.date_filter = packed_config

        # For every repository, extract the requested types to the working directory
        for repo_id, working_dir in rpm_repositories:
            # Create a repo conduit, which makes sharing code with the export and yum distributors easier
            repo_conduit = RepoPublishConduit(repo_id, ids.EXPORT_GROUP_DISTRIBUTOR_ID)

            # If there is a date filter perform an incremental export, otherwise do everything
            if self.date_filter:
                result = export_utils.export_incremental_content(working_dir, repo_conduit,
                                                                 self.date_filter)
            else:
                result = export_utils.export_complete_repo(repo_id, working_dir, repo_conduit, config,
                                                           progress_callback)
            self.summary[repo_id] = result[0]
            self.details[repo_id] = result[1]

        # If there was no export directory, publish via ISOs
        if not config.get(constants.EXPORT_DIRECTORY_KEYWORD):
            self._publish_isos(repo_group, config, progress_callback)

        for repo_id, repo_dir in rpm_repositories:
            if repo_id in self.details and len(self.details[repo_id]['errors']) != 0:
                return publish_conduit.build_failure_report(self.summary, self.details)

        self.summary['repositories_exported'] = len(rpm_repositories)
        self.summary['repositories_skipped'] = len(repo_group.repo_ids) - len(rpm_repositories)

        return publish_conduit.build_success_report(self.summary, self.details)

    def _publish_isos(self, repo_group, config, progress_callback=None):
        """
        This just decides what the http and https publishing directories should be, cleans them up,
        and then calls publish_isos method in export_utils

        :param repo_group: metadata describing the repository group. Used to retrieve the working
                directory and group id.
        :type  repo_group: pulp.plugins.model.RepositoryGroup
        :param config: plugin configuration instance; the proposed repo configuration is found within
        :type config: pulp.plugins.config.PluginCallConfiguration
        :param progress_callback: callback to report progress info to publish_conduit
        :type progress_callback: function
        """

        http_publish_dir = os.path.join(constants.GROUP_EXPORT_HTTP_DIR, repo_group.id).rstrip('/')
        https_publish_dir = os.path.join(constants.GROUP_EXPORT_HTTPS_DIR, repo_group.id).rstrip('/')
        image_prefix = config.get(constants.ISO_PREFIX_KEYWORD) or repo_group.id

        # Clean up the old export publish directories.
        shutil.rmtree(http_publish_dir, ignore_errors=True)
        shutil.rmtree(https_publish_dir, ignore_errors=True)

        # If publishing isn't enabled for http or https, set the path to None
        if not config.get(constants.PUBLISH_HTTP_KEYWORD):
            http_publish_dir = None
        if not config.get(constants.PUBLISH_HTTPS_KEYWORD):
            https_publish_dir = None

        export_utils.publish_isos(repo_group.working_dir, image_prefix, http_publish_dir,
                                  https_publish_dir, config.get(constants.ISO_SIZE_KEYWORD),
                                  progress_callback)