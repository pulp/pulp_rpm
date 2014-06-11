# -*- coding: utf-8 -*-

from pulp.common import constants as pulp_constants

from pulp_rpm.extensions.admin import repo_list
from pulp_rpm.common import constants, ids
from pulp_rpm.devel.client_base import PulpClientTests


class RpmRepoListCommandTests(PulpClientTests):

    def test_get_repositories(self):
        # Setup
        repos = [
            {'id' : 'matching',
             'notes' : {pulp_constants.REPO_NOTE_TYPE_KEY : constants.REPO_NOTE_RPM,},
             'importers' : [
                 {'config': {}, 'id': ids.YUM_IMPORTER_ID}
             ],
             'distributors' : [
                 {'id' : ids.YUM_DISTRIBUTOR_ID},
                 {'id' : ids.EXPORT_DISTRIBUTOR_ID}
             ]
            },
            {'id' : 'non-rpm-repo',
             'notes' : {}}
        ]
        self.server_mock.request.return_value = 200, repos
        distributor_list = [ids.YUM_DISTRIBUTOR_ID, ids.EXPORT_DISTRIBUTOR_ID]

        # Test
        command = repo_list.RpmRepoListCommand(self.context)
        repos = command.get_repositories({})

        # Verify
        self.assertEqual(1, len(repos))
        self.assertEqual(repos[0]['id'], 'matching')

        # Check that the distributors and importer are present
        self.assertEqual(len(repos[0]['distributors']), 2)
        for x in xrange(0, 2):
            self.assertTrue(repos[0]['distributors'][x]['id'] in distributor_list)
            distributor_list.remove(repos[0]['distributors'][x]['id'])

        self.assertEqual(len(repos[0]['importers']), 1)
        self.assertEqual(repos[0]['importers'][0]['id'], ids.YUM_IMPORTER_ID)

    def test_get_repositories_no_details(self):
        # Setup
        repos = [
            {'id' : 'foo',
             'display_name' : 'bar',
             'notes' : {pulp_constants.REPO_NOTE_TYPE_KEY : constants.REPO_NOTE_RPM,}}
        ]
        self.server_mock.request.return_value = 200, repos

        # Test
        command = repo_list.RpmRepoListCommand(self.context)
        repos = command.get_repositories({})

        # Verify
        self.assertEqual(1, len(repos))
        self.assertEqual(repos[0]['id'], 'foo')
        self.assertTrue('importers' not in repos[0])
        self.assertTrue('distributors' not in repos[0])

    def test_get_repositories_strip_ssl_cert(self):
        # Setup
        repos = [
            {'id' : 'matching',
             'notes' : {pulp_constants.REPO_NOTE_TYPE_KEY : constants.REPO_NOTE_RPM,},
             'importers' : [
                 {'config' : {'ssl_client_cert' : 'foo'}}
             ],
             'distributors' : []
            },
            {'id' : 'non-rpm-repo',
             'notes' : {}}
        ]
        self.server_mock.request.return_value = 200, repos

        # Test
        command = repo_list.RpmRepoListCommand(self.context)
        repos = command.get_repositories({})

        # Verify
        imp_config = repos[0]['importers'][0]['config']
        self.assertTrue('ssl_client_cert' not in imp_config)
        self.assertTrue('feed_ssl_configured' in imp_config)
        self.assertEqual(imp_config['feed_ssl_configured'], 'True')

    def test_get_repositories_strip_ssl_key(self):
        # Setup
        repos = [
            {'id' : 'matching',
             'notes' : {pulp_constants.REPO_NOTE_TYPE_KEY : constants.REPO_NOTE_RPM,},
             'importers' : [
                 {'config' : {'ssl_client_key' : 'foo'}}
             ],
             'distributors' : []
            },
            {'id' : 'non-rpm-repo',
             'notes' : {}}
        ]
        self.server_mock.request.return_value = 200, repos

        # Test
        command = repo_list.RpmRepoListCommand(self.context)
        repos = command.get_repositories({})

        # Verify
        imp_config = repos[0]['importers'][0]['config']
        self.assertTrue('ssl_client_key' not in imp_config)
        self.assertTrue('feed_ssl_configured' in imp_config)
        self.assertEqual(imp_config['feed_ssl_configured'], 'True')

    def test_get_other_repositories(self):
        # Setup
        repos = [
            {'repo_id' : 'matching',
             'notes' : {pulp_constants.REPO_NOTE_TYPE_KEY : constants.REPO_NOTE_RPM,},
             'distributors' : [
                 {'id' : ids.YUM_DISTRIBUTOR_ID},
                 {'id' : ids.EXPORT_DISTRIBUTOR_ID}
             ]
            },
            {'repo_id' : 'non-rpm-repo-1',
             'notes' : {}},
        ]
        self.server_mock.request.return_value = 200, repos

        # Test
        command = repo_list.RpmRepoListCommand(self.context)
        repos = command.get_other_repositories({})

        # Verify
        self.assertEqual(1, len(repos))
        self.assertEqual(repos[0]['repo_id'], 'non-rpm-repo-1')
