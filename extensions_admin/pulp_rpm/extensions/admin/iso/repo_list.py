from gettext import gettext as _

from pulp.client.commands.repo.cudl import ListRepositoriesCommand
from pulp.common import constants as pulp_constants
from pulp.common.plugins import importer_constants

from pulp_rpm.common import constants


class ISORepoListCommand(ListRepositoriesCommand):
    """
    This command allows the user to list all of the ISO repositories.
    """

    def __init__(self, context):
        """
        Configure the title text to say ISO Repositories, and initialize our repo cache.

        :param context: The client context
        :type  context: pulp.client.extensions.core.ClientContext
        """
        repos_title = _('ISO Repositories')
        super(ISORepoListCommand, self).__init__(context, repos_title=repos_title)

        # Both get_repositories and get_other_repositories will act on the full
        # list of repositories. Lazy cache the data here since both will be
        # called in succession, saving the round trip to the server.
        self.all_repos_cache = None

    def get_other_repositories(self, query_params, **kwargs):
        """
        Return a list of non-ISO repositories.

        :param query_params: A dictionary of query parameters that we will use to determine
                             the level of detail to show to the user.
        :type  query_params: dict
        """
        all_repos = self._all_repos(query_params)

        non_iso_repos = []
        for repo in all_repos:
            notes = repo['notes']
            if notes.get(pulp_constants.REPO_NOTE_TYPE_KEY, None) != constants.REPO_NOTE_ISO:
                non_iso_repos.append(repo)

        return non_iso_repos

    def get_repositories(self, query_params, **kwargs):
        """
        Return a list of ISO repositories, stripping out all SSL certificates and keys that are
        found in them.

        :param query_params: A dictionary of query parameters that we will use to determine
                             the level of detail to show to the user.
        :type  query_params: dict
        """
        all_repos = self._all_repos(query_params)

        # Due to a deficiency in the bindings to the API, we cannot used the server side repository
        # search feature to select just the ISO repositories, and also retrieve their importers and
        # distributors in that same call. Due to this, we will filter out the correct repos client
        # side. See https://bugzilla.redhat.com/show_bug.cgi?id=967980
        iso_repos = []
        for repo in all_repos:
            notes = repo['notes']
            if pulp_constants.REPO_NOTE_TYPE_KEY in notes and \
               notes[pulp_constants.REPO_NOTE_TYPE_KEY] == constants.REPO_NOTE_ISO:
                iso_repos.append(repo)

        # Strip out the certificate and private key if present
        for r in iso_repos:
            # The importers will only be present in a --details view, so make
            # sure it's there before proceeding
            if 'importers' in r:
                imp_config = r['importers'][0]['config']  # there can only be one importer

                # If either are present, tell the user the feed is using SSL
                if importer_constants.KEY_SSL_CLIENT_CERT in imp_config or \
                   importer_constants.KEY_SSL_CLIENT_KEY in imp_config:
                    imp_config['feed_ssl_configured'] = 'True'

                # Remove the actual values so they aren't displayed
                imp_config.pop(importer_constants.KEY_SSL_CLIENT_CERT, None)
                imp_config.pop(importer_constants.KEY_SSL_CLIENT_KEY, None)
                imp_config.pop(importer_constants.KEY_SSL_CA_CERT, None)

            # Remove the authorization certificate from the distributor
            if 'distributors' in r:
                for distributor in r['distributors']:
                    distributor_config = distributor['config']

                    if constants.CONFIG_SSL_AUTH_CA_CERT in distributor_config:
                        distributor_config['repo_protected'] = 'True'

                    distributor_config.pop(constants.CONFIG_SSL_AUTH_CA_CERT, None)

        return iso_repos

    def _all_repos(self, query_params):
        """
        Return a list of all the repos that exist on the server, regardless of their type. Cache
        the results on self.all_repos_cache, so we can avoid multiple calls to the server.

        :param query_params: A dictionary of query parameters that we will use to determine
                             the level of detail to show to the user.
        :type  query_params: dict
        """
        # This is safe from any issues with concurrency due to how the CLI works
        if self.all_repos_cache is None:
            self.all_repos_cache = self.context.server.repo.repositories(query_params).response_body

        return self.all_repos_cache
