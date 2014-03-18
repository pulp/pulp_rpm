import os
import shutil

from pulp.common.config import read_json_config
from pulp.plugins.distributor import Distributor
from pulp.server.exceptions import PulpDataException






# Import export_utils from this directory, which is not in the python path
from pulp_rpm.plugins.distributors.export_distributor import export_utils
from pulp_rpm.common import constants, ids
from pulp_rpm.yum_plugin import util, metadata

_logger = util.getLogger(__name__)
CONF_FILE_PATH = 'server/plugins.conf.d/%s.json' % ids.TYPE_ID_DISTRIBUTOR_EXPORT

# Things left to do:
#   Cancelling a publish operation is not currently supported
#   Published ISOs are left in the working directory. See export_utils.publish_isos to fix this.
#   This is not currently in the python path. When that gets fixed, the imports should be fixed.


def entry_point():
    config = read_json_config(CONF_FILE_PATH)
    return ISODistributor, config


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
        Call cancellation control hook. This is not currently supported for this distributor
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
        # First, validate the configuration because there may be override config options, and
        # currently, validate_config is not called prior to publishing by the manager.
        valid_config, msg = export_utils.validate_export_config(config)
        if not valid_config:
            raise PulpDataException(msg)

        _logger.info('Starting export of [%s]' % repo.id)

        progress_status = {
            ids.TYPE_ID_RPM: {'state': constants.STATE_NOT_STARTED},
            ids.TYPE_ID_ERRATA: {'state': constants.STATE_NOT_STARTED},
            ids.TYPE_ID_DISTRO: {'state': constants.STATE_NOT_STARTED},
            ids.TYPE_ID_PKG_CATEGORY: {'state': constants.STATE_NOT_STARTED},
            ids.TYPE_ID_PKG_GROUP: {'state': constants.STATE_NOT_STARTED},
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
                                                             self.date_filter, progress_callback)
        else:
            result = export_utils.export_complete_repo(repo.id, self.working_dir, publish_conduit,
                                                       config, progress_callback)

        self.summary = result[0]
        self.details = result[1]

        if not config.get(constants.EXPORT_DIRECTORY_KEYWORD):
            util.generate_listing_files(repo.working_dir, self.working_dir)
            # build iso and publish via HTTPS
            self._publish_isos(repo, config, progress_callback)
        else:
            export_dir = config.get(constants.EXPORT_DIRECTORY_KEYWORD)
            util.generate_listing_files(export_dir, self.working_dir)

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
