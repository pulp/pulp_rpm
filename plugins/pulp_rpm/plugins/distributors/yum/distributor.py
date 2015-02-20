import errno
import os
import shutil

from pulp.common.config import read_json_config
from pulp.plugins.distributor import Distributor
from pulp.server.config import config as pulp_server_config

import pulp_rpm.common.constants as constants
from pulp_rpm.common.ids import (
    TYPE_ID_DISTRIBUTOR_YUM, TYPE_ID_DISTRO, TYPE_ID_DRPM, TYPE_ID_ERRATA,
    TYPE_ID_PKG_CATEGORY, TYPE_ID_PKG_GROUP, TYPE_ID_RPM, TYPE_ID_SRPM,
    TYPE_ID_YUM_REPO_METADATA_FILE)
from pulp_rpm.yum_plugin import util
from . import configuration, publish


_logger = util.getLogger(__name__)

CONF_FILE_PATH = 'server/plugins.conf.d/%s.json' % TYPE_ID_DISTRIBUTOR_YUM

DISTRIBUTOR_DISPLAY_NAME = 'Yum Distributor'

# This needs to be a config option in the distributor's .conf file that is merged
# with a root directory specified in the configuration for the pulp server.  However,
# for now the pulp server does not have this ability so we are going to stick with
# a hard coded constant.
RELATIVE_URL = '/pulp/repos'


def entry_point():
    config = read_json_config(CONF_FILE_PATH)
    return YumHTTPDistributor, config


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
        _logger.debug('Validating yum repository configuration: %s' % repo.id)

        return configuration.validate_config(repo, config, config_conduit)

    def distributor_removed(self, repo, config):
        """
        Called when a distributor of this type is removed from a repository.

        :param repo: metadata describing the repository
        :type  repo: pulp.plugins.model.Repository

        :param config: plugin configuration
        :type  config: pulp.plugins.config.PluginCallConfiguration
        """

        # remove the directories that might have been created for this repo/distributor
        dir_list = [repo.working_dir,
                    configuration.get_master_publish_dir(repo, TYPE_ID_DISTRIBUTOR_YUM)]

        for repo_dir in dir_list:
            shutil.rmtree(repo_dir, ignore_errors=True)

        # remove the symlinks that might have been created for this repo/distributor
        http_publish_dir = configuration.get_http_publish_dir(config)
        https_publish_dir = configuration.get_https_publish_dir(config)

        for publish_dir in [http_publish_dir, https_publish_dir]:
            symlink = os.path.join(publish_dir, configuration.get_repo_relative_path(repo, config))
            symlink_without_trailing_slash = symlink.rstrip(os.sep)
            try:
                os.unlink(symlink_without_trailing_slash)
            except OSError as error:
                # If the symlink doesn't exist pass
                if error.errno != errno.ENOENT:
                    raise
            else:
                # Clean the directories that were hosted for this repo.
                self.clean_simple_hosting_directories(symlink_without_trailing_slash, publish_dir)

        # remove certificates for certificate based auth
        configuration.remove_cert_based_auth(repo, config)

    def clean_simple_hosting_directories(self, start_location, containing_dir):
        """
        Remove any orphaned directory structure left by the removal of a repo.

        :param start_location: path of the symlink of the repo that was removed.
        :type  start_location: str
        :param containing_dir: path of the location of the base dir containing hosted repos
        :type  containing_dir: str
        """
        up_dir = os.path.dirname(start_location)

        # This function is potentially dangerous so it is important to restrict it to the
        # publish directories.
        if containing_dir not in os.path.dirname(up_dir):
            return

        # If the only file is the listing file, it is safe to delete the file and containing dir.
        if os.listdir(up_dir) == ['listing']:
            os.remove(os.path.join(up_dir, 'listing'))
            try:
                os.rmdir(up_dir)
            except OSError:
                # If this happened, there was a concurrency issue and it is no longer safe to
                # remove the directory. It is possible that the concurrent operation created the
                # listing file before this operation deleted it, so to be safe, we need to
                # regenerate the listing file.
                util.generate_listing_files(up_dir, up_dir)
                return

        self.clean_simple_hosting_directories(up_dir, containing_dir)

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
        _logger.debug('Publishing yum repository: %s' % repo.id)

        self._publisher = publish.Publisher(repo, publish_conduit, config, TYPE_ID_DISTRIBUTOR_YUM)
        return self._publisher.publish()

    def cancel_publish_repo(self):
        """
        Call cancellation control hook.
        """
        _logger.debug('Canceling yum repository publish')

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
        payload = dict()
        payload['repo_name'] = repo.display_name
        payload['server_name'] = pulp_server_config.get('server', 'server_name')
        ssl_ca_path = pulp_server_config.get('security', 'ssl_ca_certificate')
        try:
            payload['ca_cert'] = open(ssl_ca_path).read()
        except (OSError, IOError):
            payload['ca_cert'] = config.get('https_ca')

        payload['relative_path'] = \
            '/'.join([RELATIVE_URL, configuration.get_repo_relative_path(repo, config)])
        payload['protocols'] = []
        if config.get('http'):
            payload['protocols'].append('http')
        if config.get('https'):
            payload['protocols'].append('https')
        payload['gpg_keys'] = []
        if config.get('gpgkey') is not None:
            payload['gpg_keys'] = {'pulp.key': config.get('gpgkey')}
        payload['client_cert'] = None
        if config.get('auth_cert') and config.get('auth_ca'):
            payload['client_cert'] = config.get('auth_cert')
        else:
            # load the global auth if enabled
            repo_auth_config = configuration.load_config(constants.REPO_AUTH_CONFIG_FILE)
            global_cert_dir = repo_auth_config.get('repos', 'global_cert_location')
            global_auth_cert = os.path.join(global_cert_dir, 'pulp-global-repo.cert')
            global_auth_key = os.path.join(global_cert_dir, 'pulp-global-repo.key')
            global_auth_ca = os.path.join(global_cert_dir, 'pulp-global-repo.ca')
            if os.path.exists(global_auth_ca) and \
                    os.path.exists(global_auth_cert) and \
                    os.path.exists(global_auth_key):
                payload['global_auth_cert'] = open(global_auth_cert).read()
                payload['global_auth_key'] = open(global_auth_key).read()
                payload['global_auth_ca'] = open(global_auth_ca).read()

        return payload
