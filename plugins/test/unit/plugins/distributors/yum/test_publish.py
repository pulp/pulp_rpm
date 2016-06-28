from cStringIO import StringIO
import datetime
import os
import shutil
import tempfile
from xml.etree import cElementTree as ET

from pulp.common.compat import json, unittest
from pulp.common.plugins import reporting_constants
from pulp.devel.unit.util import touch, compare_dict
from pulp.plugins.conduits.repo_publish import RepoPublishConduit
from pulp.plugins.config import PluginCallConfiguration
from pulp.plugins.model import Repository, Unit
from pulp.plugins.util.publish_step import PublishStep, CreatePulpManifestStep
from pulp.server import constants as server_constants
from pulp.server.db import model
from pulp.server.exceptions import InvalidValue, PulpCodedException
import isodate
import mock
import pulp.server.managers.factory as manager_factory

from pulp_rpm.common import constants
from pulp_rpm.common.ids import (
    TYPE_ID_PKG_GROUP, TYPE_ID_PKG_CATEGORY, TYPE_ID_DISTRO, TYPE_ID_DRPM, TYPE_ID_RPM,
    TYPE_ID_YUM_REPO_METADATA_FILE, YUM_DISTRIBUTOR_ID, EXPORT_DISTRIBUTOR_ID)
from pulp_rpm.devel.skip import skip_broken
from pulp_rpm.plugins.distributors.yum import configuration, publish


DATA_DIR = os.path.join(os.path.dirname(__file__), '../../../../data/')


class BaseYumDistributorPublishTests(unittest.TestCase):

    def setUp(self):
        super(BaseYumDistributorPublishTests, self).setUp()

        manager_factory.initialize()

        self.working_dir = tempfile.mkdtemp(prefix='working_')
        self.published_dir = tempfile.mkdtemp(prefix='published_')
        self.master_dir = os.path.join(self.published_dir, 'master')

        self.repo_id = 'yum-distributor-publish-test'
        self.publisher = None

        # make sure the master dir is somemplace we can actually write to
        self._original_master_dir = configuration.MASTER_PUBLISH_DIR
        configuration.MASTER_PUBLISH_DIR = self.master_dir

    def tearDown(self):
        configuration.MASTER_PUBLISH_DIR = self._original_master_dir

        for directory in (self.published_dir, self.master_dir, self.working_dir):
            if os.path.exists(directory):
                shutil.rmtree(directory, ignore_errors=True)

        self.publisher = None

    def _init_publisher(self):

        repo = Repository(self.repo_id, working_dir=self.working_dir)
        self.repo = repo

        conduit = RepoPublishConduit(repo.id, YUM_DISTRIBUTOR_ID)
        conduit.last_publish = mock.Mock(return_value=None)
        conduit.get_repo_scratchpad = mock.Mock(return_value={})

        config_defaults = {'http': True,
                           'https': True,
                           'relative_url': None,
                           'http_publish_dir': os.path.join(self.published_dir, 'http'),
                           'https_publish_dir': os.path.join(self.published_dir, 'https')}
        config = PluginCallConfiguration(None, None)
        config.default_config.update(config_defaults)

        self.publisher = publish.BaseYumRepoPublisher(repo, conduit, config, YUM_DISTRIBUTOR_ID,
                                                      working_dir=self.working_dir)
        self.publisher.get_checksum_type = mock.Mock(return_value=None)

        # mock out the repomd_file_context, so _publish_<step> can be called
        # outside of the publish() method
        self.publisher.repomd_file_context = mock.MagicMock()
        self.publisher.all_steps = mock.MagicMock()

    def _copy_to_master(self):
        # ensure the master publish directory exists
        master_dir = os.path.join(self.master_dir, self.repo_id, self.publisher.timestamp)
        shutil.copytree(os.path.join(self.working_dir, 'content'), master_dir)

    @staticmethod
    def _touch(path):

        parent = os.path.dirname(path)

        if not os.path.exists(parent):
            os.makedirs(parent)

        with open(path, 'w'):
            pass

    def _generate_rpm(self, name):

        unit_key = {'name': name,
                    'epoch': 0,
                    'version': 1,
                    'release': 0,
                    'arch': 'noarch',
                    'checksumtype': 'sha256',
                    'checksum': '1234657890'}

        unit_metadata = {'repodata': {'filelists': 'FILELISTS',
                                      'other': 'OTHER',
                                      'primary': 'PRIMARY'}}

        storage_path = os.path.join(self.working_dir, 'content', name)
        self._touch(storage_path)

        return Unit(TYPE_ID_RPM, unit_key, unit_metadata, storage_path)


class BaseYumDistributorPublishStepTests(BaseYumDistributorPublishTests):

    def setUp(self):
        super(BaseYumDistributorPublishStepTests, self).setUp()
        self._init_publisher()

    def tearDown(self):
        super(BaseYumDistributorPublishStepTests, self).tearDown()

    def add_mock_context_to_step(self, step):
        step.get_step = mock.Mock()


class BaseYumRepoPublisherTests(BaseYumDistributorPublishTests):

    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.GenerateSqliteForRepoStep')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.PublishCompsStep')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._build_final_report')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.PublishMetadataStep')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.PublishErrataStep')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.PublishDrpmStep')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.PublishRpmStep')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.PublishDistributionStep')
    def test_publish(self, mock_publish_distribution, mock_publish_rpms, mock_publish_drpms,
                     mock_publish_errata, mock_publish_metadata,
                     mock_build_final_report, mock_publish_comps,
                     mock_generate_sqlite):

        self._init_publisher()
        self.publisher.repo.content_unit_counts = {}
        self.publisher.process_lifecycle()

        mock_publish_distribution.assert_called_once_with()
        mock_publish_rpms.assert_called_once_with(mock_publish_distribution(),
                                                  repo_content_unit_q=None)
        mock_publish_drpms.assert_called_once_with(mock_publish_distribution(),
                                                   repo_content_unit_q=None)
        mock_publish_errata.assert_called_once_with()
        mock_publish_metadata.assert_called_once_with()
        mock_build_final_report.assert_called_once()
        mock_publish_comps.assert_called_once_with()
        mock_generate_sqlite.assert_called_once_with(self.working_dir)

    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.configuration.get_repo_checksum_type')
    def test_get_checksum_type(self, mock_get_checksum):
        mock_get_checksum.return_value = 'sha1'
        self._init_publisher()

        publisher = publish.BaseYumRepoPublisher(self.publisher.get_repo(),
                                                 self.publisher.get_conduit(),
                                                 self.publisher.get_config(),
                                                 YUM_DISTRIBUTOR_ID,
                                                 working_dir=self.working_dir)

        result = publisher.get_checksum_type()
        self.assertEquals('sha1', result)
        self.assertEquals('sha1', publisher.checksum_type)


