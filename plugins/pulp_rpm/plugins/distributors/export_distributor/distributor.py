import os
import shutil

from pulp.common.config import read_json_config
from pulp.plugins.distributor import Distributor
from pulp.server.exceptions import PulpDataException

from pulp_rpm.plugins.distributors.export_distributor import export_utils
from pulp_rpm.plugins.distributors.yum.publish import ExportRepoPublisher
from pulp_rpm.plugins.distributors.yum import configuration
from pulp_rpm.common import ids
from pulp_rpm.yum_plugin import util

_logger = util.getLogger(__name__)
CONF_FILE_PATH = 'server/plugins.conf.d/%s.json' % ids.TYPE_ID_DISTRIBUTOR_EXPORT

# Things left to do:
# Cancelling a publish operation is not currently supported
#   Published ISOs are left in the working directory. See export_utils.publish_isos to fix this.
#   This is not currently in the python path. When that gets fixed, the imports should be fixed.


def entry_point():
    config = read_json_config(CONF_FILE_PATH)
    return ISODistributor, config


class ISODistributor(Distributor):
    def __init__(self):
        super(ISODistributor, self).__init__()
        self._publisher = None

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
            'types': [ids.TYPE_ID_RPM, ids.TYPE_ID_SRPM, ids.TYPE_ID_DRPM, ids.TYPE_ID_ERRATA,
                      ids.TYPE_ID_DISTRO, ids.TYPE_ID_PKG_CATEGORY, ids.TYPE_ID_PKG_GROUP]
        }

    def validate_config(self, repo, config, config_conduit):
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

        :param repo:           metadata describing the repository to which the configuration applies
        :type  repo:           pulp.plugins.model.Repository
        :param config:         plugin configuration instance; the proposed repo configuration is
                               found within
        :type  config:         pulp.plugins.config.PluginCallConfiguration
        :param config_conduit: Configuration Conduit;
        :type  config_conduit: pulp.plugins.conduits.repo_validate.RepoConfigConduit

        :return: tuple of (bool, str) to describe the result
        :rtype:  tuple
        """
        return export_utils.validate_export_config(config)

    def cancel_publish_repo(self):
        """
        Call cancellation control hook.
        """
        if self._publisher is not None:
            self._publisher.cancel()

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
        # First, validate the configuration because there may be override config options, and
        # currently, validate_config is not called prior to publishing by the manager.
        valid_config, msg = export_utils.validate_export_config(config)
        if not valid_config:
            raise PulpDataException(msg)

        _logger.info('Starting export of [%s]' % repo.id)
        self._publisher = ExportRepoPublisher(repo, publish_conduit, config,
                                              ids.TYPE_ID_DISTRIBUTOR_EXPORT)
        return self._publisher.publish()

    def distributor_removed(self, repo, config):
        """
        Called when a distributor of this type is removed from a repository.

        :param repo: metadata describing the repository
        :type  repo: pulp.plugins.model.Repository

        :param config: plugin configuration
        :type  config: pulp.plugins.config.PluginCallConfiguration
        """
        # remove the directories that might have been created for this repo/distributor
        dir_list = [configuration.get_master_publish_dir(repo, ids.TYPE_ID_DISTRIBUTOR_EXPORT),
                    os.path.join(configuration.HTTP_EXPORT_DIR, repo.id),
                    os.path.join(configuration.HTTPS_EXPORT_DIR, repo.id)]

        for repo_dir in dir_list:
            shutil.rmtree(repo_dir, ignore_errors=True)
