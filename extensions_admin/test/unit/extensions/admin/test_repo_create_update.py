import os

from pulp.client.commands import options
from pulp.client.commands.repo import cudl, importer_config
from pulp.client.commands.repo.importer_config import ImporterConfigMixin
from pulp.client.extensions.core import TAG_SUCCESS
from pulp.common.compat import json
from pulp.common.plugins import importer_constants as constants

from pulp_rpm.common import ids
from pulp_rpm.devel.client_base import PulpClientTests
from pulp_rpm.extensions.admin import repo_options
from pulp_rpm.extensions.admin import repo_create_update


DATA_DIR = os.path.abspath(os.path.dirname(__file__)) + '/../../data/'


class RpmRepoCreateCommandTests(PulpClientTests):

    def setUp(self):
        super(RpmRepoCreateCommandTests, self).setUp()

        self.options_bundle = importer_config.OptionsBundle()

    def test_create_structure(self):
        command = repo_create_update.RpmRepoCreateCommand(self.context)

        self.assertTrue(isinstance(command, ImporterConfigMixin))

        # Ensure the required option groups
        found_group_names = set([o.name for o in command.option_groups])
        self.assertTrue(repo_options.NAME_AUTH in found_group_names)
        self.assertTrue(repo_options.NAME_PUBLISHING in found_group_names)

        # Ensure the correct method is wired up
        self.assertEqual(command.method, command.run)

        # Ensure the correct metadata
        self.assertEqual(command.name, 'create')
        self.assertEqual(command.description, cudl.DESC_CREATE)

    def test_run(self):
        # Setup
        cert_file = os.path.join(DATA_DIR, 'cert.crt')
        cert_key = os.path.join(DATA_DIR, 'cert.key')
        ca_cert = os.path.join(DATA_DIR, 'valid_ca.crt')
        gpg_key = os.path.join(DATA_DIR, 'cert.key') # contents shouldn't matter

        data = {
            options.OPTION_REPO_ID.keyword : 'test-repo',
            options.OPTION_NAME.keyword : 'Test Name',
            options.OPTION_DESCRIPTION.keyword : 'Test Description',
            options.OPTION_NOTES.keyword : {'a' : 'a'},
            self.options_bundle.opt_feed.keyword : 'http://localhost',
            self.options_bundle.opt_validate.keyword : True,
            self.options_bundle.opt_remove_missing.keyword : True,
            self.options_bundle.opt_retain_old_count.keyword : 2,
            self.options_bundle.opt_proxy_host.keyword : 'http://localhost',
            self.options_bundle.opt_proxy_port.keyword : 80,
            self.options_bundle.opt_proxy_user.keyword : 'user',
            self.options_bundle.opt_proxy_pass.keyword : 'pass',
            self.options_bundle.opt_max_speed.keyword : 1024,
            self.options_bundle.opt_max_downloads.keyword : 8,
            self.options_bundle.opt_feed_ca_cert.keyword : ca_cert,
            self.options_bundle.opt_verify_feed_ssl.keyword : True,
            self.options_bundle.opt_feed_cert.keyword : cert_file,
            self.options_bundle.opt_feed_key.keyword : cert_key,
            repo_options.OPT_SKIP.keyword : [ids.TYPE_ID_RPM],
            repo_options.OPT_RELATIVE_URL.keyword : '/repo',
            repo_options.OPT_SERVE_HTTP.keyword : True,
            repo_options.OPT_SERVE_HTTPS.keyword : True,
            repo_options.OPT_CHECKSUM_TYPE.keyword : 'sha256',
            repo_options.OPT_GPG_KEY.keyword : gpg_key,
            repo_options.OPT_HOST_CA.keyword : ca_cert,
            repo_options.OPT_AUTH_CA.keyword : ca_cert,
            repo_options.OPT_AUTH_CERT.keyword : cert_file,
        }

        self.server_mock.request.return_value = 201, {}

        # Test
        command = repo_create_update.RpmRepoCreateCommand(self.context)
        command.run(**data)

        # Verify
        self.assertEqual(1, self.server_mock.request.call_count)

        body = self.server_mock.request.call_args[0][2]
        body = json.loads(body)

        self.assertEqual(body['display_name'], 'Test Name')
        self.assertEqual(body['description'], 'Test Description')
        self.assertEqual(body['notes'], {'_repo-type' : 'rpm-repo', 'a' : 'a'})

        self.assertEqual(ids.TYPE_ID_IMPORTER_YUM, body['importer_type_id'])
        importer_config = body['importer_config']
        self.assertEqual(importer_config[constants.KEY_FEED], 'http://localhost')
        self.assertTrue(importer_config[constants.KEY_SSL_CA_CERT] is not None)
        self.assertTrue(importer_config[constants.KEY_SSL_CLIENT_CERT] is not None)
        self.assertTrue(importer_config[constants.KEY_SSL_CLIENT_KEY] is not None)
        self.assertEqual(importer_config[constants.KEY_SSL_VALIDATION], True)
        self.assertEqual(importer_config[constants.KEY_VALIDATE], True)
        self.assertEqual(importer_config[constants.KEY_PROXY_HOST], 'http://localhost')
        self.assertEqual(importer_config[constants.KEY_PROXY_PORT], 80)
        self.assertEqual(importer_config[constants.KEY_PROXY_USER], 'user')
        self.assertEqual(importer_config[constants.KEY_PROXY_PASS], 'pass')
        self.assertEqual(importer_config[constants.KEY_MAX_SPEED], 1024)
        self.assertEqual(importer_config[constants.KEY_MAX_DOWNLOADS], 8)
        self.assertEqual(importer_config[repo_create_update.CONFIG_KEY_SKIP], [ids.TYPE_ID_RPM])
        self.assertEqual(importer_config[constants.KEY_UNITS_REMOVE_MISSING], True)
        self.assertEqual(importer_config[constants.KEY_UNITS_RETAIN_OLD_COUNT], 2)

        # The API will be changing to be a dict for each distributor, not a
        # list. This code will have to change to look up the parts by key
        # instead of index.

        yum_distributor = body['distributors'][0]
        self.assertEqual(ids.TYPE_ID_DISTRIBUTOR_YUM, yum_distributor['distributor_type_id'])
        self.assertEqual(True, yum_distributor['auto_publish'])
        self.assertEqual(ids.YUM_DISTRIBUTOR_ID, yum_distributor['distributor_id'])

        yum_config = yum_distributor['distributor_config']
        self.assertEqual(yum_config['relative_url'], '/repo')
        self.assertEqual(yum_config['http'], True)
        self.assertEqual(yum_config['https'], True)
        self.assertTrue(yum_config['gpgkey'] is not None)
        self.assertEqual(yum_config['checksum_type'], 'sha256')
        self.assertTrue(yum_config['auth_ca'] is not None)
        self.assertTrue(yum_config['auth_cert'] is not None)
        self.assertTrue(yum_config['https_ca'] is not None)
        self.assertEqual(yum_config['skip'], [ids.TYPE_ID_RPM])

        iso_distributor = body['distributors'][1]
        self.assertEqual(ids.TYPE_ID_DISTRIBUTOR_EXPORT, iso_distributor['distributor_id'])
        self.assertEqual(False, iso_distributor['auto_publish'])
        self.assertEqual(ids.EXPORT_DISTRIBUTOR_ID, iso_distributor['distributor_id'])

        iso_config = iso_distributor['distributor_config']
        self.assertEqual(iso_config['http'], True)
        self.assertEqual(iso_config['https'], True)
        self.assertEqual(iso_config['skip'], [ids.TYPE_ID_RPM])

        self.assertEqual([TAG_SUCCESS], self.prompt.get_write_tags())

    def test_run_through_cli(self):
        # Setup
        self.server_mock.request.return_value = 201, {}

        # Test
        command = repo_create_update.RpmRepoCreateCommand(self.context)
        self.cli.add_command(command)
        self.cli.run("create --repo-id r --validate true".split())

        # Verify
        self.assertEqual(1, self.server_mock.request.call_count)

        body = self.server_mock.request.call_args[0][2]
        body = json.loads(body)

        self.assertEqual(body['id'], 'r')
        self.assertEqual(body['importer_config'][constants.KEY_VALIDATE], True) # not the string "true"

    def test_process_relative_url_with_feed(self):
        # Setup
        repo_id = 'feed-repo'
        importer_config = {constants.KEY_FEED : 'http://localhost/foo/bar/baz'}
        distributor_config = {} # will be populated in this call
        command = repo_create_update.RpmRepoCreateCommand(self.context)

        # Test
        command.process_relative_url(repo_id, importer_config, distributor_config)

        # Verify
        self.assertTrue('relative_url' in distributor_config)
        self.assertEqual(distributor_config['relative_url'], '/foo/bar/baz')

    def test_process_relative_url_no_feed(self):
        # Setup
        repo_id = 'no-feed-repo'
        importer_config = {}
        distributor_config = {} # will be populated in this call
        command = repo_create_update.RpmRepoCreateCommand(self.context)

        # Test
        command.process_relative_url(repo_id, importer_config, distributor_config)

        # Verify
        self.assertTrue('relative_url' in distributor_config)
        self.assertEqual(distributor_config['relative_url'], repo_id)

    def test_process_relative_url_specified(self):
        # Setup
        repo_id = 'specified'
        importer_config = {}
        distributor_config = {'relative_url' : 'wombat'}
        command = repo_create_update.RpmRepoCreateCommand(self.context)

        # Test
        command.process_relative_url(repo_id, importer_config, distributor_config)

        # Verify
        self.assertTrue('relative_url' in distributor_config)
        self.assertEqual(distributor_config['relative_url'], 'wombat')