@mock.patch('pulp_rpm.plugins.distributors.yum.publish.export_utils.create_date_range_filter')
class ExportRepoPublisherTests(unittest.TestCase):
    """
    Test that the export steps are correct.
    """
    def setUp(self):
        repo = model.Repository(repo_id='foo')
        self.transfer_repo = repo.to_transfer_repo()
        self.filter = 'some filter'
        self.working_dir = 'working_dir'
        self.export_dir = 'export_dir'
        self.content_dir = os.path.join(self.working_dir, 'scratch')
        self.realized_dir = os.path.join(self.working_dir, 'realized')
        self.output_dir = os.path.join(self.working_dir, 'output')
        self.export_target_dir = os.path.join(self.export_dir, repo.repo_id)
        self.iso_target_dir = os.path.join(self.realized_dir, repo.repo_id)
        self.master_dir = os.path.join(configuration.MASTER_PUBLISH_DIR, YUM_DISTRIBUTOR_ID,
                                       repo.repo_id)
        self.conduit = RepoPublishConduit(repo.repo_id, YUM_DISTRIBUTOR_ID)

    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.GenerateListingFileStep')
    @mock.patch('pulp.plugins.util.publish_step.CopyDirectoryStep')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.PublishErrataStepIncremental')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.PublishRpmAndDrpmStepIncremental')
    def test_export_init_export_dir(self, mock_rpm_incremental, mock_errata_incremental,
                                    mock_copydir, mock_listing, mock_export_utils):
        """
        Verify the publish steps when the export directory is specified.
        """
        mock_export_utils.return_value = self.filter
        config = PluginCallConfiguration(None,
                                         {constants.EXPORT_DIRECTORY_KEYWORD: self.export_dir})
        publish.ExportRepoPublisher(self.transfer_repo, self.conduit, config, YUM_DISTRIBUTOR_ID,
                                    working_dir=self.working_dir)

        mock_rpm_incremental.assert_called_once_with(repo_content_unit_q=mock_export_utils())
        mock_errata_incremental.assert_called_once_with(repo_content_unit_q=mock_export_utils())
        mock_copydir.assert_called_once_with(self.working_dir, self.export_target_dir)
        mock_listing.assert_called_once_with(self.export_dir, self.export_target_dir)

    @mock.patch('pulp.plugins.util.publish_step.CreatePulpManifestStep')
    @mock.patch('pulp.plugins.util.publish_step.AtomicDirectoryPublishStep')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.CreateIsoStep')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.GenerateListingFileStep')
    @mock.patch('pulp.plugins.util.publish_step.CopyDirectoryStep')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.PublishErrataStepIncremental')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.PublishRpmAndDrpmStepIncremental')
    def test_export_init_iso(self, mock_rpm_incremental, mock_errata_incremental, mock_copydir,
                             mock_listing, mock_create_iso, mock_atomic_publish, mock_manifest,
                             mock_export_utils):
        """
        Verify the publish steps when the export directory is not specified.
        """
        mock_export_utils.return_value = self.filter
        config = PluginCallConfiguration(None, None)
        publish.ExportRepoPublisher(self.transfer_repo, self.conduit, config, YUM_DISTRIBUTOR_ID,
                                    working_dir=self.working_dir)
        mock_rpm_incremental.assert_called_once_with(repo_content_unit_q=mock_export_utils())
        mock_errata_incremental.assert_called_once_with(repo_content_unit_q=mock_export_utils())
        mock_copydir.assert_called_once_with(self.content_dir, self.iso_target_dir)
        mock_listing.assert_called_once_with(self.realized_dir, self.iso_target_dir)
        mock_create_iso.assert_called_once_with(self.realized_dir, self.output_dir)
        mock_atomic_publish.assert_called_once_with(self.output_dir, [], self.master_dir)
        self.assertEqual(mock_manifest.call_count, 0)

    @mock.patch('pulp.plugins.util.publish_step.CreatePulpManifestStep')
    def test_export_create_manifest(self, mock_manifest, mock_export_utils):
        """
        Test that the manifest step is added when the manifest flag is set to True.
        """
        mock_export_utils.return_value = self.filter
        config = PluginCallConfiguration({constants.CREATE_PULP_MANIFEST: True}, None)
        publish.ExportRepoPublisher(self.transfer_repo, self.conduit, config, YUM_DISTRIBUTOR_ID,
                                    working_dir=self.working_dir)
        mock_manifest.assert_called_once_with(self.output_dir)

    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.PublishErrataStep')
    def test_export_incremental_repomd(self, mock_errata, mock_export_utils):
        """
        Test that the errata step is called with filters when the incremental_export_repomd flag
        is set to True.
        """
        mock_export_utils.return_value = self.filter
        config = PluginCallConfiguration(None, {constants.INCREMENTAL_EXPORT_REPOMD_KEYWORD: True})
        publish.ExportRepoPublisher(self.transfer_repo, self.conduit, config, YUM_DISTRIBUTOR_ID,
                                    working_dir=self.working_dir)
        mock_errata.assert_called_once_with(repo_content_unit_q=mock_export_utils())


