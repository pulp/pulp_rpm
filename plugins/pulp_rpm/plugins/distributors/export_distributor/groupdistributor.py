from gettext import gettext as _
import os
import shutil

from pulp.common.config import read_json_config
from pulp.plugins.conduits.repo_publish import RepoPublishConduit
from pulp.plugins.distributor import GroupDistributor
from pulp.server.exceptions import PulpDataException






# Import export_utils from this directory, which is not in the python path
import export_utils
from pulp_rpm.common import constants, ids
from pulp_rpm.plugins.db import models
from pulp_rpm.yum_plugin import util

_logger = util.getLogger(__name__)
CONF_FILE_PATH = 'server/plugins.conf.d/%s.json' % ids.TYPE_ID_DISTRIBUTOR_GROUP_EXPORT

# Things left to do:
#   Cancelling a publish operation is not currently supported.
#   Published ISOs are left in the working directory. See export_utils.publish_isos to fix this.
#   This is not currently in the python path. When that gets fixed, the imports should be fixed.


def entry_point():
    config = read_json_config(CONF_FILE_PATH)
    return GroupISODistributor, config


class GroupISODistributor(GroupDistributor):

    def __init__(self):
        super(GroupISODistributor, self).__init__()
        self.cancelled = False
        self.summary = {}
        self.details = {}

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

        # The progress report for a group publish
        progress_status = {
            constants.PROGRESS_REPOS_KEYWORD: {constants.PROGRESS_STATE_KEY: constants.STATE_NOT_STARTED},
            constants.PROGRESS_ISOS_KEYWORD: {constants.PROGRESS_STATE_KEY: constants.STATE_NOT_STARTED},
            constants.PROGRESS_PUBLISH_HTTP: {constants.PROGRESS_STATE_KEY: constants.STATE_NOT_STARTED},
            constants.PROGRESS_PUBLISH_HTTPS: {constants.PROGRESS_STATE_KEY: constants.STATE_NOT_STARTED}
        }

        def progress_callback(progress_keyword, status):
            """
            Progress callback used to update the progress report for the publish conduit

            :param progress_keyword:    The keyword to assign the status to in the progress report dict
            :type  progress_keyword:    str
            :param status:              The status to assign to the keyword.
            :type  status:              dict
            """
            progress_status[progress_keyword] = status
            publish_conduit.set_progress(progress_status)

        # Before starting, clean out the working directory. Done to remove last published ISOs
        shutil.rmtree(repo_group.working_dir, ignore_errors=True)
        os.makedirs(repo_group.working_dir)

        # Retrieve the configuration for each repository, the skip types, and the date filter
        packed_config = export_utils.retrieve_group_export_config(repo_group, config)
        rpm_repositories, self.date_filter = packed_config

        # Update the progress for the repositories section
        repos_progress = export_utils.init_progress_report(len(rpm_repositories))
        progress_callback(constants.PROGRESS_REPOS_KEYWORD, repos_progress)

        # For every repository, extract the requested types to the working directory
        for repo_id, working_dir in rpm_repositories:
            # Create a repo conduit, which makes sharing code with the export and yum distributors easier
            repo_conduit = RepoPublishConduit(repo_id, publish_conduit.distributor_id)

            # If there is a date filter perform an incremental export, otherwise do everything
            if self.date_filter:
                result = export_utils.export_incremental_content(working_dir, repo_conduit,
                                                                 self.date_filter)
            else:
                result = export_utils.export_complete_repo(repo_id, working_dir, repo_conduit, config)
            if not config.get(constants.EXPORT_DIRECTORY_KEYWORD):
                util.generate_listing_files(repo_group.working_dir, working_dir)
            else:
                export_dir = config.get(constants.EXPORT_DIRECTORY_KEYWORD)
                util.generate_listing_files(export_dir, working_dir)

            self.summary[repo_id] = result[0]
            self.details[repo_id] = result[1]

            repos_progress[constants.PROGRESS_ITEMS_LEFT_KEY] -= 1
            repos_progress[constants.PROGRESS_NUM_SUCCESS_KEY] += 1
            progress_callback(constants.PROGRESS_REPOS_KEYWORD, repos_progress)

        repos_progress[constants.PROGRESS_STATE_KEY] = constants.STATE_COMPLETE
        progress_callback(constants.PROGRESS_REPOS_KEYWORD, repos_progress)

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

        :param repo_group:          metadata describing the repository group. Used to retrieve the
                                    working directory and group id.
        :type  repo_group:          pulp.plugins.model.RepositoryGroup
        :param config:              plugin configuration instance
        :type config:               pulp.plugins.config.PluginCallConfiguration
        :param progress_callback:   callback to report progress info to publish_conduit. This function is
                                    expected to take the following arguments: type_id, a string, and
                                    status, which is a dict
        :type progress_callback:    function
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
