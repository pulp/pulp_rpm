from cStringIO import StringIO
from copy import deepcopy
import os
import unittest

import mock
from nectar.config import DownloaderConfig
from nectar.downloaders.base import Downloader
from pulp.common.plugins import importer_constants
from pulp.plugins.conduits.repo_sync import RepoSyncConduit
from pulp.plugins.config import PluginCallConfiguration
from pulp.plugins.model import Repository, SyncReport
import pulp.server.managers.factory as manager_factory

from pulp_rpm.common import constants
from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.importers.yum.existing import associate_already_downloaded_units
from pulp_rpm.plugins.importers.yum.repomd import metadata, group, updateinfo, packages, presto, primary
from pulp_rpm.plugins.importers.yum.sync import RepoSync, FailedException, CancelException
import model_factory


manager_factory.initialize()


class BaseSyncTest(unittest.TestCase):
    def setUp(self):
        self.url = 'http://pulpproject.org/'
        self.metadata_files = metadata.MetadataFiles(self.url, '/foo/bar', DownloaderConfig())
        self.metadata_files.download_repomd = mock.MagicMock()
        self.repo = Repository('repo1')
        self.conduit = RepoSyncConduit(self.repo.id, 'yum_importer', 'user', 'me')
        self.conduit.set_progress = mock.MagicMock(spec_set=self.conduit.set_progress)
        self.config = PluginCallConfiguration({}, {importer_constants.KEY_FEED: self.url})
        self.reposync = RepoSync(self.repo, self.conduit, self.config)
        self.downloader = Downloader(DownloaderConfig())


class TestInit(BaseSyncTest):
    def test_sets_initial_progress(self):
        self.conduit.set_progress.assert_called_once_with(self.reposync.progress_status)

    def test_initial_report_states(self):
        self.assertEqual(len(self.reposync.progress_status.keys()), 5)
        for step_name, report in self.reposync.progress_status.iteritems():
            self.assertEqual(report['state'], constants.STATE_NOT_STARTED)

    def test_not_immediately_canceled(self):
        self.assertFalse(self.reposync.cancelled)

    def test_nectar_config(self):
        self.assertTrue(isinstance(self.reposync.nectar_config, DownloaderConfig))


class TestSetProgress(BaseSyncTest):
    def test_not_canceled(self):
        self.conduit.set_progress = mock.MagicMock(spec_set=self.conduit.set_progress)

        self.reposync.set_progress()

        self.conduit.set_progress.assert_called_once_with(self.reposync.progress_status)

    def test_canceled(self):
        self.conduit.set_progress = mock.MagicMock(spec_set=self.conduit.set_progress)
        self.reposync.cancelled = True

        self.assertRaises(CancelException, self.reposync.set_progress)

        self.conduit.set_progress.assert_called_once_with(self.reposync.progress_status)


class TestSyncFeed(BaseSyncTest):
    def test_with_trailing_slash(self):
        ret = self.reposync.sync_feed

        self.assertEqual(ret, self.url)

    def test_without_trailing_slash(self):
        # it should add back the trailing slash if not present
        self.config.override_config[importer_constants.KEY_FEED] = self.url.rstrip('/')

        ret = self.reposync.sync_feed

        self.assertEqual(ret, self.url)