class ExportRepoGroupPublisherTests(BaseYumDistributorPublishStepTests):

    @skip_broken
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.BaseYumRepoPublisher.get_working_dir')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.model.Repository.objects')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.export_utils.create_date_range_filter')
    def test_init_with_date_and_export_dir(self, mock_export_utils, mock_repo_qs, m_wd):
        mock_export_utils.return_value = 'foo'
        export_dir = 'flux'
        config = PluginCallConfiguration(None, {constants.EXPORT_DIRECTORY_KEYWORD: export_dir})
        repo_group = mock.Mock(repo_ids=['foo', 'bar'],
                               working_dir=self.working_dir)
        foo = model.Repository(repo_id='foo', display_name='foo', description='description',
                               notes={'_repo-type': 'rpm-repo'}, content_unit_counts={'rpm': 1})

        bar = model.Repository(repo_id='bar', display_name='bar', description='description',
                               notes={'_repo-type': 'puppet'},
                               content_unit_counts={'puppet-module': 1})
        mock_repo_qs.return_value = [foo, bar]

        step = publish.ExportRepoGroupPublisher(repo_group,
                                                self.publisher.get_conduit(),
                                                config,
                                                EXPORT_DISTRIBUTOR_ID)

        self.assertTrue(isinstance(step.children[0], publish.ExportRepoPublisher))
        self.assertEquals(len(step.children), 1)

        self.assertEquals(step.children[0].children[0].association_filters, 'foo')
        self.assertEquals(step.children[0].children[1].association_filters, 'foo')

    @skip_broken
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.model.Repository.objects')
    def test_init_with_empty_repos_export_dir(self, mock_repo_qs):
        export_dir = 'flux'
        config = PluginCallConfiguration(None, {constants.EXPORT_DIRECTORY_KEYWORD: export_dir})
        repo_group = mock.Mock(repo_ids=[],
                               working_dir=self.working_dir)
        mock_repo_qs.return_value = []
        step = publish.ExportRepoGroupPublisher(repo_group,
                                                self.publisher.get_conduit(),
                                                config,
                                                EXPORT_DISTRIBUTOR_ID)

        self.assertTrue(isinstance(step.children[0], publish.GenerateListingFileStep))
        self.assertEquals(len(step.children), 1)

    @skip_broken
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.model.Repository.objects')
    def test_init_with_empty_repos_iso(self, mock_repo_qs):
        config = PluginCallConfiguration(None, {})
        repo_group = mock.Mock(repo_ids=[],
                               working_dir=self.working_dir)
        mock_repo_qs.return_value = []
        step = publish.ExportRepoGroupPublisher(repo_group,
                                                self.publisher.get_conduit(),
                                                config,
                                                EXPORT_DISTRIBUTOR_ID)
        self.assertTrue(isinstance(step.children[0], publish.GenerateListingFileStep))
        self.assertTrue(isinstance(step.children[1], publish.CreateIsoStep))
        self.assertTrue(isinstance(step.children[2], publish.AtomicDirectoryPublishStep))
        self.assertEquals(len(step.children), 3)

    @skip_broken
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.BaseYumRepoPublisher.get_working_dir')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.model.Repository.objects')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.export_utils.create_date_range_filter')
    def test_init_with_date_and_iso(self, mock_export_utils, mock_repo_qs, mock_wd):
        mock_export_utils.return_value = 'foo'
        config = PluginCallConfiguration(None, {})
        repo_group = mock.Mock(repo_ids=['foo', 'bar'],
                               working_dir=self.working_dir)
        foo = model.Repository(repo_id='foo', display_name='foo', description='description',
                               notes={'_repo-type': 'rpm-repo'}, content_unit_counts={'rpm': 1})

        mock_repo_qs.return_value = [foo]
        step = publish.ExportRepoGroupPublisher(repo_group,
                                                self.publisher.get_conduit(),
                                                config,
                                                EXPORT_DISTRIBUTOR_ID)

        self.assertTrue(isinstance(step.children[0], publish.ExportRepoPublisher))
        self.assertTrue(isinstance(step.children[1], publish.CreateIsoStep))
        self.assertTrue(isinstance(step.children[2], publish.AtomicDirectoryPublishStep))
        self.assertEquals(len(step.children), 3)

        self.assertEquals(step.children[0].children[0].association_filters, 'foo')
        self.assertEquals(step.children[0].children[1].association_filters, 'foo')

    @skip_broken
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.BaseYumRepoPublisher.get_working_dir')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.model.Repository.objects')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.export_utils.create_date_range_filter')
    def test_init_with_create_manifest(self, mock_export_utils, mock_repo_qs, m_wd):
        mock_export_utils.return_value = 'foo'
        config = PluginCallConfiguration(None, {constants.CREATE_PULP_MANIFEST: True})
        repo_group = mock.Mock(repo_ids=['foo', 'bar'],
                               working_dir=self.working_dir)
        mock_repo = mock.MagicMock(id='foo', display_name='foo', description='description',
                                   notes={'_repo-type': 'rpm-repo'}, content_unit_counts={'rpm': 1})
        mock_transfer = mock.MagicMock()
        mock_repo.to_transfer_repo.return_value = mock_transfer
        mock_repo_qs.return_value = [mock_repo]
        step = publish.ExportRepoGroupPublisher(repo_group,
                                                self.publisher.get_conduit(),
                                                config,
                                                EXPORT_DISTRIBUTOR_ID)

        self.assertTrue(isinstance(step.children[-2], CreatePulpManifestStep))


class PublisherTests(BaseYumDistributorPublishStepTests):

    @skip_broken
    def test_init(self):
        config = PluginCallConfiguration(None, {
            constants.PUBLISH_HTTPS_KEYWORD: True,
            constants.PUBLISH_HTTP_KEYWORD: True})
        step = publish.Publisher(self.publisher.get_repo(),
                                 self.publisher.get_conduit(),
                                 config, YUM_DISTRIBUTOR_ID, working_dir=self.working_dir)
        self.assertTrue(isinstance(step.children[-1], publish.GenerateListingFileStep))
        self.assertTrue(isinstance(step.children[-2], publish.GenerateListingFileStep))
        self.assertTrue(isinstance(step.children[-3], publish.AtomicDirectoryPublishStep))
        atomic_publish = step.children[-3]
        repo = self.publisher.get_repo()
        target_publish_locations = [
            ['/', os.path.join(configuration.get_https_publish_dir(config),
                               configuration.get_repo_relative_path(repo, config))],
            ['/', os.path.join(configuration.get_http_publish_dir(config),
                               configuration.get_repo_relative_path(repo, config))]
        ]
        self.assertEquals(atomic_publish.publish_locations, target_publish_locations)

        # verify that listing file steps got the correct arguments
        http_step = step.children[-1]
        https_step = step.children[-2]
        self.assertEqual(http_step.target_dir, target_publish_locations[1][1])
        self.assertEqual(http_step.root_dir, configuration.get_http_publish_dir(config))
        self.assertEqual(https_step.target_dir, target_publish_locations[0][1])
        self.assertEqual(https_step.root_dir, configuration.get_https_publish_dir(config))

    @skip_broken
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.configuration.get_https_publish_dir')
    def test_init_incremental_publish_from_https_dir(self, mock_get_https_dir):
        config = PluginCallConfiguration(None, {
            constants.PUBLISH_HTTPS_KEYWORD: True,
            constants.PUBLISH_HTTP_KEYWORD: False})
        # Set the last publish time
        self.publisher.get_conduit().last_publish = \
            mock.Mock(return_value=datetime.datetime.now(tz=isodate.UTC))

        # set up the previous publish directory
        repo = self.publisher.get_repo()
        mock_get_https_dir.return_value = self.working_dir
        specific_master = os.path.join(self.working_dir,
                                       configuration.get_repo_relative_path(repo, config))
        os.makedirs(specific_master)

        step = publish.Publisher(self.publisher.get_repo(),
                                 self.publisher.get_conduit(),
                                 config, YUM_DISTRIBUTOR_ID, working_dir=self.working_dir)
        self.assertTrue(isinstance(step.children[0], publish.CopyDirectoryStep))

    @skip_broken
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.configuration.get_https_publish_dir')
    def test_init_incremental_publish_blocked_by_deletion(self, mock_get_https_dir):
        config = PluginCallConfiguration(None, {
            constants.PUBLISH_HTTPS_KEYWORD: True,
            constants.PUBLISH_HTTP_KEYWORD: False})
        # Set the last publish & delete time
        delete_time = datetime.datetime.now(tz=isodate.UTC)
        self.publisher.get_repo().last_unit_removed = delete_time
        last_publish = delete_time + datetime.timedelta(hours=-1)
        self.publisher.get_conduit().last_publish = \
            mock.Mock(return_value=last_publish)

        # set up the previous publish directory
        repo = self.publisher.get_repo()
        mock_get_https_dir.return_value = self.working_dir
        specific_master = os.path.join(self.working_dir,
                                       configuration.get_repo_relative_path(repo, config))
        os.makedirs(specific_master)

        step = publish.Publisher(self.publisher.get_repo(),
                                 self.publisher.get_conduit(),
                                 config, YUM_DISTRIBUTOR_ID, working_dir=self.working_dir)
        self.assertFalse(isinstance(step.children[0], publish.CopyDirectoryStep))

    @skip_broken
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.configuration.get_http_publish_dir')
    def test_init_incremental_publish_from_http_dir(self, mock_get_http_dir):
        config = PluginCallConfiguration(None, {
            constants.PUBLISH_HTTPS_KEYWORD: False,
            constants.PUBLISH_HTTP_KEYWORD: True})
        # Set the last publish time
        self.publisher.get_conduit().last_publish = \
            mock.Mock(return_value=datetime.datetime.now(tz=isodate.UTC))

        # set up the previous publish directory
        repo = self.publisher.get_repo()
        mock_get_http_dir.return_value = self.working_dir
        specific_master = os.path.join(self.working_dir,
                                       configuration.get_repo_relative_path(repo, config))
        os.makedirs(specific_master)

        step = publish.Publisher(self.publisher.get_repo(),
                                 self.publisher.get_conduit(),
                                 config, YUM_DISTRIBUTOR_ID, working_dir=self.working_dir)
        self.assertTrue(isinstance(step.children[0], publish.CopyDirectoryStep))


