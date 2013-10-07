# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the License
# (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied, including the
# implied warranties of MERCHANTABILITY, NON-INFRINGEMENT, or FITNESS FOR A
# PARTICULAR PURPOSE.
# You should have received a copy of GPLv2 along with this software;
# if not, see http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt

from pulp.common.config import read_json_config
from pulp.plugins.distributor import Distributor

from pulp_rpm.common.ids import (
    TYPE_ID_DISTRIBUTOR_YUM, TYPE_ID_DISTRO, TYPE_ID_DRPM, TYPE_ID_ERRATA,
    TYPE_ID_PKG_CATEGORY, TYPE_ID_PKG_GROUP, TYPE_ID_RPM, TYPE_ID_SRPM,
    TYPE_ID_YUM_REPO_METADATA_FILE)
from pulp_rpm.yum_plugin import util

from . import configuration, publish

# -- global constants ----------------------------------------------------------

_LOG = util.getLogger(__name__)

CONF_FILE_PATH = 'server/plugins.conf.d/%s.json' % TYPE_ID_DISTRIBUTOR_YUM

DISTRIBUTOR_DISPLAY_NAME = 'Yum Distributor'

# -- entry point ---------------------------------------------------------------

def entry_point():
    config = read_json_config(CONF_FILE_PATH)
    return YumHTTPDistributor, config

# -- distributor ---------------------------------------------------------------

class YumHTTPDistributor(Distributor):
    """
    Distributor class for HTTP and HTTPS Yum repositories.
    """

    def __init__(self):
        super(YumHTTPDistributor, self).__init__()

        self.canceled = False
        self._publisher = None

    @classmethod
    def metadata(cls):
        """
        Used by Pulp to classify the capabilities of this distributor.

        :return: description of the distributor's capabilities
        :rtype:  dict
        """
        return {'id': TYPE_ID_DISTRIBUTOR_YUM,
                'display_name': DISTRIBUTOR_DISPLAY_NAME,
                'types': [TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM, TYPE_ID_ERRATA,
                          TYPE_ID_PKG_GROUP, TYPE_ID_PKG_CATEGORY, TYPE_ID_DISTRO,
                          TYPE_ID_YUM_REPO_METADATA_FILE]}

    # -- repo lifecycle methods ------------------------------------------------

    def validate_config(self, repo, config, config_conduit):
        """
        Allows the distributor to check the contents of a potential configuration
        for the given repository. This call is made both for the addition of
        this distributor to a new repository as well as updating the configuration
        for this distributor on a previously configured repository.

        :param repo: metadata describing the repository to which the
                     configuration applies
        :type  repo: pulp.plugins.model.Repository

        :param config: plugin configuration instance; the proposed repo
                       configuration is found within
        :type  config: pulp.plugins.config.PluginCallConfiguration

        :param config_conduit: Configuration Conduit;
        :type  config_conduit: pulp.plugins.conduits.repo_config.RepoConfigConduit

        :return: tuple of (bool, str) to describe the result
        :rtype:  tuple
        """
        _LOG.debug('Validating yum repository configuration: %s' % repo.id)

        return configuration.validate_config(repo, config, config_conduit)

    def distributor_added(self, repo, config):
        """
        Called upon the successful addition of a distributor of this type to a
        repository.

        :param repo: metadata describing the repository
        :type  repo: pulp.plugins.model.Repository

        :param config: plugin configuration
        :type  config: pulp.plugins.config.PluginCallConfiguration
        """
        pass

    def distributor_removed(self, repo, config):
        """
        Called when a distributor of this type is removed from a repository.

        :param repo: metadata describing the repository
        :type  repo: pulp.plugins.model.Repository

        :param config: plugin configuration
        :type  config: pulp.plugins.config.PluginCallConfiguration
        """
        pass

    # -- actions ---------------------------------------------------------------

    def publish_repo(self, repo, publish_conduit, config):
        """
        Publishes the given repository.

        :param repo: metadata describing the repository
        :type  repo: pulp.plugins.model.Repository

        :param publish_conduit: provides access to relevant Pulp functionality
        :type  publish_conduit: pulp.plugins.conduits.repo_publish.RepoPublishConduit

        :param config: plugin configuration
        :type  config: pulp.plugins.config.PluginConfiguration

        :return: report describing the publish run
        :rtype:  pulp.plugins.model.PublishReport
        """
        _LOG.debug('Publishing yum repository: %s' % repo.id)

        self._publisher = publish.Publisher(repo, publish_conduit, config)
        self._publisher.publish()

    def cancel_publish_repo(self, call_request, call_report):
        """
        Call cancellation control hook.

        :param call_request: call request for the call to cancel
        :type call_request: pulp.server.dispatch.call.CallRequest
        :param call_report: call report for the call to cancel
        :type call_report: pulp.server.dispatch.call.CallReport
        """
        _LOG.debug('Canceling yum repository publish')

        self.canceled = True
        if self._publisher is not None:
            self._publisher.cancel()

    def create_consumer_payload(self, repo, config, binding_config):
        """
        Called when a consumer binds to a repository using this distributor.
        This call should return a dictionary describing all data the consumer
        will need to access the repository.

        :param repo: metadata describing the repository
        :type  repo: pulp.plugins.model.Repository

        :param config: plugin configuration
        :type  config: pulp.plugins.config.PluginCallConfiguration

        :param binding_config: configuration applicable only for the specific
               consumer the payload is generated for; this will be None
               if there are no specific options for the consumer in question
        :type  binding_config: object or None

        :return: dictionary of relevant data
        :rtype:  dict
        """
        return {}


