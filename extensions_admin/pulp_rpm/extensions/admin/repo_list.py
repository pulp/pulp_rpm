# -*- coding: utf-8 -*-
# Copyright (c) 2013 Red Hat, Inc.
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
from pulp_rpm.common import constants
from pulp_rpm.common.ids import YUM_DISTRIBUTOR_ID


class RpmRepoListCommand(ListRepositoriesCommand):

    def __init__(self, context):
        repos_title = _('RPM Repositories')
        super(RpmRepoListCommand, self).__init__(context, repos_title=repos_title)

        # Both get_repositories and get_other_repositories will act on the full
        # list of repositories. Lazy cache the data here since both will be
        # called in succession, saving the round trip to the server.
        self.all_repos_cache = None

    def get_repositories(self, query_params, **kwargs):
        all_repos = self._all_repos(query_params, **kwargs)

        rpm_repos = []
        for repo in all_repos:
            notes = repo['notes']
            if pulp_constants.REPO_NOTE_TYPE_KEY in notes and notes[pulp_constants.REPO_NOTE_TYPE_KEY] == constants.REPO_NOTE_RPM:
                rpm_repos.append(repo)

        # There isn't really anything compelling in the exporter distributor
        # to display to the user, so remove it entirely.
        for r in rpm_repos:
            if 'distributors' in r:
                r['distributors'] = [x for x in r['distributors'] if x['id'] == YUM_DISTRIBUTOR_ID]

        # Strip out the certificate and private key if present
        for r in rpm_repos:
            # The importers will only be present in a --details view, so make
            # sure it's there before proceeding
            if 'importers' not in r:
                continue

            imp_config = r['importers'][0]['config'] # there can only be one importer

            # If either are present, tell the user the feed is using SSL
            if 'ssl_client_cert' in imp_config or 'ssl_client_key' in imp_config:
                imp_config['feed_ssl_configured'] = 'True'

            # Remove the actual values so they aren't displayed
            imp_config.pop('ssl_client_cert', None)
            imp_config.pop('ssl_client_key', None)

        return rpm_repos

    def get_other_repositories(self, query_params, **kwargs):
        all_repos = self._all_repos(query_params, **kwargs)

        non_rpm_repos = []
        for repo in all_repos:
            notes = repo['notes']
            if notes.get(pulp_constants.REPO_NOTE_TYPE_KEY, None) != constants.REPO_NOTE_RPM:
                non_rpm_repos.append(repo)

        return non_rpm_repos

    def _all_repos(self, query_params, **kwargs):

        # This is safe from any issues with concurrency due to how the CLI works
        if self.all_repos_cache is None:
            self.all_repos_cache = self.context.server.repo.repositories(query_params).response_body

        return self.all_repos_cache
