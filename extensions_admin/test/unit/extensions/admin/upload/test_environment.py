import mock

from pulp.client.commands.options import OPTION_REPO_ID
from pulp.client.commands.polling import FLAG_BACKGROUND
from pulp.client.commands.repo.upload import FLAG_VERBOSE, UploadCommand

from pulp_rpm.common.ids import TYPE_ID_PKG_ENVIRONMENT
from pulp_rpm.devel.client_base import PulpClientTests
from pulp_rpm.extensions.admin.upload import environment


class CreatePackageEnvironmentCommand(PulpClientTests):
    def setUp(self):
        super(CreatePackageEnvironmentCommand, self).setUp()
        self.upload_manager = mock.MagicMock()
        self.command = environment.CreatePackageEnvironmentCommand(self.context, self.upload_manager)

    def test_structure(self):
        self.assertTrue(isinstance(self.command, UploadCommand))
        self.assertEqual(self.command.name, environment.NAME)
        self.assertEqual(self.command.description, environment.DESC)

        expected_options = set([environment.OPT_ENV_ID, environment.OPT_NAME,
                                environment.OPT_DESCRIPTION, environment.OPT_ORDER,
                                environment.OPT_GROUP, FLAG_VERBOSE, OPTION_REPO_ID, FLAG_BACKGROUND
                                ])
        found_options = set(self.command.options)

        self.assertEqual(expected_options, found_options)

    def test_determine_type_id(self):
        type_id = self.command.determine_type_id(None)
        self.assertEqual(type_id, TYPE_ID_PKG_ENVIRONMENT)

    def test_generate_unit_key(self):
        args = {
            OPTION_REPO_ID.keyword: 'test-repo',
            environment.OPT_ENV_ID.keyword: 'test-env'
        }
        unit_key = self.command.generate_unit_key(None, **args)
        self.assertEqual(unit_key['id'], 'test-env')
        self.assertEqual(unit_key['repo_id'], 'test-repo')

    def test_generate_metadata(self):
        args = {
            environment.OPT_NAME.keyword: 'test-name',
            environment.OPT_DESCRIPTION.keyword: 'test-description',
            environment.OPT_ORDER.keyword: 'test-order',
            environment.OPT_GROUP.keyword: 'test-group',
        }

        metadata = self.command.generate_metadata(None, **args)

        self.assertEqual(metadata['name'], 'test-name')
        self.assertEqual(metadata['description'], 'test-description')
        self.assertEqual(metadata['display_order'], 'test-order')
        self.assertEqual(metadata['group_ids'], 'test-group')
        self.assertEqual(metadata['translated_description'], {})
        self.assertEqual(metadata['translated_name'], {})
        self.assertEqual(metadata['options'], [])
