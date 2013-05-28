# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

from gettext import gettext as _

from pulp.client.commands.repo.cudl import ListRepositoriesCommand
from pulp.common import constants as pulp_constants
from pulp.common.plugins import importer_constants

from pulp_rpm.common import constants


class ISORepoListCommand(ListRepositoriesCommand):

    def __init__(self, context):
        repos_title = _('ISO Repositories')
        super(ISORepoListCommand, self).__init__(context, repos_title=repos_title)

        # Both get_repositories and get_other_repositories will act on the full
        # list of repositories. Lazy cache the data here since both will be
        # called in succession, saving the round trip to the server.
        self.all_repos_cache = None

    def get_other_repositories(self, query_params, **kwargs):
        all_repos = self._all_repos(query_params)

        non_iso_repos = []
        for repo in all_repos:
            notes = repo['notes']
            if notes.get(pulp_constants.REPO_NOTE_TYPE_KEY, None) != constants.REPO_NOTE_ISO:
                non_iso_repos.append(repo)

        return non_iso_repos

    def get_repositories(self, query_params, **kwargs):
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
                imp_config = r['importers'][0]['config'] # there can only be one importer
    
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

        # This is safe from any issues with concurrency due to how the CLI works
        if self.all_repos_cache is None:
            self.all_repos_cache = self.context.server.repo.repositories(query_params).response_body

        return self.all_repos_cache