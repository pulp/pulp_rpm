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

from copy import deepcopy
from gettext import gettext as _
import mock

from pulp.common.plugins import importer_constants

from pulp_rpm.common import constants
from pulp_rpm.extension.admin.iso import repo_list
import rpm_support_base


# These are some test repos that are returned by the repo_mock() repo object. They were copied from
# real repositories from a working database and then massaged into this form for testing purposes
TEST_REPOS = [
    {'display_name': 'test_iso_repo', 'description': None,
     'distributors': [
        {'repo_id': 'test_iso_repo', '_ns': 'repo_distributors',
         'last_publish': '2013-05-21T12:41:17-04:00', 'auto_publish': True,
         'scheduled_publishes': [], 'distributor_type_id': 'iso_distributor',
         '_id': {'$oid': '519ba0a0b1a8a15a1fcae0b1'}, 'config': {}, 'id': 'iso_distributor'}],
     '_ns': 'repos', 'notes': {'_repo-type': 'iso-repo'}, 'content_unit_counts': {'iso': 3},
     'importers': [
        {'repo_id': 'test_iso_repo', '_ns': 'repo_importers', 'importer_type_id': 'iso_importer',
         'last_sync': '2013-05-21T12:44:52-04:00', 'scheduled_syncs': [],
         '_id': {'$oid': '519ba0a0b1a8a15a1fcae0b0'},
         'config': {
            importer_constants.KEY_FEED: 'http://pkilambi.fedorapeople.org/test_file_repo/',
            importer_constants.KEY_MAX_DOWNLOADS: 1, importer_constants.KEY_MAX_SPEED: 50000},
         'id': 'iso_importer'}],
     '_id': {'$oid': '519ba0a0b1a8a15a1fcae0af'}, 'id': 'test_iso_repo',
     '_href': '/pulp/api/v2/repositories/test_iso_repo/'},
    # This is an ISO repository that uses SSL certificates. This helps us test that the certificates
    # get scrubbed appropriately by the ISORepoListCommand.
    {'display_name': 'cdn', 'description': None,
     'distributors': [
        {'repo_id': 'cdn', '_ns': 'repo_distributors', 'last_publish': None,
         'auto_publish': False, 'scheduled_publishes': [], 'distributor_type_id': 'iso_distributor',
         '_id': {'$oid': '5163309cb1a8a160d0117efd'},
         'config': {constants.CONFIG_SSL_AUTH_CA_CERT: 'A cert',
                    constants.CONFIG_SERVE_HTTPS: True, constants.CONFIG_SERVE_HTTP: False},
         'id': 'iso_dist'}],
     '_ns': 'repos', 'notes': {'_repo-type': 'iso-repo'}, 'content_unit_counts': {'iso': 5},
     'importers': [
        {'repo_id': 'cdn', '_ns': 'repo_importers', 'importer_type_id': 'iso_importer',
         'last_sync': '2013-04-08T18:12:20-04:00', 'scheduled_syncs': [],
         '_id': {'$oid': '5163309cb1a8a160d0117ef3'},
         'config': {
            importer_constants.KEY_FEED: 'https://cdn.redhat.com/iso',
            importer_constants.KEY_SSL_CA_CERT: 'CA Certificate',
            importer_constants.KEY_SSL_CLIENT_CERT: 'Client Certificate',
            'id': 'cdn', importer_constants.KEY_SSL_CLIENT_KEY: 'Client Key'},
         'id': 'iso_importer'}],
     '_id': {'$oid': '5163309cb1a8a160d0117eea'}, 'id': 'cdn',
     '_href': '/pulp/api/v2/repositories/cdn/'},
    # This is an RPM repository. It should get filtered out by get_repositories(), and it should be
    # shown by get_other_repositories().
    {'display_name': 'zoo', 'description': None,
     'distributors': [
        {'repo_id': 'zoo', '_ns': 'repo_distributors', 'last_publish': '2013-04-30T10:27:31-04:00',
         'auto_publish': True, 'scheduled_publishes': [], 'distributor_type_id': 'yum_distributor',
         '_id': {'$oid': '517fd4c3b1a8a112da54b1ba'},
         'config': {'http': False, 'relative_url': '/repos/pulp/pulp/demo_repos/zoo/',
                    'https': True}, 'id': 'yum_distributor'},
        {'repo_id': 'zoo', '_ns': 'repo_distributors', 'last_publish': None, 'auto_publish': False,
         'scheduled_publishes': [], 'distributor_type_id': 'export_distributor',
         '_id': {'$oid': '517fd4c3b1a8a112da54b1bb'}, 'config': {'http': False, 'https': True},
         'id': 'export_distributor'}],
     '_ns': 'repos', 'notes': {'_repo-type': 'rpm-repo'},
     'content_unit_counts': {'package_group': 2, 'package_category': 1, 'rpm': 32, 'erratum': 4},
     'importers': [
        {'repo_id': 'zoo', '_ns': 'repo_importers', 'importer_type_id': 'yum_importer',
         'last_sync': '2013-04-30T10:27:29-04:00', 'scheduled_syncs': [],
         '_id': {'$oid': '517fd4c3b1a8a112da54b1b9'},
         'config': {'feed_url': 'http://repos.fedorapeople.org/repos/pulp/pulp/demo_repos/zoo/'},
         'id': 'yum_importer'}],
     '_id': {'$oid': '517fd4c3b1a8a112da54b1b8'}, 'id': 'zoo',
     '_href': '/pulp/api/v2/repositories/zoo/'}]


