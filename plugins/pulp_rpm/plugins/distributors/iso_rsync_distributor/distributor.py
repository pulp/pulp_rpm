import logging
from gettext import gettext as _

from pulp.common.config import read_json_config
from pulp.plugins.distributor import Distributor
from pulp.plugins.rsync import configuration

from pulp_rpm.common.ids import TYPE_ID_ISO
from pulp_rpm.plugins.distributors.iso_rsync_distributor import publish

_LOG = logging.getLogger(__name__)

TYPE_ID_DISTRIBUTOR_ISO_RSYNC = 'iso_rsync_distributor'
CONF_FILE_PATH = 'server/plugins.conf.d/%s.json' % TYPE_ID_DISTRIBUTOR_ISO_RSYNC

DISTRIBUTOR_DISPLAY_NAME = 'ISO Rsync Distributor'


def entry_point():
    config = read_json_config(CONF_FILE_PATH)
    return ISORsyncDistributor, config


class ISORsyncDistributor(Distributor):
    """
    Distributor class for publishing RPM repo to remote server.

    :ivar canceled: if true, the task has been canceled
    :ivar _publisher: instance of RPMRsyncPublisher
    """

    def __init__(self):
        super(ISORsyncDistributor, self).__init__()
        self.canceled = False
        self._publisher = None

    @classmethod
    def metadata(cls):
        """
        Used by Pulp to classify the capabilities of this distributor.

        :return: description of the distributor's capabilities
        :rtype:  dict
        """
        return {'id': TYPE_ID_DISTRIBUTOR_ISO_RSYNC,
                'display_name': DISTRIBUTOR_DISPLAY_NAME,
                'types': [TYPE_ID_ISO]}

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
        _LOG.debug(_('Validating iso repository configuration: %(repoid)s') % {'repoid': repo.id})
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
        _LOG.debug(_('Publishing ISO repository: %(repoid)s') % {'repoid': repo.id})
        self._publisher = publish.ISORsyncPublisher(repo, publish_conduit, config,
                                                    TYPE_ID_DISTRIBUTOR_ISO_RSYNC)
        return self._publisher.publish()

    def cancel_publish_repo(self):
        """
        Call cancellation control hook.
        """
        _LOG.debug(_('Canceling publishing repo to remote server'))
        self.canceled = True
        if self._publisher is not None:
            self._publisher.cancel()