class PublishRpmAndDrpmStepIncrementalTests(BaseYumDistributorPublishStepTests):

    @skip_broken
    def test_process_unit(self):
        step = publish.PublishRpmAndDrpmStepIncremental()
        self.publisher.add_child(step)
        unit_key = {'name': 'foo', 'version': '1', 'release': '2', 'arch': 'flux'}
        metadata = {'filename': 'bar.txt', 'repodata': 'baz', '_test': 'hidden'}
        storage_path = os.path.join(self.working_dir, 'foo')
        touch(storage_path)
        test_unit = Unit('foo_type', unit_key, metadata.copy(), storage_path)

        step.process_main(test_unit)
        modified_metadata = metadata.copy()
        modified_metadata.pop('repodata')
        modified_metadata.pop('_test')
        modified_metadata[server_constants.PULP_USER_METADATA_FIELDNAME] = {}
        unit_file = os.path.join(self.working_dir, 'foo-1-2.flux.json')
        self.assertTrue(os.path.exists(unit_file))
        with open(unit_file) as file_handle:
            loaded = json.load(file_handle)
            compare_dict(loaded, {
                'unit_key': unit_key, 'unit_metadata': modified_metadata
            })


class PublishErrataStepIncrementalTests(BaseYumDistributorPublishStepTests):

    @skip_broken
    def test_process_unit(self):
        step = publish.PublishErrataStepIncremental()
        self.publisher.add_child(step)
        unit_key = {'id': 'foo'}
        metadata = {'filename': 'bar.txt', '_test': 'hidden'}
        test_unit = Unit('foo_type', unit_key, metadata.copy(), '')

        step.process_main(test_unit)

        modified_metadata = metadata.copy()
        modified_metadata.pop('_test')
        modified_metadata[server_constants.PULP_USER_METADATA_FIELDNAME] = {}
        unit_file = os.path.join(self.working_dir, 'foo.json')
        self.assertTrue(os.path.exists(unit_file))
        with open(unit_file) as file_handle:
            loaded = json.load(file_handle)
            compare_dict(loaded, {'unit_key': unit_key, 'unit_metadata': modified_metadata})


class CreateIsoStepTests(BaseYumDistributorPublishStepTests):

    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.generate_iso.create_iso')
    def test_process_main(self, mock_create):
        step = publish.CreateIsoStep('foo', 'bar')
        step.config = PluginCallConfiguration(None, {
            constants.ISO_SIZE_KEYWORD: 5,
            constants.ISO_PREFIX_KEYWORD: 'flux'
        })
        step.process_main()
        mock_create.assert_called_once_with('foo', 'bar', 'flux', 5)


class GenerateListingsFilesStep(BaseYumDistributorPublishStepTests):

    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.util.generate_listing_files')
    def test_process_main(self, mock_generate):
        step = publish.GenerateListingFileStep('foo', 'bar')
        step.process_main()
        mock_generate.assert_called_once_with('foo', 'bar')


class PublishCompsStepTests(BaseYumDistributorPublishStepTests):

    @skip_broken
    def test_units_total(self):
        step = publish.PublishCompsStep()
        step.parent = self.publisher
        self.publisher.repo.content_unit_counts = {TYPE_ID_PKG_CATEGORY: 3, TYPE_ID_PKG_GROUP: 5}
        self.assertEquals(8, step._get_total())

    @skip_broken
    def test_units_generator(self):
        self._init_publisher()
        step = publish.PublishCompsStep()
        step.parent = self.publisher
        step.comps_context = mock.Mock()
        self.publisher.get_conduit().get_units = mock.Mock(side_effect=[['foo', 'bar'],
                                                                        ['baz', 'qux'],
                                                                        ['quux', 'waldo']])

        unit_list = [x.unit for x in step.get_iterator()]
        self.assertEquals(unit_list, ['foo', 'bar', 'baz', 'qux', 'quux', 'waldo'])

    @skip_broken
    def test_process_unit(self):
        # verify that the process unit calls the unit process method
        self._init_publisher()
        step = publish.PublishCompsStep()
        mock_unit = mock.Mock()
        step.process_main(mock_unit)
        mock_unit.process.assert_called_once_with(mock_unit.unit)

    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.PackageXMLFileContext')
    def test_initialize_metadata(self, mock_context):
        self._init_publisher()
        step = publish.PublishCompsStep()
        step.parent = self.publisher
        step.initialize()
        mock_context.return_value.initialize.assert_called_once_with()

    def test_finalize_metadata(self):
        self._init_publisher()
        step = publish.PublishCompsStep()
        step.parent = self.publisher
        step.parent.repomd_file_context = mock.Mock()
        step.comps_context = mock.Mock()

        step.finalize()
        step.comps_context.finalize.assert_called_once_with()
        step.parent.repomd_file_context. \
            add_metadata_file_metadata.assert_called_once_with('group', mock.ANY, mock.ANY)

    def test_finalize_no_initialization(self):
        """
        Test to ensure that calling finalize before initialize_metadata() doesn't
        raise an exception
        """
        step = publish.PublishCompsStep()
        step.parent = self.publisher
        step.finalize()