def repo_mock():
    repo = mock.MagicMock()
    repo.repositories = mock.MagicMock()
    response = mock.MagicMock()
    response.response_body = deepcopy(TEST_REPOS)
    repo.repositories.return_value = response
    return repo


class TestISORepoListCommand(rpm_support_base.PulpClientTests):
    """
    Test the ISORepoListCommand class.
    """
    @mock.patch('pulp_rpm.extension.admin.iso.repo_list.ListRepositoriesCommand.__init__',
                side_effect=repo_list.ListRepositoriesCommand.__init__, autospec=True)
    def test___init__(self, list_repo_init):
        """
        Test the __init__() method.
        """
        list_command = repo_list.ISORepoListCommand(self.context)

        list_repo_init.assert_called_once_with(list_command, self.context,
                                               repos_title=_('ISO Repositories'))
        self.assertEqual(list_command.all_repos_cache, None)

    def test__all_repos(self):
        """
        Test the _all_repos() method.
        """
        self.context.server.repo = repo_mock()
        list_command = repo_list.ISORepoListCommand(self.context)
        query_params = {}

        all_repos = list_command._all_repos(query_params)

        # The mock should have been called, and all_repos should just be our TEST_REPOS
        self.context.server.repo.repositories.assert_call_once_with(query_params)
        self.assertEqual(all_repos, TEST_REPOS)

        # The cache should be filled now
        self.assertEqual(list_command.all_repos_cache, TEST_REPOS)

        # Calling it again should not increase the mock's call count since the cache should be used
        list_command._all_repos(query_params)
        self.assertEqual(self.context.server.repo.repositories.call_count, 1)

    def test_get_other_repositories(self):
        """
        Test the get_other_repositories() method.
        """
        self.context.server.repo = repo_mock()
        list_command = repo_list.ISORepoListCommand(self.context)
        query_params = {}

        other_repos = list_command.get_other_repositories(query_params)

        # The only "other repo" is the third test one, the "zoo" RPM repo
        self.assertEqual(other_repos, [TEST_REPOS[2]])

    def test_get_repositories(self):
        """
        Test the get_repositories() method.
        """
        self.context.server.repo = repo_mock()
        list_command = repo_list.ISORepoListCommand(self.context)
        query_params = {}

        iso_repos = list_command.get_repositories(query_params)

        # Let's inspect the repos to make sure they have all the correct properties
        # There should be two ISO repos (cdn and iso). zoo was an RPM repo
        self.assertEqual(len(iso_repos), 2)

        # The first repo should be test_iso_repo, unaltered
        self.assertEqual(iso_repos[0], TEST_REPOS[0])

        # The second repo should be cdn, but the SSL certificates should have been removed
        expected_cdn = deepcopy(TEST_REPOS[1])
        expected_cdn['importers'][0]['config']['feed_ssl_configured'] = 'True'
        expected_cdn['importers'][0]['config'].pop(importer_constants.KEY_SSL_CLIENT_CERT)
        expected_cdn['importers'][0]['config'].pop(importer_constants.KEY_SSL_CLIENT_KEY)
        expected_cdn['importers'][0]['config'].pop(importer_constants.KEY_SSL_CA_CERT)
        expected_cdn['distributors'][0]['config'].pop(constants.CONFIG_SSL_AUTH_CA_CERT)
        expected_cdn['distributors'][0]['config']['repo_protected'] = 'True'
        self.assertEqual(iso_repos[1], expected_cdn)