class TestRun(BaseSyncTest):
    def setUp(self):
        super(TestRun, self).setUp()
        self.reposync.get_metadata = mock.MagicMock(spec_set=self.reposync.get_metadata,
                                                    return_value=self.metadata_files)
        self.reposync.update_content = mock.MagicMock(spec_set=self.reposync.update_content)
        self.reposync.get_errata = mock.MagicMock(spec_set=self.reposync.get_errata)
        self.reposync.get_comps_file_units = mock.MagicMock(spec_set=self.reposync.get_comps_file_units)

        self.reposync.set_progress = mock.MagicMock(spec_set=self.reposync.set_progress)

    @mock.patch('shutil.rmtree', autospec=True)
    @mock.patch('tempfile.mkdtemp', autospec=True)
    def test_removes_tmp_dir_after_exception(self, mock_mkdtemp, mock_rmtree):
        self.reposync.get_metadata.side_effect = ValueError

        self.reposync.run()

        mock_rmtree.assert_called_once_with(mock_mkdtemp.return_value, ignore_errors=True)

    @mock.patch('pulp_rpm.plugins.importers.yum.parse.treeinfo.sync', autospec=True)
    @mock.patch('shutil.rmtree', autospec=True)
    @mock.patch('tempfile.mkdtemp', autospec=True)
    def test_calls_workflow(self, mock_mkdtemp, mock_rmtree, mock_treeinfo_sync):
        report = self.reposync.run()

        self.assertTrue(report.success_flag)
        self.assertFalse(report.canceled_flag)

        self.reposync.get_metadata.assert_called_once_with()
        self.reposync.update_content.assert_called_once_with(self.metadata_files)
        self.reposync.get_errata.assert_called_once_with(self.metadata_files)
        calls = [mock.call(self.metadata_files, group.process_group_element, group.GROUP_TAG),
                 mock.call(self.metadata_files, group.process_environment_element,
                           group.ENVIRONMENT_TAG),
                 mock.call(self.metadata_files, group.process_category_element, group.CATEGORY_TAG)]
        self.reposync.get_comps_file_units.assert_has_calls(calls, any_order=True)

        mock_treeinfo_sync.assert_called_once_with(self.conduit, self.url, mock_mkdtemp.return_value,
                                                   self.reposync.nectar_config,
                                                   self.reposync.distribution_report,
                                                   self.reposync.set_progress)
        # make sure we cleaned up the temporary directory
        mock_rmtree.assert_called_once_with(mock_mkdtemp.return_value, ignore_errors=True)

    # this lets the treeinfo sync method run and manage its own state while
    # causing it to quit early
    @mock.patch('pulp_rpm.plugins.importers.yum.parse.treeinfo.get_treefile',
                autospec=True, return_value=None)
    @mock.patch('shutil.rmtree', autospec=True)
    @mock.patch('tempfile.mkdtemp', autospec=True)
    def test_reports_state_complete(self, mock_mkdtemp, mock_rmtree, mock_get_treefile):
        report = self.reposync.run()

        self.assertTrue(isinstance(report, SyncReport))
        for step_name, report in report.details.iteritems():
            self.assertEqual(report['state'], constants.STATE_COMPLETE, 'setp: %s' % step_name)

    @mock.patch('pulp_rpm.plugins.importers.yum.parse.treeinfo.sync', autospec=True)
    @mock.patch('shutil.rmtree', autospec=True)
    @mock.patch('tempfile.mkdtemp', autospec=True)
    def test_skip_types(self, mock_mkdtemp, mock_rmtree, mock_treeinfo_sync):
        self.config.default_config[constants.CONFIG_SKIP] = [
            models.Distribution.TYPE,
            models.Errata.TYPE,
        ]

        report = self.reposync.run()

        self.assertEqual(self.reposync.get_errata.call_count, 0)
        self.assertEqual(mock_treeinfo_sync.call_count, 0)
        self.assertEqual(report.details['errata']['state'],
                         constants.STATE_SKIPPED)
        self.assertEqual(report.details['distribution']['state'],
                         constants.STATE_SKIPPED)

    @mock.patch('pulp_rpm.plugins.importers.yum.sync.treeinfo')
    @mock.patch('shutil.rmtree', autospec=True)
    @mock.patch('tempfile.mkdtemp', autospec=True)
    @mock.patch('nectar.config.DownloaderConfig.finalize')
    def test_finalize(self, mock_finalize, mock_mkdtemp, mock_rmtree, mock_treeinfo):

        self.reposync.run()

        mock_finalize.assert_called_once()

    @mock.patch('shutil.rmtree', autospec=True)
    @mock.patch('tempfile.mkdtemp', autospec=True)
    def test_cancel(self, mock_mkdtemp, mock_rmtree):
        self.reposync.get_metadata.side_effect = CancelException

        report = self.reposync.run()

        self.assertTrue(report.canceled_flag)
        self.assertFalse(report.success_flag)

    @mock.patch('shutil.rmtree', autospec=True)
    @mock.patch('tempfile.mkdtemp', autospec=True)
    def test_misc_failure(self, mock_mkdtemp, mock_rmtree):
        self.reposync.get_metadata.side_effect = AttributeError

        report = self.reposync.run()

        self.assertEqual(report.details['metadata']['state'], constants.STATE_FAILED)
        self.assertEqual(report.details['content']['state'], constants.STATE_NOT_STARTED)
        self.assertFalse(report.success_flag)
        self.assertFalse(report.canceled_flag)
        self.assertEqual(self.reposync.set_progress.call_count, 2)

    def test_fail_on_missing_feed(self):
        self.config = PluginCallConfiguration({}, {})
        reposync = RepoSync(self.repo, self.conduit, self.config)
        reposync.call_config.get(importer_constants.KEY_FEED)
        report = reposync.run()
        self.assertEquals(report.details['metadata']['error'],
                          'Unable to sync a repository that has no feed')


class TestProgressSummary(BaseSyncTest):
    def test_content(self):
        ret = self.reposync._progress_summary

        self.assertTrue(len(ret) > 0)
        self.assertEqual(len(ret), len(self.reposync.progress_status))
        for step_name in self.reposync.progress_status.keys():
            self.assertTrue(step_name in ret, 'missing key: %s' % step_name)
            # ensure that just the state is present.
            self.assertEqual(ret[step_name].keys(), ['state'])
            self.assertEqual(self.reposync.progress_status[step_name]['state'],
                             ret[step_name]['state'])