class PublishDrpmStepTests(BaseYumDistributorPublishStepTests):

    def _generate_drpm(self, name):

        unit_key = {'epoch': '0',
                    'version': '1',
                    'release': '1',
                    'filename': name,
                    'checksumtype': 'sha256',
                    'checksum': '1234567890'}

        unit_metadata = {'new_package': name,
                         'arch': 'noarch',
                         'oldepoch': '0',
                         'oldversion': '1',
                         'oldrelease': '0',
                         'sequence': '0987654321',
                         'size': 5}

        storage_path = os.path.join(self.working_dir, 'content', name)
        self._touch(storage_path)

        return Unit(TYPE_ID_DRPM, unit_key, unit_metadata, storage_path)

    @skip_broken
    @mock.patch('pulp.plugins.util.publish_step.PublishStep._create_symlink')
    def test_process_unit(self, mock_symlink):
        step = publish.PublishDrpmStep(mock.Mock(package_dir=None))
        step.parent = self.publisher
        test_unit = self._generate_drpm('foo.rpm')
        test_unit.storage_path = '/bar'

        step.context = mock.Mock()
        step.dist_step.package_dirs = []
        step.process_main(test_unit)

        mock_symlink.assert_called_once_with('/bar', os.path.join(self.working_dir, 'drpms',
                                                                  'foo.rpm'))
        step.context.add_unit_metadata.assert_called_once_with(test_unit)

    @skip_broken
    @mock.patch('pulp.plugins.util.publish_step.PublishStep._create_symlink')
    def test_process_unit_links_packages_dir(self, mock_symlink):
        step = publish.PublishDrpmStep(mock.Mock(package_dir='bar'))
        step.parent = self.publisher

        test_unit = self._generate_drpm('foo.rpm')
        test_unit.storage_path = '/bar'
        step.context = mock.Mock()
        step.dist_step.package_dirs = ['/bar']
        step.process_main(test_unit)

        mock_symlink.assert_any_call('/bar', os.path.join(self.working_dir, 'drpms', 'foo.rpm'))

    def test_skip_if_no_units(self):
        step = publish.PublishDrpmStep(mock.Mock(package_dir=None))
        step.parent = self.publisher

        self.assertTrue(step.is_skipped())

    @skip_broken
    @mock.patch('pulp.server.db.model.TaskStatus')
    @mock.patch('pulp.plugins.conduits.repo_publish.RepoPublishConduit.get_units')
    def test_publish_drpms(self, mock_get_units, mock_update):
        self.publisher.repo.content_unit_counts = {TYPE_ID_DRPM: 2}

        units = [self._generate_drpm(u) for u in ('A', 'B')]
        mock_get_units.return_value = units

        package_dir_base = os.path.join(self.working_dir, 'bar')
        step = publish.PublishDrpmStep(mock.Mock(package_dirs=[package_dir_base]))
        step.parent = self.publisher

        step.process()

        for u in units:
            unit_path = os.path.join('drpms', u.unit_key['filename'])
            path = os.path.join(self.working_dir, unit_path)
            self.assertTrue(os.path.exists(path))
            self.assertTrue(os.path.islink(path))
            package_dir_path = os.path.join(package_dir_base, unit_path)
            self.assertTrue(os.path.exists(package_dir_path))
            self.assertTrue(os.path.islink(package_dir_path))

        self.assertTrue(os.path.exists(
            os.path.join(self.working_dir, 'repodata/prestodelta.xml.gz')))

    def test_finalize_no_initialization(self):
        """
        Test to ensure that calling finalize before initialize_metadata() doesn't
        raise an exception
        """
        step = publish.PublishDrpmStep(mock.Mock())
        step.parent = self.publisher
        step.finalize()


class TestPublishDistributionWritePulpDistributionFile(unittest.TestCase):
    xml_path = os.path.join(DATA_DIR, constants.DISTRIBUTION_XML)
    included_paths = ('foo', 'a/b', 'a/c')

    def setUp(self):
        super(TestPublishDistributionWritePulpDistributionFile, self).setUp()
        self.step = publish.PublishDistributionStep()
        self.step.working_dir = '/foo/bar'
        self.target = StringIO()

    def assertPathPresent(self, root, path):
        for child in root:
            if child.text == path:
                return
        self.fail('path not found in XML: %s' % path)

    def assertPathNotPresent(self, root, path):
        for child in root:
            if child.text == path:
                self.fail('path in XML: %s' % path)

    @mock.patch('os.path.join')
    @mock.patch('os.remove')
    def test_removes_file_entries(self, mock_remove, mock_path_join):
        """
        Make sure any paths in "distro_files" that are not present in the original XML get
        filtered out.
        """
        mock_path_join.side_effect = [self.target]
        paths = list(self.included_paths)
        paths.append('remove/me')

        self.step._write_pulp_distribution_file(paths, self.xml_path)

        root = ET.fromstring(self.target.getvalue())

        self.assertEqual(len(root), len(self.included_paths))
        # make sure it removed this entry that was not in the original file
        self.assertPathNotPresent(root, 'remove/me')
        # make sure it kept these entries
        for path in self.included_paths:
            self.assertPathPresent(root, path)


