from gettext import gettext as _
import logging

from pulp.common.config import read_json_config
from pulp.plugins.distributor import Distributor
from pulp.plugins.rsync import configuration

from pulp_rpm.plugins.distributors.rsync import publish
from pulp_rpm.common.ids import (TYPE_ID_DISTRO, TYPE_ID_DRPM, TYPE_ID_ERRATA, TYPE_ID_PKG_GROUP,
                                 TYPE_ID_PKG_CATEGORY, TYPE_ID_RPM, TYPE_ID_SRPM,
                                 TYPE_ID_YUM_REPO_METADATA_FILE)

_LOG = logging.getLogger(__name__)

TYPE_ID_DISTRIBUTOR_RPM_RSYNC = 'rpm_rsync_distributor'
CONF_FILE_PATH = 'server/plugins.conf.d/%s.json' % TYPE_ID_DISTRIBUTOR_RPM_RSYNC

DISTRIBUTOR_DISPLAY_NAME = 'RPM Rsync Distributor'


def entry_point():
    config = read_json_config(CONF_FILE_PATH)
    return RPMRsyncDistributor, config


class RPMRsyncDistributor(Distributor):
    """
    Distributor class for publishing RPM repo to remote server.

    :ivar canceled: if true, task has been canceled
    :ivar _publisher: instance of RPMRsyncPublisher
    """

    def __init__(self):
        super(RPMRsyncDistributor, self).__init__()

        self.canceled = False
        self._publisher = None

    @classmethod
    def metadata(cls):
        """
        Used by Pulp to classify the capabilities of this distributor.

        :return: description of the distributor's capabilities
        :rtype:  dict
        """
        return {'id': TYPE_ID_DISTRIBUTOR_RPM_RSYNC,
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
        _LOG.debug(_('Validating yum repository configuration: %(repoid)s') % {'repoid': repo.id})

        return configuration.validate_config(repo, config, config_conduit)

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
        _LOG.debug(_('Publishing yum repository: %(repoid)s') % {'repoid': repo.id})

        self._publisher = publish.RPMRsyncPublisher(repo, publish_conduit, config,
                                                    TYPE_ID_DISTRIBUTOR_RPM_RSYNC)
        return self._publisher.publish()