class TestGetMetadata(BaseSyncTest):
    def setUp(self):
        super(TestGetMetadata, self).setUp()
        self.reposync.tmp_dir = '/tmp'

    @mock.patch.object(metadata, 'MetadataFiles', autospec=True)
    def test_failed_download(self, mock_metadata_files):
        mock_metadata_files.return_value = self.metadata_files
        self.metadata_files.download_repomd = mock.MagicMock(side_effect=IOError, autospec=True)

        self.assertRaises(FailedException, self.reposync.get_metadata)

    @mock.patch.object(metadata, 'MetadataFiles', autospec=True)
    def test_failed_download_repomd(self, mock_metadata_files):
        mock_metadata_files.return_value = self.metadata_files
        self.metadata_files.parse_repomd = mock.MagicMock(side_effect=ValueError, autospec=True)

        self.assertRaises(FailedException, self.reposync.get_metadata)

    @mock.patch.object(metadata, 'MetadataFiles', autospec=True)
    def test_failed_parse_repomd(self, mock_metadata_files):
        mock_metadata_files.return_value = self.metadata_files
        self.metadata_files.download_repomd = mock.MagicMock(autospec=True)
        self.metadata_files.parse_repomd = mock.MagicMock(side_effect=ValueError, autospec=True)

        self.assertRaises(FailedException, self.reposync.get_metadata)

    @mock.patch.object(metadata, 'MetadataFiles', autospec=True)
    def test_success(self, mock_metadata_files):
        mock_metadata_instane = mock_metadata_files.return_value
        mock_metadata_instane.downloader = mock.MagicMock()
        self.reposync.import_unknown_metadata_files = mock.MagicMock(spec_set=self.reposync.import_unknown_metadata_files)

        ret = self.reposync.get_metadata()

        self.assertEqual(ret, mock_metadata_instane)
        mock_metadata_instane.download_repomd.assert_called_once_with()
        mock_metadata_instane.parse_repomd.assert_called_once_with()
        mock_metadata_instane.download_metadata_files.assert_called_once_with()
        mock_metadata_instane.generate_dbs.assert_called_once_with()
        self.reposync.import_unknown_metadata_files.assert_called_once_with(mock_metadata_instane)


class TestSaveMetadataChecksum(BaseSyncTest):
    def setUp(self):
        super(TestSaveMetadataChecksum, self).setUp()
        self.reposync.tmp_dir = '/tmp'

    def test_process_successful(self):
        self.conduit.get_repo_scratchpad = mock.Mock(return_value={})
        self.conduit.set_repo_scratchpad = mock.Mock()

        file_info = deepcopy(metadata.FILE_INFO_SKEL)
        file_info['checksum']['algorithm'] = 'sha1'
        self.metadata_files.metadata['foo'] = file_info

        self.reposync.save_default_metadata_checksum_on_repo(self.metadata_files)
        self.conduit.set_repo_scratchpad.assert_called_once_with(
            {constants.SCRATCHPAD_DEFAULT_METADATA_CHECKSUM: 'sha1'})

    def test_process_no_hash(self):
        self.conduit = mock.Mock()
        self.reposync.save_default_metadata_checksum_on_repo(self.metadata_files)
        self.assertFalse(self.conduit.set_repo_scratchpad.called)


class ImportUnknownMetadataFiles(BaseSyncTest):
    def setUp(self):
        super(ImportUnknownMetadataFiles, self).setUp()
        self.conduit.save_unit = mock.MagicMock(spec_set=self.conduit.save_unit)
        self.conduit.init_unit = mock.MagicMock(spec_set=self.conduit.save_unit)

    def test_known_type(self):
        self.conduit.init_unit = mock.MagicMock(spec_set=self.conduit.init_unit)
        self.metadata_files.metadata = {'primary': mock.MagicMock()}

        self.reposync.import_unknown_metadata_files(self.metadata_files)

        # nothing can be done without calling init_unit, so this is a good
        # indicator that the file type was skipped.
        self.assertEqual(self.conduit.init_unit.call_count, 0)

    def test_none_found(self):
        self.reposync.import_unknown_metadata_files(self.metadata_files)

        self.assertEqual(self.conduit.save_unit.call_count, 0)

    @mock.patch('shutil.copyfile', autospec=True)
    def test_found_one(self, mock_copy):
        self.metadata_files.metadata['fake_type'] = {
            'checksum': {'hex_digest': 'checksum_value', 'algorithm': 'sha257'},
            'local_path': 'path/to/fake_type.xml'
        }

        self.reposync.import_unknown_metadata_files(self.metadata_files)

        self.conduit.init_unit.assert_called_once_with(
            models.YumMetadataFile.TYPE,
            {'repo_id': self.repo.id, 'data_type': 'fake_type'},
            {'checksum': 'checksum_value', 'checksum_type': 'sha257'},
            '%s/fake_type.xml' % self.repo.id,
        )
        self.conduit.save_unit.assert_called_once_with(self.conduit.init_unit.return_value)
        mock_copy.assert_called_once_with('path/to/fake_type.xml',
                                          self.conduit.init_unit.return_value.storage_path)


class TestUpdateContent(BaseSyncTest):
    """
    The function being tested doesn't really do anything besides walk through a
    workflow of calling other functions.
    """
    @mock.patch('pulp_rpm.plugins.importers.yum.sync.RepoSync._decide_what_to_download',
                spec_set=RepoSync._decide_what_to_download)
    @mock.patch('pulp_rpm.plugins.importers.yum.sync.RepoSync.download',
                spec_set=RepoSync.download)
    @mock.patch('pulp_rpm.plugins.importers.yum.purge.purge_unwanted_units', autospec=True)
    def test_workflow(self, mock_purge, mock_download, mock_decide):
        rpms = set([1, 2, 3])
        drpms = set([4, 5, 6])
        mock_decide.return_value = (rpms, drpms)

        self.reposync.update_content(self.metadata_files)

        mock_decide.assert_called_once_with(self.metadata_files)
        mock_download.assert_called_once_with(self.metadata_files, rpms, drpms)
        mock_purge.assert_called_once_with(self.metadata_files, self.conduit, self.config)