class PublishDistributionStepTests(BaseYumDistributorPublishStepTests):

    def _generate_distribution_unit(self, name, metadata={}):
        storage_path = os.path.join(self.working_dir, 'content', name)
        if not os.path.exists(storage_path):
            os.makedirs(storage_path)

        unit_key = {"id": name}
        unit_metadata = {"files": [
            {
                "downloadurl": "http://download-01.eng.brq.redhat.com/pub/rhel/released/RHEL-6/6.4/"
                               "Server/x86_64/os/images/boot.iso",
                "item_type": "distribution",
                "savepath": "/var/lib/pulp/working/repos/distro/importers/yum_importer/tmpGn5a2b/"
                            "tmpE7TPuQ/images/boot.iso",
                "checksumtype": "sha256",
                "relativepath": "images/boot.iso",
                "checksum": "929669e1203117f2b6a0d94f963af11db2eafe84f05c42c7e582d285430dc7a4",
                "pkgpath": "/var/lib/pulp/content/distribution/ks-Red Hat Enterprise Linux-Server-"
                           "6.4-x86_64/images",
                "filename": "boot.iso"
            }
        ]}
        unit_metadata.update(metadata)
        self._touch(os.path.join(storage_path, 'images', 'boot.iso'))

        return Unit(TYPE_ID_DISTRO, unit_key, unit_metadata, storage_path)

    @skip_broken
    @mock.patch('pulp.server.db.model.TaskStatus')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.PublishDistributionStep.'
                '_publish_distribution_packages_link')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.PublishDistributionStep.'
                '_publish_distribution_treeinfo')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.PublishDistributionStep.'
                '_publish_distribution_files')
    @mock.patch('pulp.plugins.conduits.repo_publish.RepoPublishConduit.get_units')
    def test_publish_distribution(self, mock_get_units, mock_files, mock_treeinfo, mock_packages,
                                  mock_update):
        self.publisher.repo.content_unit_counts = {TYPE_ID_DISTRO: 1}
        units = [self._generate_distribution_unit(u) for u in ('one', )]
        mock_get_units.return_value = units

        step = publish.PublishDistributionStep()
        step.parent = self.publisher
        step.process()

        mock_files.assert_called_once_with(units[0])
        mock_treeinfo.assert_called_once_with(units[0])
        mock_packages.assert_called_once_with(units[0])
        self.assertEquals(step.state, reporting_constants.STATE_COMPLETE)

    @skip_broken
    @mock.patch('pulp.server.db.model.TaskStatus')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.PublishDistributionStep.'
                '_publish_distribution_treeinfo')
    @mock.patch('pulp.plugins.conduits.repo_publish.RepoPublishConduit.get_units')
    def test_publish_distribution_error(self, mock_get_units, mock_treeinfo, mock_update):
        self.publisher.repo.content_unit_counts = {TYPE_ID_DISTRO: 1}
        units = [self._generate_distribution_unit(u) for u in ('one', )]
        mock_get_units.return_value = units
        error = Exception('Test Error')
        mock_treeinfo.side_effect = error
        step = publish.PublishDistributionStep()
        step.parent = self.publisher
        self.assertRaises(Exception, step.process)
        self.assertEquals(step.progress_failures, 1)

    @skip_broken
    def test_publish_distribution_multiple_distribution(self):
        step = publish.PublishDistributionStep()
        step.parent = self.publisher
        step._get_total = mock.Mock(return_value=2)
        self.assertRaises(Exception, step.initialize)

    @skip_broken
    def test_publish_distribution_treeinfo_does_nothing_if_no_treeinfo_file(self):
        unit = self._generate_distribution_unit('one')
        step = publish.PublishDistributionStep()
        step.parent = self.publisher
        step._publish_distribution_treeinfo(unit)
        self.assertEquals(step.progress_successes + step.progress_failures, 0)

    @mock.patch('pulp.plugins.util.misc.create_symlink', spec_set=True)
    def _perform_treeinfo_success_test(self, treeinfo_name, mock_symlink):
        unit = self._generate_distribution_unit('one')
        file_name = os.path.join(unit.storage_path, treeinfo_name)
        open(file_name, 'a').close()
        target_directory = os.path.join(self.publisher.repo.working_dir, treeinfo_name)
        step = publish.PublishDistributionStep()
        step.parent = self.publisher
        step._publish_distribution_treeinfo(unit)

        mock_symlink.assert_called_once_with(file_name, target_directory)

    @skip_broken
    def test_publish_distribution_treeinfo_finds_treeinfo(self):
        self._perform_treeinfo_success_test('treeinfo')

    @skip_broken
    def test_publish_distribution_treeinfo_finds_dot_treeinfo(self):
        self._perform_treeinfo_success_test('.treeinfo')

    @skip_broken
    @mock.patch('pulp.plugins.util.misc.create_symlink', spec_set=True)
    def test_publish_distribution_treeinfo_error(self, mock_symlink):
        unit = self._generate_distribution_unit('one')
        file_name = os.path.join(unit.storage_path, 'treeinfo')
        open(file_name, 'a').close()
        target_directory = os.path.join(self.publisher.repo.working_dir, 'treeinfo')
        mock_symlink.side_effect = Exception("Test Error")
        step = publish.PublishDistributionStep()
        step.parent = self.publisher

        self.assertRaises(Exception, step._publish_distribution_treeinfo, unit)

        mock_symlink.assert_called_once_with(file_name, target_directory)
        self.assertEquals(0, step.progress_successes)

    @skip_broken
    def test_publish_distribution_files(self):
        unit = self._generate_distribution_unit('one')
        step = publish.PublishDistributionStep()
        step.parent = self.publisher
        step._publish_distribution_files(unit)

        content_file = os.path.join(unit.storage_path, 'images', 'boot.iso')
        created_link = os.path.join(self.publisher.repo.working_dir, "images", 'boot.iso')
        self.assertTrue(os.path.islink(created_link))
        self.assertEquals(os.path.realpath(created_link), os.path.realpath(content_file))

    @skip_broken
    def test_publish_distribution_files_does_not_skip_repomd(self):
        """
        Assert that _publish_distribution_files() includes repomd.xml, in response to #1090534.

        https://bugzilla.redhat.com/show_bug.cgi?id=1090534
        """
        unit = self._generate_distribution_unit('one')
        unit.metadata['files'][0]['relativepath'] = 'repodata/repomd.xml'
        step = publish.PublishDistributionStep()
        step.parent = self.publisher
        # Let's put the file that should get linked to in the expected location
        repomd_path = os.path.join(self.working_dir, 'content', 'one', 'repodata', 'repomd.xml')
        self._touch(repomd_path)

        step._publish_distribution_files(unit)

        created_link = os.path.join(self.publisher.repo.working_dir, "repodata", 'repomd.xml')
        self.assertTrue(os.path.exists(created_link))
        # Make sure the symlink points to the correct path
        self.assertTrue(os.path.islink(created_link))
        self.assertEqual(os.readlink(created_link), repomd_path)

    @mock.patch('pulp.plugins.util.misc.create_symlink', spec_set=True)
    def test_publish_distribution_files_error(self, mock_symlink):
        unit = self._generate_distribution_unit('one')
        mock_symlink.side_effect = Exception('Test Error')
        step = publish.PublishDistributionStep()
        step.parent = self.publisher

        self.assertRaises(Exception, step._publish_distribution_files, unit)

    @skip_broken
    @mock.patch('pulp.plugins.util.misc.create_symlink', spec_set=True)
    def test_publish_distribution_files_no_files(self, mock_symlink):
        unit = self._generate_distribution_unit('one')
        unit.metadata.pop('files', None)
        step = publish.PublishDistributionStep()
        step.parent = self.publisher
        step._publish_distribution_files(unit)
        # This would throw an exception if it didn't work properly

    @skip_broken
    def test_publish_distribution_packages_link_with_packagedir(self):
        unit = self._generate_distribution_unit('one', {'packagedir': 'Server'})
        step = publish.PublishDistributionStep()
        step.parent = self.publisher
        step._publish_distribution_packages_link(unit)
        self.assertEquals(os.path.join(self.working_dir, 'Server'), step.package_dirs[0])

    @skip_broken
    def test_publish_distribution_packages_link_with_invalid_packagedir(self):
        self._init_publisher()
        step = publish.PublishDistributionStep()
        step.parent = self.publisher
        unit = self._generate_distribution_unit('one', {'packagedir': 'Server/../../foo'})
        self.assertRaises(InvalidValue, step._publish_distribution_packages_link, unit)

    @skip_broken
    def test_publish_distribution_packages_link_with_packagedir_equals_packages(self):
        unit = self._generate_distribution_unit('one', {'packagedir': 'Packages'})
        step = publish.PublishDistributionStep()
        step.parent = self.publisher
        step._publish_distribution_packages_link(unit)
        packages_dir = os.path.join(self.publisher.repo.working_dir, 'Packages')
        self.assertEquals(packages_dir, step.package_dirs[0])

    @skip_broken
    def test_publish_distribution_packages_link_with_packagedir_delete_existing_packages(self):
        packages_dir = os.path.join(self.working_dir, 'Packages')
        old_directory = os.path.join(self.working_dir, "foo")
        os.mkdir(old_directory)
        PublishStep._create_symlink(old_directory, packages_dir)
        self.assertEquals(os.path.realpath(packages_dir), old_directory)
        unit = self._generate_distribution_unit('one', {'packagedir': 'Packages'})
        step = publish.PublishDistributionStep()
        step.parent = self.publisher
        step._publish_distribution_packages_link(unit)
        self.assertFalse(os.path.islink(packages_dir))

    @mock.patch('pulp.plugins.util.misc.create_symlink', spec_set=True)
    def test_publish_distribution_packages_link_error(self, mock_symlink):
        self._init_publisher()
        mock_symlink.side_effect = Exception("Test Error")
        step = publish.PublishDistributionStep()
        step.parent = self.publisher
        self.assertRaises(Exception, step._publish_distribution_packages_link)


