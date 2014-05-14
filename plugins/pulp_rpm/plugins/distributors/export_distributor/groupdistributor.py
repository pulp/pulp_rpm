from gettext import gettext as _
import os
import shutil

from pulp.common.config import read_json_config
from pulp.plugins.distributor import GroupDistributor
from pulp.server.exceptions import PulpDataException

from pulp_rpm.common import  ids
from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.distributors.export_distributor import export_utils
from pulp_rpm.plugins.distributors.yum import configuration
from pulp_rpm.yum_plugin import util

from pulp_rpm.plugins.distributors.yum.publish import ExportRepoGroupPublisher

_logger = util.getLogger(__name__)
CONF_FILE_PATH = 'server/plugins.conf.d/%s.json' % ids.TYPE_ID_DISTRIBUTOR_GROUP_EXPORT


def entry_point():
    config = read_json_config(CONF_FILE_PATH)
    return GroupISODistributor, config


class GroupISODistributor(GroupDistributor):

    def __init__(self):
        super(GroupISODistributor, self).__init__()
        self.cancelled = False
        self.summary = {}
        self.details = {}
        self._publisher = None

    @classmethod
    def metadata(cls):
        """
        Used by Pulp to classify the capabilities of this distributor. The
        following keys must be present in the returned dictionary:

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
            'id': ids.TYPE_ID_DISTRIBUTOR_GROUP_EXPORT,
            'display_name': _('Group Export Distributor'),
            'types': [models.RPM.TYPE, models.SRPM.TYPE, models.DRPM.TYPE, models.Errata.TYPE,
                      models.Distribution.TYPE, models.PackageCategory.TYPE, models.PackageGroup.TYPE]
        }

    def validate_config(self, repo_group, config, config_conduit):
        """
        Allows the distributor to check the contents of a potential configuration
        for the given repository. This call is made both for the addition of
        this distributor to a new repository group, as well as updating the configuration
        for this distributor on a previously configured repository.

        The return is a tuple of the result of the validation (True for success,
        False for failure) and a message. The message may be None and is unused
        in the success case. If the message is not None, i18n is taken into
        consideration when generating the message.

        The related_repo_groups parameter contains a list of other repository groups that
        have a configured distributor of this type. The distributor configurations
        is found in each repository group in the "plugin_configs" field.

        :param repo_group:          metadata describing the repository to which the configuration applies
        :type  repo_group:          pulp.plugins.model.Repository
        :param config:              plugin configuration instance
        :type  config:              pulp.plugins.config.PluginCallConfiguration
        :param config_conduit:      Configuration Conduit;
        :type config_conduit:       pulp.plugins.conduits.repo_validate.RepoConfigConduit

        :return: tuple of (bool, str) to describe the result
        :rtype:  tuple
        """
        return export_utils.validate_export_config(config)

    def publish_group(self, repo_group, publish_conduit, config):
        """
        Publishes the given repository group.

        :param repo_group:      metadata describing the repository group
        :type  repo_group:      pulp.plugins.model.RepositoryGroup
        :param publish_conduit: provides access to relevant Pulp functionality
        :type  publish_conduit: pulp.plugins.conduits.repo_publish.RepoGroupPublishConduit
        :param config:          plugin configuration
        :type  config:          pulp.plugins.config.PluginConfiguration
        :return:                report describing the publish run
        :rtype:                 pulp.plugins.model.PublishReport
        """
        # First, validate the configuration because there may be override config options, and currently,
        # validate_config is not called prior to publishing by the manager.
        valid_config, msg = export_utils.validate_export_config(config)
        if not valid_config:
            raise PulpDataException(msg)

        _logger.info('Beginning export of the following repository group: [%s]' % repo_group.id)
        self._publisher = ExportRepoGroupPublisher(repo_group, publish_conduit, config,
                                                   ids.TYPE_ID_DISTRIBUTOR_GROUP_EXPORT)
        return self._publisher.publish()

    def cancel_publish_repo(self):
        """
        Call cancellation control hook.
        """
        if self._publisher is not None:
            self._publisher.cancel()

    def distributor_removed(self, repo, config):
        """
        Called when a distributor of this type is removed from a repository.

        :param repo: metadata describing the repository
        :type  repo: pulp.plugins.model.RepositoryGroup

        :param config: plugin configuration
        :type  config: pulp.plugins.config.PluginCallConfiguration
        """
        # remove the directories that might have been created for this repo/distributor
        dir_list = [repo.working_dir,
                    configuration.get_master_publish_dir(repo,
                                                         ids.TYPE_ID_DISTRIBUTOR_GROUP_EXPORT),
                    os.path.join(configuration.HTTP_EXPORT_GROUP_DIR, repo.id),
                    os.path.join(configuration.HTTPS_EXPORT_GROUP_DIR, repo.id)]

        for repo_dir in dir_list:
            shutil.rmtree(repo_dir, ignore_errors=True)