class TestDecideWhatToDownload(BaseSyncTest):
    @mock.patch('pulp_rpm.plugins.importers.yum.sync.RepoSync._decide_rpms_to_download',
                spec_set=RepoSync._decide_rpms_to_download)
    @mock.patch('pulp_rpm.plugins.importers.yum.sync.RepoSync._decide_drpms_to_download',
                spec_set=RepoSync._decide_drpms_to_download)
    def test_all(self, mock_decide_drpms, mock_decide_rpms):
        rpm_model = model_factory.rpm_models(1)[0]
        drpm_model = model_factory.drpm_models(1)[0]
        mock_decide_rpms.return_value = (set([rpm_model.as_named_tuple]), 1, 1024)
        mock_decide_drpms.return_value = (set([drpm_model.as_named_tuple]), 1, 1024)
        self.conduit.set_progress = mock.MagicMock(spec_set=self.conduit.set_progress)

        ret = self.reposync._decide_what_to_download(self.metadata_files)

        self.assertEqual(ret[0], set([rpm_model.as_named_tuple]))
        self.assertEqual(ret[1], set([drpm_model.as_named_tuple]))
        self.assertEqual(len(ret), 2)
        mock_decide_rpms.assert_called_once_with(self.metadata_files)
        mock_decide_drpms.assert_called_once_with(self.metadata_files)
        self.assertEqual(self.conduit.set_progress.call_count, 1)

        # make sure we reported initial progress values correctly
        report = self.conduit.set_progress.call_args[0][0]
        self.assertEqual(report['content']['size_total'], 2048)
        self.assertEqual(report['content']['size_left'], 2048)
        self.assertEqual(report['content']['items_total'], 2)
        self.assertEqual(report['content']['items_left'], 2)
        self.assertEqual(report['content']['details']['rpm_total'], 1)
        self.assertEqual(report['content']['details']['drpm_total'], 1)


class TestDecideRPMsToDownload(BaseSyncTest):
    def test_skip_rpms(self):
        self.config.override_config[constants.CONFIG_SKIP] = [models.RPM.TYPE]

        ret = self.reposync._decide_rpms_to_download(self.metadata_files)

        self.assertEqual(ret, (set(), 0, 0))

    @mock.patch('__builtin__.open', autospec=True)
    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.packages.package_list_generator', autospec=True)
    @mock.patch('pulp_rpm.plugins.importers.yum.sync.RepoSync._identify_wanted_versions',
                spec_set=RepoSync._identify_wanted_versions)
    @mock.patch('pulp_rpm.plugins.importers.yum.existing.check_repo', autospec=True)
    def test_calls_identify_wanted_and_existing(self, mock_check_repo, mock_identify,
                                                mock_generator, mock_open):
        primary_file = StringIO()
        mock_open.return_value = primary_file
        model = model_factory.rpm_models(1)[0]
        self.metadata_files.metadata[primary.METADATA_FILE_NAME] = {'local_path': '/path/to/primary'}
        mock_generator.return_value = [model.as_named_tuple]
        mock_identify.return_value = {model.as_named_tuple: 1024}
        mock_check_repo.return_value = set([model.as_named_tuple])

        ret = self.reposync._decide_rpms_to_download(self.metadata_files)

        self.assertEqual(ret, (set([model.as_named_tuple]), 1, 1024))
        mock_open.assert_called_once_with('/path/to/primary', 'r')
        mock_generator.assert_called_once_with(primary_file, primary.PACKAGE_TAG, primary.process_package_element)
        mock_identify.assert_called_once_with(mock_generator.return_value)
        self.assertTrue(primary_file.closed)

    @mock.patch('__builtin__.open', autospec=True)
    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.packages.package_list_generator', autospec=True)
    def test_closes_file_on_exception(self, mock_generator, mock_open):
        primary_file = StringIO()
        mock_open.return_value = primary_file
        self.metadata_files.metadata[primary.METADATA_FILE_NAME] = {'local_path': '/path/to/primary'}
        mock_generator.side_effect = ValueError

        self.assertRaises(ValueError, self.reposync._decide_rpms_to_download,
                          self.metadata_files)

        mock_open.assert_called_once_with('/path/to/primary', 'r')
        self.assertTrue(primary_file.closed)