class PublishRpmStepTests(BaseYumDistributorPublishStepTests):

    @skip_broken
    @mock.patch('pulp.server.db.model.TaskStatus')
    @mock.patch('pulp.plugins.conduits.repo_publish.RepoPublishConduit.get_units')
    def test_publish_rpms(self, mock_get_units, mock_update):
        self.publisher.repo.content_unit_counts = {TYPE_ID_RPM: 3}

        units = [self._generate_rpm(u) for u in ('one', 'two', 'tree')]
        mock_get_units.return_value = units

        step = publish.PublishRpmStep(mock.Mock(package_dirs=[]))
        step.parent = self.publisher

        step.process()

        for u in units:
            path = os.path.join(self.working_dir, u.unit_key['name'])
            self.assertTrue(os.path.exists(path))
            self.assertTrue(os.path.islink(path))

        self.assertTrue(os.path.exists(os.path.join(self.working_dir, 'repodata/filelists.xml.gz')))
        self.assertTrue(os.path.exists(os.path.join(self.working_dir, 'repodata/other.xml.gz')))
        self.assertTrue(os.path.exists(os.path.join(self.working_dir, 'repodata/primary.xml.gz')))

    @skip_broken
    @mock.patch('pulp.server.db.model.TaskStatus')
    @mock.patch('pulp.plugins.conduits.repo_publish.RepoPublishConduit.get_units')
    def test_process_unit_links_package_dir(self, mock_get_units, mock_update):
        unit = self._generate_rpm('one')
        mock_get_units.return_value = [unit]
        self.publisher.repo.content_unit_counts = {TYPE_ID_RPM: 1}
        package_dir = os.path.join(self.working_dir, 'packages')

        step = publish.PublishRpmStep(mock.Mock(package_dirs=[package_dir]))
        self.publisher.add_child(step)

        step.process()

        unit_path = os.path.join(package_dir, unit.unit_key['name'])
        self.assertTrue(os.path.exists(unit_path))

    def test_finalize_no_initialization(self):
        """
        Test to ensure that calling finalize before initialize_metadata() doesn't
        raise an exception
        """
        step = publish.PublishRpmStep(mock.Mock(package_dir=None))
        step.parent = self.publisher
        step.finalize()

    def test_total_packages_in_repo(self):
        """
        the "total_packages_in_repo" property should calculate a number based on content unit counts
        on the repo
        """
        repo = model.Repository(repo_id='foo')
        repo.content_unit_counts = {'rpm': 2, 'srpm': 3}
        step = publish.PublishRpmStep(mock.Mock(package_dir=None))
        step.repo = repo.to_transfer_repo()

        total = step.total_packages_in_repo

        self.assertEqual(total, 5)

    def test_total_packages_in_repo_empty_repo(self):
        """
        in case the repo is empty and has no data in content_unit_counts, make sure this returns 0
        """
        repo = model.Repository(repo_id='foo')
        step = publish.PublishRpmStep(mock.Mock(package_dir=None))
        step.repo = repo.to_transfer_repo()

        total = step.total_packages_in_repo

        self.assertEqual(total, 0)


class PublishErrataStepTests(BaseYumDistributorPublishStepTests):

    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.UpdateinfoXMLFileContext')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.models')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.repo_controller')
    def test_initialize_metadata(self, mock_repo_controller, mock_models, mock_context):
        self._init_publisher()
        step = publish.PublishErrataStep()
        step.parent = self.publisher
        mock_queryset = mock.Mock()
        mock_repo_controller.get_unit_model_querysets.return_value = [mock_queryset]
        mock_queryset.scalar.return_value = [('n1', 'e1', 'v1', 'r1', 'a1')]

        step.initialize()
        mock_context.return_value.initialize.assert_called_once_with()
        repo_id = step.get_repo().id
        mock_repo_controller.get_unit_model_querysets.assert_called_once_with(repo_id,
                                                                              mock_models.RPM)
        mock_queryset.scalar.assert_called_once_with('name', 'epoch', 'version', 'release', 'arch')

    def test_finalize_metadata(self):
        self._init_publisher()
        step = publish.PublishErrataStep()
        step.parent = self.publisher
        step.parent.repomd_file_context = mock.Mock()
        step.context = mock.Mock()
        step.finalize()
        step.context.finalize.assert_called_once_with()
        step.parent.repomd_file_context. \
            add_metadata_file_metadata.assert_called_once_with('updateinfo', mock.ANY, mock.ANY)

    def test_finalize_no_initialization(self):
        """
        Test to ensure that calling finalize before initialize_metadata() doesn't
        raise an exception
        """
        step = publish.PublishErrataStep()
        step.parent = self.publisher
        step.finalize()