class RpmRepoUpdateCommandTests(PulpClientTests):

    def setUp(self):
        super(RpmRepoUpdateCommandTests, self).setUp()
        self.options_bundle = importer_config.OptionsBundle()

    def test_create_structure(self):
        command = repo_create_update.RpmRepoUpdateCommand(self.context)

        self.assertTrue(isinstance(command, ImporterConfigMixin))

        # Ensure the required option groups
        found_group_names = set([o.name for o in command.option_groups])
        self.assertTrue(repo_options.NAME_AUTH in found_group_names)
        self.assertTrue(repo_options.NAME_PUBLISHING in found_group_names)

        # Ensure the correct method is wired up
        self.assertEqual(command.method, command.run)

        # Ensure the correct metadata
        self.assertEqual(command.name, 'update')
        self.assertEqual(command.description, cudl.DESC_UPDATE)

    def test_run_202(self):
        # Setup
        data = {
            options.OPTION_REPO_ID.keyword : 'test-repo',
            options.OPTION_NAME.keyword : 'Test Name',
            options.OPTION_DESCRIPTION.keyword : 'Test Description',
            options.OPTION_NOTES.keyword : {'b' : 'b'},
            self.options_bundle.opt_feed.keyword : 'http://localhost',
            repo_options.OPT_SERVE_HTTP.keyword : True,
            repo_options.OPT_SERVE_HTTPS.keyword : True,
            repo_options.OPT_SKIP.keyword : [ids.TYPE_ID_RPM],
            }

        self.server_mock.request.return_value = 202, {}

        # Test
        command = repo_create_update.RpmRepoUpdateCommand(self.context)
        command.run(**data)

        # Verify that things at least didn't blow up, which they were for BZ 1096931
        self.assertEqual(1, self.server_mock.request.call_count)

    def test_run(self):
        # Setup
        data = {
            options.OPTION_REPO_ID.keyword : 'test-repo',
            options.OPTION_NAME.keyword : 'Test Name',
            options.OPTION_DESCRIPTION.keyword : 'Test Description',
            options.OPTION_NOTES.keyword : {'b' : 'b'},
            self.options_bundle.opt_feed.keyword : 'http://localhost',
            repo_options.OPT_SERVE_HTTP.keyword : True,
            repo_options.OPT_SERVE_HTTPS.keyword : True,
            repo_options.OPT_SKIP.keyword : [ids.TYPE_ID_RPM],
        }

        self.server_mock.request.return_value = 200, {}

        # Test
        command = repo_create_update.RpmRepoUpdateCommand(self.context)
        command.run(**data)

        # Verify
        self.assertEqual(1, self.server_mock.request.call_count)

        body = self.server_mock.request.call_args[0][2]
        body = json.loads(body)

        delta = body['delta']
        self.assertEqual(delta['display_name'], 'Test Name')
        self.assertEqual(delta['description'], 'Test Description')
        self.assertEqual(delta['notes'], {'b' : 'b'})

        yum_imp_config = body['importer_config']
        self.assertEqual(yum_imp_config[constants.KEY_FEED], 'http://localhost')
        self.assertEqual(yum_imp_config[repo_create_update.CONFIG_KEY_SKIP], [ids.TYPE_ID_RPM])

        yum_dist_config = body['distributor_configs'][ids.YUM_DISTRIBUTOR_ID]
        self.assertEqual(yum_dist_config['http'], True)
        self.assertEqual(yum_dist_config['https'], True)
        self.assertEqual(yum_dist_config['skip'],  [ids.TYPE_ID_RPM])
        
        iso_dist_config = body['distributor_configs'][ids.EXPORT_DISTRIBUTOR_ID]
        self.assertEqual(iso_dist_config['http'], True)
        self.assertEqual(iso_dist_config['https'], True)
        self.assertEqual(iso_dist_config['skip'],  [ids.TYPE_ID_RPM])

    def test_run_through_cli(self):
        """
        See the note in test_run_through_cli under the create tests for
        more info.
        """

        # Setup
        self.server_mock.request.return_value = 201, {}

        # Test
        command = repo_create_update.RpmRepoUpdateCommand(self.context)
        self.cli.add_command(command)
        self.cli.run("update --repo-id r --validate true".split())

        # Verify
        self.assertEqual(1, self.server_mock.request.call_count)

        body = self.server_mock.request.call_args[0][2]
        body = json.loads(body)

        self.assertEqual(body['importer_config'][constants.KEY_VALIDATE], True) # not the string "true"

    def test_remove_skip_types(self):
        # Setup
        self.server_mock.request.return_value = 201, {}

        # Test
        command = repo_create_update.RpmRepoUpdateCommand(self.context)
        self.cli.add_command(command)
        self.cli.run("update --repo-id r --skip".split() + [''])

        # Verify
        self.assertEqual(1, self.server_mock.request.call_count)

        body = self.server_mock.request.call_args[0][2]
        body = json.loads(body)

        self.assertEqual(body['importer_config']['type_skip_list'], None)
        self.assertEqual(body['distributor_configs']['yum_distributor']['skip'], None)
        self.assertEqual(body['distributor_configs']['export_distributor']['skip'], None)