class TestDecideDRPMsToDownload(BaseSyncTest):
    def test_skip_drpms(self):
        self.config.override_config[constants.CONFIG_SKIP] = [models.DRPM.TYPE]

        ret = self.reposync._decide_drpms_to_download(self.metadata_files)

        self.assertEqual(ret, (set(), 0, 0))

    def test_no_file_available(self):
        self.assertTrue(self.metadata_files.get_metadata_file_handle(presto.METADATA_FILE_NAME) is None)

        ret = self.reposync._decide_drpms_to_download(self.metadata_files)

        self.assertEqual(ret, (set(), 0, 0))

    @mock.patch('__builtin__.open', autospec=True)
    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.packages.package_list_generator', autospec=True)
    @mock.patch('pulp_rpm.plugins.importers.yum.sync.RepoSync._identify_wanted_versions',
                spec_set=RepoSync._identify_wanted_versions)
    @mock.patch('pulp_rpm.plugins.importers.yum.existing.check_repo', autospec=True)
    def test_calls_identify_wanted_and_existing(self, mock_check_repo, mock_identify,
                                                mock_generator, mock_open):
        presto_file = StringIO()
        mock_open.return_value = presto_file
        model = model_factory.drpm_models(1)[0]
        self.metadata_files.metadata[presto.METADATA_FILE_NAME] = {'local_path': '/path/to/presto'}
        mock_generator.return_value = [model.as_named_tuple]
        mock_identify.return_value = {model.as_named_tuple: 1024}
        mock_check_repo.return_value = set([model.as_named_tuple])

        ret = self.reposync._decide_drpms_to_download(self.metadata_files)

        self.assertEqual(ret, (set([model.as_named_tuple]), 1, 1024))
        mock_open.assert_called_once_with('/path/to/presto', 'r')
        mock_generator.assert_called_once_with(presto_file, presto.PACKAGE_TAG, presto.process_package_element)
        mock_identify.assert_called_once_with(mock_generator.return_value)
        self.assertTrue(presto_file.closed)

    @mock.patch('__builtin__.open', autospec=True)
    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.packages.package_list_generator', autospec=True)
    def test_closes_file_on_exception(self, mock_generator, mock_open):
        presto_file = StringIO()
        mock_open.return_value = presto_file
        self.metadata_files.metadata[presto.METADATA_FILE_NAME] = {'local_path': '/path/to/presto'}
        mock_generator.side_effect = ValueError

        self.assertRaises(ValueError, self.reposync._decide_drpms_to_download,
                          self.metadata_files)

        mock_open.assert_called_once_with('/path/to/presto', 'r')
        self.assertTrue(presto_file.closed)


class TestDownload(BaseSyncTest):
    RELATIVEPATH = 'myrelativepath'

    def setUp(self):
        super(TestDownload, self).setUp()
        # nothing in these tests should actually attempt to write anything
        self.reposync.tmp_dir = '/idontexist/'

    @mock.patch.object(packages, 'package_list_generator', autospec=True)
    def test_none_to_download(self, mock_package_list_generator):
        """
        make sure it does nothing if there are no units specified to download
        """
        self.metadata_files.get_metadata_file_handle = mock.MagicMock(
            spec_set=self.metadata_files.get_metadata_file_handle,
            side_effect=StringIO,
        )
        mock_package_list_generator.side_effect = iter([model_factory.rpm_models(3),
                                                    model_factory.drpm_models(3)])

        report = self.reposync.download(self.metadata_files, set(), set())

        self.assertTrue(report.success_flag)
        self.assertEqual(report.added_count, 0)
        self.assertEqual(report.removed_count, 0)
        self.assertEqual(report.updated_count, 0)

    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.nectar_factory.create_downloader', autospec=True)
    @mock.patch.object(packages, 'package_list_generator', autospec=True)
    def test_rpms_to_download(self, mock_package_list_generator, mock_create_downloader):
        """
        test with only RPMs specified to download
        """
        file_handle = StringIO()
        self.metadata_files.get_metadata_file_handle = mock.MagicMock(
            spec_set=self.metadata_files.get_metadata_file_handle,
            side_effect=[file_handle, None], # None means it will skip DRPMs
        )
        rpms = model_factory.rpm_models(3)
        for rpm in rpms:
            rpm.metadata['relativepath'] = self.RELATIVEPATH
            # for this mock data, relativepath is already the same as
            # os.path.basename(relativepath)
            rpm.metadata['filename'] = self.RELATIVEPATH
        mock_package_list_generator.return_value = rpms
        self.downloader.download = mock.MagicMock(spec_set=self.downloader.download)
        mock_create_downloader.return_value = self.downloader

        # call download, passing in only two of the 3 rpms as units we want
        report = self.reposync.download(self.metadata_files, set(m.as_named_tuple for m in rpms[:2]), set())

        # make sure we skipped DRPMs
        self.assertEqual(self.downloader.download.call_count, 1)
        self.assertEqual(mock_package_list_generator.call_count, 1)

        # verify that the download requests were correct
        requests = list(self.downloader.download.call_args[0][0])
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0].url, os.path.join(self.url, self.RELATIVEPATH))
        self.assertEqual(requests[0].destination, os.path.join(self.reposync.tmp_dir, self.RELATIVEPATH))
        self.assertTrue(requests[0].data is rpms[0])
        self.assertEqual(requests[1].url, os.path.join(self.url, self.RELATIVEPATH))
        self.assertEqual(requests[1].destination, os.path.join(self.reposync.tmp_dir, self.RELATIVEPATH))
        self.assertTrue(requests[1].data is rpms[1])
        self.assertTrue(file_handle.closed)

    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.nectar_factory.create_downloader', autospec=True)
    @mock.patch.object(packages, 'package_list_generator', autospec=True)
    def test_drpms_to_download(self, mock_package_list_generator, mock_create_downloader):
        """
        test with only DRPMs specified to download
        """
        file_handle = StringIO()
        self.metadata_files.get_metadata_file_handle = mock.MagicMock(
            spec_set=self.metadata_files.get_metadata_file_handle,
            side_effect=[StringIO(), file_handle],
        )
        drpms = model_factory.drpm_models(3)
        for drpm in drpms:
            drpm.metadata['relativepath'] = ''
        mock_package_list_generator.side_effect = iter([[], drpms])
        self.downloader.download = mock.MagicMock(spec_set=self.downloader.download)
        mock_create_downloader.return_value = self.downloader

        # call download, passing in only two of the 3 rpms as units we want
        report = self.reposync.download(self.metadata_files, set(), set(m.as_named_tuple for m in drpms[:2]))

        self.assertEqual(self.downloader.download.call_count, 2)
        self.assertEqual(mock_package_list_generator.call_count, 2)

        # verify that the download requests were correct
        requests = list(self.downloader.download.call_args[0][0])
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0].url, os.path.join(self.url, drpms[0].filename))
        self.assertEqual(requests[0].destination, os.path.join(self.reposync.tmp_dir, drpms[0].filename))
        self.assertTrue(requests[0].data is drpms[0])
        self.assertEqual(requests[1].url, os.path.join(self.url, drpms[1].filename))
        self.assertEqual(requests[1].destination, os.path.join(self.reposync.tmp_dir, drpms[1].filename))
        self.assertTrue(requests[1].data is drpms[1])
        self.assertTrue(file_handle.closed)


