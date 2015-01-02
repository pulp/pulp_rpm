import os

from pulp.plugins.file.distributor import FileDistributor

from pulp_rpm.common import ids
from pulp_rpm.common import constants
from pulp_rpm.plugins.distributors.iso_distributor import configuration, publish


def entry_point():
    """
    Advertise the ISODistributor to Pulp.

    :return: ISODistributor and its empty config
    :rtype:  tuple
    """
    return ISODistributor, {}


class ISODistributor(FileDistributor):
    """
    Distribute ISOs like a boss.
    """

    @classmethod
    def metadata(cls):
        """
        Advertise the capabilities of the mighty ISODistributor.

        :return: The description of the impressive ISODistributor's capabilities.
        :rtype:  dict
        """
        return {
            'id': ids.TYPE_ID_DISTRIBUTOR_ISO,
            'display_name': 'ISO Distributor',
            'types': [ids.TYPE_ID_ISO]
        }

    def validate_config(self, repo, config, config_conduit):
        return configuration.validate(config)

    def unpublish_repo(self, repo, config):
        """
        Perform actions necessary when upublishing a repo

        Please also see the superclass method definition for more documentation on this method.

        :param repo: metadata describing the repository
        :type  repo: pulp.plugins.model.Repository

        :param config: plugin configuration
        :type  config: pulp.plugins.config.PluginCallConfiguration
        """
        super(ISODistributor, self).unpublish_repo(repo, config)
        publish.remove_repository_protection(repo)

    def get_hosting_locations(self, repo, config):
        """
        Get the paths on the filesystem where the build directory should be copied

        :param repo: The repository that is going to be hosted
        :type repo: pulp.plugins.model.Repository
        :param config:    plugin configuration
        :type  config:    pulp.plugins.config.PluginConfiguration
        :return : list of paths on the filesystem where the build directory should be copied
        :rtype list of str
        """

        hosting_locations = []
        # Publish the HTTP portion, if applicable
        http_dest_dir = os.path.join(constants.ISO_HTTP_DIR, repo.id)

        serve_http = config.get_boolean(constants.CONFIG_SERVE_HTTP)
        serve_http = serve_http if serve_http is not None else constants.CONFIG_SERVE_HTTP_DEFAULT
        if serve_http:
            hosting_locations.append(http_dest_dir)

        # Publish the HTTPs portion, if applicable
        if self._is_https_supported(config):
            https_dest_dir = os.path.join(constants.ISO_HTTPS_DIR, repo.id)
            hosting_locations.append(https_dest_dir)

        return hosting_locations

    def post_repo_publish(self, repo, config):
        """
        API method that is called after the contents of a published repo have
        been moved into place on the filesystem

        :param repo: The repository that is going to be hosted
        :type repo: pulp.plugins.model.Repository
        :param config: the configuration for the repository
        :type  config: pulp.plugins.config.PluginCallConfiguration
        """
        if self._is_https_supported(config):
            authorization_ca_cert = config.get(constants.CONFIG_SSL_AUTH_CA_CERT)
            if authorization_ca_cert:
                publish.configure_repository_protection(repo, authorization_ca_cert)

    def _is_https_supported(self, config):
        """
        Internal method to test if a config supports https

        :param config: the configuration for the repository
        :type  config: pulp.plugins.config.PluginCallConfiguration

        :return True if https is supported, otherwise false
        :rtype boolean
        """
        serve_https = config.get_boolean(constants.CONFIG_SERVE_HTTPS)
        serve_https = serve_https if serve_https is not None else \
            constants.CONFIG_SERVE_HTTPS_DEFAULT

        return serve_https
