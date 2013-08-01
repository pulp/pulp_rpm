# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

import os
import shutil

from pulp.plugins.distributor import Distributor
from pulp.server.exceptions import PulpDataException

# Import export_utils from this directory, which is not in the python path
import export_utils
from pulp_rpm.common import constants, models, ids
from pulp_rpm.yum_plugin import util, metadata

_logger = util.getLogger(__name__)

# Things left to do:
#   Cancelling a publish operation is not currently supported
#   Published ISOs are left in the working directory. See export_utils.publish_isos to fix this.
#   This is not currently in the python path. When that gets fixed, the imports should be fixed.


class ISODistributor(Distributor):

    def __init__(self):
        super(ISODistributor, self).__init__()
        self.cancelled = False
        self.summary = {}
        self.details = {'errors': {}}

    @classmethod
    def metadata(cls):
        """
        Used by Pulp to classify the capabilities of this distributor. The
        following keys are present in the returned dictionary:

        * id - Programmatic way to refer to this distributor. Must be unique
               across all distributors. Only letters and underscores are valid.
        * display_name - User-friendly identification of the distributor.
        * types - List of all content type IDs that may be published using this
               distributor.

        This method call may be made multiple times during the course of a
        running Pulp server and thus should not be used for initialization
        purposes.

        :return: description of the distributor's capabilities
        :rtype:  dict
        """
        return {
            'id': ids.TYPE_ID_DISTRIBUTOR_EXPORT,
            'display_name': 'Export Distributor',
            'types': [models.RPM.TYPE, models.SRPM.TYPE, models.DRPM.TYPE, models.Errata.TYPE,
                      models.Distribution.TYPE, models.PackageCategory.TYPE, models.PackageGroup.TYPE]
        }

    def validate_config(self, repo, config, related_repos):
        """
        Allows the distributor to check the contents of a potential configuration
        for the given repository. This call is made both for the addition of
        this distributor to a new repository as well as updating the configuration
        for this distributor on a previously configured repository.

        The return is a tuple of the result of the validation (True for success,
        False for failure) and a message. The message may be None and is unused
        in the success case. If the message is not None, i18n is taken into
        consideration when generating the message.

        The related_repos parameter contains a list of other repositories that
        have a configured distributor of this type. The distributor configurations
        is found in each repository in the "plugin_configs" field.

        :param repo: metadata describing the repository to which the configuration applies
        :type  repo: pulp.plugins.model.Repository
        :param config: plugin configuration instance; the proposed repo configuration is found within
        :type  config: pulp.plugins.config.PluginCallConfiguration
        :param related_repos: list of other repositories using this distributor type; empty list if
                there are none; entries are of type pulp.plugins.model.RelatedRepository
        :type  related_repos: list
        :return: tuple of (bool, str) to describe the result
        :rtype:  tuple
        """
        return export_utils.validate_export_config(config)

    def cancel_publish_repo(self, call_request, call_report):
        """
        Call cancellation control hook. This is not currently supported for this distributor

        :param call_request: call request for the call to cancel
        :type  call_request: CallRequest
        :param call_report:  call report for the call to cancel
        :type  call_report:  CallReport
        """
        # TODO: Add cancel support
        self.cancelled = True
        return metadata.cancel_createrepo(self.working_dir)

    def set_progress(self, type_id, status, progress_callback=None):
        """
        Calls the progress_callback function after checking that it is not None

        :param type_id:           The type id parameter for progress_callback
        :type  type_id:           str
        :param status:            The status parameter for progress_callback
        :type  status:            dict
        :param progress_callback: A function that takes type_id and status, in that order
        :type  progress_callback: function
        """
        if progress_callback:
            progress_callback(type_id, status)

    def publish_repo(self, repo, publish_conduit, config):
        """
        Export a yum repository to a given directory, or to ISO

        :param repo:            metadata describing the repository
        :type  repo:            pulp.plugins.model.Repository
        :param publish_conduit: provides access to relevant Pulp functionality
        :type  publish_conduit: pulp.plugins.conduits.repo_publish.RepoPublishConduit
        :param config:          plugin configuration
        :type  config:          pulp.plugins.config.PluginConfiguration

        :return: report describing the publish run
        :rtype:  pulp.plugins.model.PublishReport
        """
        # First, validate the configuration because there may be override config options, and currently,
        # validate_config is not called prior to publishing by the manager.
        valid_config, msg = export_utils.validate_export_config(config)
        if not valid_config:
            raise PulpDataException(msg)

        _logger.info('Starting export of [%s]' % repo.id)

        progress_status = {
            models.RPM.TYPE: {'state': constants.STATE_NOT_STARTED},
            models.Errata.TYPE: {'state': constants.STATE_NOT_STARTED},
            models.Distribution.TYPE: {'state': constants.STATE_NOT_STARTED},
            models.PackageCategory.TYPE: {'state': constants.STATE_NOT_STARTED},
            models.PackageGroup.TYPE: {'state': constants.STATE_NOT_STARTED},
            'metadata': {'state': constants.STATE_NOT_STARTED},
            'isos': {'state': constants.STATE_NOT_STARTED},
            'publish_http': {'state': constants.STATE_NOT_STARTED},
            'publish_https': {'state': constants.STATE_NOT_STARTED},
        }

        def progress_callback(type_id, status):
            progress_status[type_id] = status
            publish_conduit.set_progress(progress_status)

        # Retrieve a config tuple and unpack it for use
        config_settings = export_utils.retrieve_repo_config(repo, config)
        self.working_dir, self.date_filter = config_settings

        # Before starting, clean out the working directory. Done to remove last published ISOs
        shutil.rmtree(repo.working_dir, ignore_errors=True)
        os.makedirs(repo.working_dir)

        # If a date filter is not present, do a complete export. If it is, do an incremental export.
        if self.date_filter:
            result = export_utils.export_incremental_content(self.working_dir, publish_conduit,
                                                             self.date_filter)
        else:
            result = export_utils.export_complete_repo(repo.id, self.working_dir, publish_conduit,
                                                       config, progress_callback)
        self.summary = result[0]
        self.details = result[1]

        if not config.get(constants.EXPORT_DIRECTORY_KEYWORD):
            # build iso and publish via HTTPS
            self._publish_isos(repo, config, progress_callback)

        if len(self.details['errors']) != 0:
            return publish_conduit.build_failure_report(self.summary, self.details)
        return publish_conduit.build_success_report(self.summary, self.details)

    def _publish_isos(self, repo, config, progress_callback=None):
        """
        Extracts the necessary configuration information for the ISO creator and then calls it.

        :param repo:                metadata describing the repository
        :type  repo:                pulp.plugins.model.Repository
        :param config:              plugin configuration instance
        :type  config:              pulp.plugins.config.PluginCallConfiguration
        :param progress_callback:   callback to report progress info to publish_conduit. This function is
                                        expected to take the following arguments: type_id, a string, and
                                        status, which is a dict
        :type  progress_callback:   function
        """
        http_publish_dir = os.path.join(constants.EXPORT_HTTP_DIR, repo.id).rstrip('/')
        https_publish_dir = os.path.join(constants.EXPORT_HTTPS_DIR, repo.id).rstrip('/')
        image_prefix = config.get(constants.ISO_PREFIX_KEYWORD) or repo.id

        # Clean up the old export publish directories.
        shutil.rmtree(http_publish_dir, ignore_errors=True)
        shutil.rmtree(https_publish_dir, ignore_errors=True)

        # If publishing isn't enabled for http or https, set the path to None
        if not config.get(constants.PUBLISH_HTTP_KEYWORD):
            http_publish_dir = None
        if not config.get(constants.PUBLISH_HTTPS_KEYWORD):
            https_publish_dir = None

        export_utils.publish_isos(repo.working_dir, image_prefix, http_publish_dir, https_publish_dir,
                                  config.get(constants.ISO_SIZE_KEYWORD), progress_callback)