class TestCancel(BaseSyncTest):
    def test_sets_bools(self):
        self.reposync.downloader = self.downloader

        self.reposync.cancel()

        self.assertTrue(self.reposync.cancelled)
        self.assertTrue(self.downloader.is_canceled)

    def test_handles_no_downloader(self):
        # it shouldn't get upset if there isn't a downloader available
        self.reposync.cancel()

        self.assertTrue(self.reposync.cancelled)
        self.assertTrue(getattr(self.reposync, 'downloader', None) is None)

    def test_sets_progress(self):
        # get a sync running, but have the "get_metadata" call actually result
        # in a "cancel" call
        self.reposync.get_metadata = mock.MagicMock(side_effect=self.reposync.cancel,
                                                    spec_set=self.reposync.get_metadata)
        self.reposync.save_default_metadata_checksum_on_repo = mock.MagicMock()

        report = self.reposync.run()

        # this proves that the progress was correctly set and a corresponding report
        # was made
        self.assertTrue(report.canceled_flag)
        self.assertEqual(report.details['metadata']['state'], constants.STATE_CANCELLED)


class TestGetErrata(BaseSyncTest):
    @mock.patch.object(RepoSync, 'save_fileless_units', autospec=True)
    def test_no_metadata(self, mock_save):
        self.reposync.get_errata(self.metadata_files)

        self.assertEqual(mock_save.call_count, 0)

    @mock.patch.object(RepoSync, 'save_fileless_units', autospec=True)
    @mock.patch.object(metadata.MetadataFiles, 'get_metadata_file_handle',
                       autospec=True, return_value=StringIO())
    def test_closes_file(self, mock_get, mock_save):
        """
        make sure this closes its file handle
        """
        self.assertFalse(mock_get.return_value.closed)

        self.reposync.get_errata(self.metadata_files)

        self.assertTrue(mock_get.return_value.closed)

    @mock.patch.object(RepoSync, 'save_fileless_units', autospec=True,
                       side_effect=AttributeError)
    @mock.patch.object(metadata.MetadataFiles, 'get_metadata_file_handle',
                       autospec=True, return_value=StringIO())
    def test_closes_file_on_exception(self, mock_get, mock_save):
        """
        make sure this closes its file handle even if an exception is raised
        """
        self.assertFalse(mock_get.return_value.closed)

        self.assertRaises(AttributeError, self.reposync.get_errata, self.metadata_files)

        self.assertTrue(mock_get.return_value.closed)

    @mock.patch.object(updateinfo, 'process_package_element', autospec=True)
    @mock.patch.object(RepoSync, 'save_fileless_units', autospec=True)
    @mock.patch.object(metadata.MetadataFiles, 'get_metadata_file_handle',
                       autospec=True, return_value=StringIO())
    def test_with_metadata(self, mock_get, mock_save, mock_process):
        self.reposync.get_errata(self.metadata_files)

        mock_save.assert_called_once_with(self.reposync,
                                          mock_get.return_value,
                                          updateinfo.PACKAGE_TAG,
                                          updateinfo.process_package_element)


class TestGetCompsFileUnits(BaseSyncTest):

    @mock.patch.object(RepoSync, 'save_fileless_units', autospec=True)
    def test_no_metadata(self, mock_save):
        self.reposync.get_comps_file_units(self.metadata_files, mock.Mock(), "foo")

        self.assertEqual(mock_save.call_count, 0)

    @mock.patch.object(RepoSync, 'save_fileless_units', autospec=True)
    @mock.patch.object(metadata.MetadataFiles, 'get_group_file_handle',
                       autospec=True, return_value=StringIO())
    def test_closes_file(self, mock_get, mock_save):
        """
        make sure this closes its file handle
        """
        self.assertFalse(mock_get.return_value.closed)

        self.reposync.get_comps_file_units(self.metadata_files, mock.Mock(), "foo")

        self.assertTrue(mock_get.return_value.closed)

    @mock.patch.object(RepoSync, 'save_fileless_units', autospec=True,
                       side_effect=AttributeError)
    @mock.patch.object(metadata.MetadataFiles, 'get_group_file_handle',
                       autospec=True, return_value=StringIO())
    def test_closes_file_on_exception(self, mock_get, mock_save):
        """
        make sure this closes its file handle even if an exception is raised
        """
        self.assertFalse(mock_get.return_value.closed)

        self.assertRaises(AttributeError, self.reposync.get_comps_file_units,
                          self.metadata_files, mock.Mock(), "foo")

        self.assertTrue(mock_get.return_value.closed)

    @mock.patch.object(RepoSync, 'save_fileless_units', autospec=True)
    @mock.patch.object(metadata.MetadataFiles, 'get_group_file_handle',
                       autospec=True, return_value=StringIO())
    def test_with_metadata(self, mock_get, mock_save):
        mock_process_element = mock.Mock()
        self.reposync.get_comps_file_units(self.metadata_files, mock_process_element, "foo")

        self.assertEqual(mock_save.call_count, 1)
        self.assertEqual(mock_save.call_args[0][1], mock_get.return_value)
        self.assertEqual(mock_save.call_args[0][2], "foo")
        self.assertTrue(mock_save.call_args[0][3])

        # verify that the process func delegates properly with the correct repo id
        process_func = mock_save.call_args[0][3]
        fake_element = mock.MagicMock()
        process_func(fake_element)
        mock_process_element.assert_called_once_with(self.repo.id, fake_element)