class PublishMetadataStepTests(BaseYumDistributorPublishStepTests):

    def _generate_metadata_file_unit(self, data_type, repo_id):

        unit_key = {'data_type': data_type,
                    'repo_id': repo_id}

        unit_metadata = {}

        storage_path = os.path.join(self.working_dir, 'content', 'metadata_files', data_type)
        self._touch(storage_path)

        return Unit(TYPE_ID_YUM_REPO_METADATA_FILE, unit_key, unit_metadata, storage_path)

    @skip_broken
    @mock.patch('pulp.server.db.model.TaskStatus')
    @mock.patch('pulp.plugins.conduits.repo_publish.RepoPublishConduit.get_units')
    def test_publish_metadata(self, mock_get_units, mock_update):
        # Setup
        units = [self._generate_metadata_file_unit(dt, 'test-repo') for dt in ('A', 'B')]
        mock_get_units.return_value = units
        self.publisher.repo.content_unit_counts = {TYPE_ID_YUM_REPO_METADATA_FILE: len(units)}

        # Test
        step = publish.PublishMetadataStep()
        step.parent = self.publisher
        step.process()

        # Verify
        self.assertEquals(reporting_constants.STATE_COMPLETE, step.state)
        self.assertEquals(len(units), step.total_units)
        self.assertEquals(0, step.progress_failures)
        self.assertEquals(len(units), step.progress_successes)

        for u in units:
            data_type = u.unit_key['data_type']
            path = os.path.join(self.working_dir, publish.REPO_DATA_DIR_NAME, data_type)
            self.assertTrue(os.path.exists(path))
            self.assertTrue(os.path.islink(path))
            self.assertTrue(os.path.exists(
                os.path.join(self.working_dir, 'repodata/%s' % data_type)))

    def test_publish_metadata_canceled(self):
        # Setup
        step = publish.PublishMetadataStep()
        self.publisher.add_child(step)
        mock_report_progress = mock.MagicMock()
        self.publisher._report_progress = mock_report_progress

        # Test
        self.publisher.cancel()
        step.process()

        # Verify
        self.assertEqual(0, mock_report_progress.call_count)


class GenerateSqliteForRepoStepTests(BaseYumDistributorPublishStepTests):

    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.subprocess.Popen')
    def test_process_main(self, Popen):
        pipe_output = ('some output', None)
        Popen.return_value = mock.MagicMock()
        Popen.return_value.returncode = 0
        Popen.return_value.communicate.return_value = pipe_output
        step = publish.GenerateSqliteForRepoStep('/foo')
        step.parent = mock.MagicMock()
        step.parent.get_checksum_type.return_value = 'sha1'
        step.process_main()
        Popen.assert_called_once_with('createrepo_c -d --update --keep-all-metadata '
                                      '--local-sqlite '
                                      '-s sha1 '
                                      '--skip-stat /foo',
                                      shell=True, stderr=mock.ANY, stdout=mock.ANY)

    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.subprocess.Popen')
    def test_process_main_with_error(self, Popen):
        step = publish.GenerateSqliteForRepoStep('/foo')
        step.parent = mock.MagicMock()
        pipe_output = ('some output', None)
        Popen.return_value = mock.MagicMock()
        Popen.return_value.returncode = 1
        Popen.return_value.communicate.return_value = pipe_output
        with self.assertRaisesRegexp(PulpCodedException, 'createrepo_c') as cm:
            step.process_main()
        self.assertEqual(cm.exception.error_code.code, 'RPM0001')

    def test_is_skipped_no_config(self):
        # Generating sqlite files is turned off by default
        step = publish.GenerateSqliteForRepoStep('/foo')
        self.publisher.add_child(step)
        self.assertTrue(step.is_skipped())

    def test_is_skipped_config_falise(self):
        step = publish.GenerateSqliteForRepoStep('/foo')
        self.publisher.add_child(step)
        self.publisher.get_config().default_config.update({'generate_sqlite': False})
        self.assertTrue(step.is_skipped())

    def test_is_skipped_config_true(self):
        step = publish.GenerateSqliteForRepoStep('/foo')
        self.publisher.add_child(step)
        self.publisher.get_config().default_config.update({'generate_sqlite': True})
        self.assertFalse(step.is_skipped())


class GenerateRepoviewStepTests(BaseYumDistributorPublishStepTests):
    """
    Test GenerateRepoviewStep of the publish process.
    """
    @mock.patch('pulp.plugins.util.publish_step.PluginStep.get_repo')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.subprocess.Popen')
    def test_process_main(self, Popen, mock_get_repo):
        """
        Test that repoview tool was called with proper parameters.
        """
        pipe_output = ('some output', None)
        Popen.return_value = mock.MagicMock()
        Popen.return_value.returncode = 0
        Popen.return_value.communicate.return_value = pipe_output
        mock_get_repo.return_value.id = 'test-repo'
        step = publish.GenerateRepoviewStep('/foo')
        step.process_main()
        Popen.assert_called_once_with('repoview --title test-repo /foo',
                                      shell=True, stderr=mock.ANY, stdout=mock.ANY)

    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.subprocess.Popen')
    def test_process_main_with_error(self, Popen):
        """
        Test that PulpCodedException is raised if some error happened during the execution
        of a child process.
        """
        step = publish.GenerateRepoviewStep('/foo')
        step.parent = mock.MagicMock()
        pipe_output = ('some output', None)
        Popen.return_value = mock.MagicMock()
        Popen.return_value.returncode = 1
        Popen.return_value.communicate.return_value = pipe_output
        with self.assertRaisesRegexp(PulpCodedException, 'repoview') as cm:
            step.process_main()
        self.assertEqual(cm.exception.error_code.code, 'RPM0001')

    def test_is_skipped_no_config(self):
        """
        Test that GenerateRepoviewStep is skipped if the repoview flag was not specified
        in the config.
        """
        step = publish.GenerateRepoviewStep('/foo')
        self.publisher.add_child(step)
        self.assertTrue(step.is_skipped())

    def test_is_skipped_config_false(self):
        """
        Test that GenerateRepoviewStep is skipped if the repoview flag was set to False
        in the config.
        """
        step = publish.GenerateRepoviewStep('/foo')
        self.publisher.add_child(step)
        self.publisher.get_config().default_config.update({'repoview': False})
        self.assertTrue(step.is_skipped())

    def test_is_skipped_config_true(self):
        """
        Test that GenerateRepoviewStep is not skipped if the repoview flag was set to True
        in the config.
        """
        step = publish.GenerateRepoviewStep('/foo')
        self.publisher.add_child(step)
        self.publisher.get_config().default_config.update({'repoview': True})
        self.assertFalse(step.is_skipped())