class TestSaveFilelessUnits(BaseSyncTest):
    @mock.patch('pulp_rpm.plugins.importers.yum.existing.check_repo', autospec=True)
    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.packages.package_list_generator', autospec=True)
    def test_save_erratas_none_existing(self, mock_generator, mock_check_repo):
        """
        test where no errata already exist, so all should be saved
        """
        errata = tuple(model_factory.errata_models(3))
        mock_generator.return_value = errata
        mock_check_repo.return_value = [g.as_named_tuple for g in errata]
        self.conduit.init_unit = mock.MagicMock(spec_set=self.conduit.init_unit)
        self.conduit.save_unit = mock.MagicMock(spec_set=self.conduit.save_unit)
        file_handle = StringIO()

        self.reposync.save_fileless_units(file_handle, updateinfo.PACKAGE_TAG, updateinfo.process_package_element)

        mock_generator.assert_any_call(file_handle, updateinfo.PACKAGE_TAG, updateinfo.process_package_element)
        self.assertEqual(mock_generator.call_count, 2)
        self.assertEqual(mock_check_repo.call_count, 1)
        self.assertEqual(list(mock_check_repo.call_args[0][0]), [g.as_named_tuple for g in errata])
        self.assertEqual(mock_check_repo.call_args[0][1], self.conduit.get_units)

        for model in errata:
            self.conduit.init_unit.assert_any_call(model.TYPE, model.unit_key, model.metadata, None)
        self.conduit.save_unit.assert_any_call(self.conduit.init_unit.return_value)
        self.assertEqual(self.conduit.save_unit.call_count, 3)

    @mock.patch('pulp_rpm.plugins.importers.yum.existing.check_repo', autospec=True)
    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.packages.package_list_generator', autospec=True)
    def test_save_erratas_some_existing(self, mock_generator, mock_check_repo):
        """
        test where some errata already exist, so only some should be saved
        """
        errata = tuple(model_factory.errata_models(3))
        mock_generator.return_value = errata
        mock_check_repo.return_value = [g.as_named_tuple for g in errata[:2]]
        self.conduit.init_unit = mock.MagicMock(spec_set=self.conduit.init_unit)
        self.conduit.save_unit = mock.MagicMock(spec_set=self.conduit.save_unit)
        file_handle = StringIO()

        self.reposync.save_fileless_units(file_handle, updateinfo.PACKAGE_TAG, updateinfo.process_package_element)

        mock_generator.assert_any_call(file_handle, updateinfo.PACKAGE_TAG, updateinfo.process_package_element)
        self.assertEqual(mock_generator.call_count, 2)
        self.assertEqual(mock_check_repo.call_count, 1)
        self.assertEqual(list(mock_check_repo.call_args[0][0]), [g.as_named_tuple for g in errata])
        self.assertEqual(mock_check_repo.call_args[0][1], self.conduit.get_units)

        for model in errata[:2]:
            self.conduit.init_unit.assert_any_call(model.TYPE, model.unit_key, model.metadata, None)
        self.conduit.save_unit.assert_any_call(self.conduit.init_unit.return_value)
        self.assertEqual(self.conduit.save_unit.call_count, 2)

    @mock.patch('pulp_rpm.plugins.importers.yum.existing.check_repo', autospec=True)
    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.packages.package_list_generator', autospec=True)
    def test_save_groups_some_existing(self, mock_generator, mock_check_repo):
        """
        test where some groups already exist, and make sure all of them are
        saved regardless
        """
        groups = tuple(model_factory.group_models(3))
        mock_generator.return_value = groups
        mock_check_repo.return_value = [g.as_named_tuple for g in groups[:2]]
        self.conduit.init_unit = mock.MagicMock(spec_set=self.conduit.init_unit)
        self.conduit.save_unit = mock.MagicMock(spec_set=self.conduit.save_unit)
        file_handle = StringIO()

        self.reposync.save_fileless_units(file_handle, group.GROUP_TAG,
                                          group.process_group_element, mutable_type=True)

        mock_generator.assert_any_call(file_handle, group.GROUP_TAG, group.process_group_element)
        # skip the check for existing units since groups are mutable
        self.assertEqual(mock_generator.call_count, 1)
        self.assertEqual(mock_check_repo.call_count, 0)

        for model in groups:
            self.conduit.init_unit.assert_any_call(model.TYPE, model.unit_key, model.metadata, None)
        self.conduit.save_unit.assert_any_call(self.conduit.init_unit.return_value)
        self.assertEqual(self.conduit.save_unit.call_count, 3)

    @mock.patch('pulp_rpm.plugins.importers.yum.existing.check_repo', autospec=True)
    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.packages.package_list_generator', autospec=True)
    def test_save_erratas_all_existing(self, mock_generator, mock_check_repo):
        """
        test where all errata already exist, so none should be saved
        """
        errata = tuple(model_factory.errata_models(3))
        mock_generator.return_value = errata
        mock_check_repo.return_value = []
        self.conduit.init_unit = mock.MagicMock(spec_set=self.conduit.init_unit)
        self.conduit.save_unit = mock.MagicMock(spec_set=self.conduit.save_unit)
        file_handle = StringIO()

        self.reposync.save_fileless_units(file_handle, updateinfo.PACKAGE_TAG, updateinfo.process_package_element)

        mock_generator.assert_any_call(file_handle, updateinfo.PACKAGE_TAG, updateinfo.process_package_element)
        self.assertEqual(mock_generator.call_count, 2)
        self.assertEqual(mock_check_repo.call_count, 1)
        self.assertEqual(list(mock_check_repo.call_args[0][0]), [g.as_named_tuple for g in errata])
        self.assertEqual(mock_check_repo.call_args[0][1], self.conduit.get_units)

        self.assertEqual(self.conduit.save_unit.call_count, 0)


class TestIdentifyWantedVersions(BaseSyncTest):
    def test_keep_all(self):
        self.config.override_config[importer_constants.KEY_UNITS_RETAIN_OLD_COUNT] = None
        units = model_factory.rpm_models(3)
        for unit in units:
            unit.metadata['size'] = 1024

        result = sorted(self.reposync._identify_wanted_versions(units).keys())

        self.assertEqual([u.as_named_tuple for u in units], result)

    def test_keep_one(self):
        self.config.override_config[importer_constants.KEY_UNITS_RETAIN_OLD_COUNT] = 0
        units = model_factory.rpm_models(3, True)
        units.extend(model_factory.rpm_models(2))
        for unit in units:
            unit.metadata['size'] = 1024

        # the generator can yield results out of their original order, which is ok
        result = self.reposync._identify_wanted_versions(units)

        self.assertFalse(units[0].as_named_tuple in result)
        self.assertFalse(units[1].as_named_tuple in result)
        self.assertTrue(units[2].as_named_tuple in result)
        self.assertTrue(units[3].as_named_tuple in result)
        self.assertTrue(units[4].as_named_tuple in result)
        for size in result.values():
            self.assertEqual(size, 1024)

    def test_keep_two(self):
        self.config.override_config[importer_constants.KEY_UNITS_RETAIN_OLD_COUNT] = 1
        units = model_factory.rpm_models(3, True)
        units.extend(model_factory.rpm_models(2))
        for unit in units:
            unit.metadata['size'] = 1024

        # the generator can yield results out of their original order, which is ok
        result = self.reposync._identify_wanted_versions(units)

        self.assertFalse(units[0].as_named_tuple in result)
        self.assertTrue(units[1].as_named_tuple in result)
        self.assertTrue(units[2].as_named_tuple in result)
        self.assertTrue(units[3].as_named_tuple in result)
        self.assertTrue(units[4].as_named_tuple in result)
        for size in result.values():
            self.assertEqual(size, 1024)


class TestFilteredUnitGenerator(BaseSyncTest):
    def test_without_to_download(self):
        units = model_factory.rpm_models(3)

        result = list(self.reposync._filtered_unit_generator(units))

        self.assertEqual(units, result)

    def test_with_to_download(self):
        units = model_factory.rpm_models(3)
        # specify which we want
        to_download = set([unit.as_named_tuple for unit in units[:2]])

        result = list(self.reposync._filtered_unit_generator(units, to_download))

        # make sure we only got the ones we want
        self.assertEqual(result, units[:2])


class TestAlreadyDownloadedUnits(BaseSyncTest):

    @mock.patch('pulp.plugins.conduits.repo_sync.RepoSyncConduit.search_all_units', autospec=True)
    @mock.patch('pulp.plugins.conduits.repo_sync.RepoSyncConduit.save_unit', autospec=True)
    def test_associate_already_downloaded_units_positive(self, mock_save, mock_search_all_units):
        units = model_factory.rpm_models(3)
        mock_search_all_units.return_value = units
        for unit in units:
            unit.metadata['relativepath'] = 'test-relative-path'
            unit.metadata['filename'] = 'test-filename'
        result = associate_already_downloaded_units(models.RPM.TYPE, units, self.conduit)
        self.assertEqual(len(list(result)), 0)

    @mock.patch('pulp.plugins.conduits.repo_sync.RepoSyncConduit.search_all_units', autospec=True)
    @mock.patch('pulp.plugins.conduits.repo_sync.RepoSyncConduit.save_unit', autospec=True)
    def test_associate_already_downloaded_units_negative(self, mock_save, mock_search_all_units):
        mock_search_all_units.return_value = []
        units = model_factory.rpm_models(3)
        for unit in units:
            unit.metadata['relativepath'] = 'test-relative-path'
        result = associate_already_downloaded_units(models.RPM.TYPE, units, self.conduit)
        self.assertEqual(len(list(result)), 3)

