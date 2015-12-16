from copy import deepcopy
from cStringIO import StringIO
import os
import time

try:
    import unittest2 as unittest
except ImportError:
    import unittest

from nectar.config import DownloaderConfig
from nectar.downloaders.base import Downloader
from pulp.common.plugins import importer_constants
from pulp.plugins.conduits.repo_sync import RepoSyncConduit
from pulp.plugins.config import PluginCallConfiguration
from pulp.plugins.model import Repository, SyncReport, Unit
from pulp.server.exceptions import PulpCodedException
import pulp.server.managers.factory as manager_factory
import mock

from pulp_rpm.common import constants, ids
from pulp_rpm.devel.skip import skip_broken
from pulp_rpm.plugins import error_codes
from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.importers.yum.existing import check_all_and_associate
from pulp_rpm.plugins.importers.yum.parse import treeinfo
from pulp_rpm.plugins.importers.yum.repomd import metadata, group, updateinfo, packages, presto, \
    primary
from pulp_rpm.plugins.importers.yum.sync import RepoSync, CancelException
import model_factory


manager_factory.initialize()


class BaseSyncTest(unittest.TestCase):
    def setUp(self):
        self.url = 'http://pulpproject.org/'
        self.metadata_files = metadata.MetadataFiles(self.url, '/foo/bar', DownloaderConfig())
        self.metadata_files.download_repomd = mock.MagicMock()
        self.repo = Repository('repo1')
        self.conduit = RepoSyncConduit(self.repo.id, 'yum_importer')
        self.conduit.set_progress = mock.MagicMock(spec_set=self.conduit.set_progress)
        self.conduit.get_scratchpad = mock.MagicMock(spec_set=self.conduit.get_scratchpad,
                                                     return_value={})
        self.conduit.set_scratchpad = mock.MagicMock(spec_set=self.conduit.get_scratchpad)
        self.config = PluginCallConfiguration({}, {importer_constants.KEY_FEED: self.url})
        self.reposync = RepoSync(self.repo, self.conduit, self.config)
        self.downloader = Downloader(DownloaderConfig())


@skip_broken
class TestUpdateState(BaseSyncTest):
    def setUp(self):
        super(TestUpdateState, self).setUp()
        self.state_dict = {constants.PROGRESS_STATE_KEY: constants.STATE_NOT_STARTED}

    def test_normal_states(self):
        with self.reposync.update_state(self.state_dict):
            self.assertEqual(self.state_dict[constants.PROGRESS_STATE_KEY], constants.STATE_RUNNING)

        self.assertEqual(self.state_dict[constants.PROGRESS_STATE_KEY], constants.STATE_COMPLETE)

    def test_updates_progress(self):
        progress_call_count = self.conduit.set_progress.call_count

        with self.reposync.update_state(self.state_dict):
            self.assertEqual(self.conduit.set_progress.call_count, progress_call_count + 1)

        self.assertEqual(self.conduit.set_progress.call_count, progress_call_count + 2)

    def test_failure(self):
        with self.reposync.update_state(self.state_dict):
            self.state_dict[constants.PROGRESS_STATE_KEY] = constants.STATE_FAILED

        # make sure the context manager did not change the state from "failed"
        self.assertEqual(self.state_dict[constants.PROGRESS_STATE_KEY], constants.STATE_FAILED)

    def test_cancelled(self):
        with self.reposync.update_state(self.state_dict):
            self.state_dict[constants.PROGRESS_STATE_KEY] = constants.STATE_CANCELLED

        # make sure the context manager did not change the state from "failed"
        self.assertEqual(self.state_dict[constants.PROGRESS_STATE_KEY], constants.STATE_CANCELLED)

    def test_skipped_type(self):
        self.reposync.call_config.override_config[constants.CONFIG_SKIP] = ['sometype']

        with self.reposync.update_state(self.state_dict, 'sometype') as skip:
            self.assertTrue(skip is True)
            self.assertEqual(self.state_dict[constants.PROGRESS_STATE_KEY], constants.STATE_SKIPPED)

        self.assertEqual(self.state_dict[constants.PROGRESS_STATE_KEY], constants.STATE_SKIPPED)

    def test_nonskipped_type(self):
        self.reposync.call_config.override_config[constants.CONFIG_SKIP] = ['sometype']

        with self.reposync.update_state(self.state_dict, 'someothertype') as skip:
            self.assertTrue(skip is False)
            self.assertEqual(self.state_dict[constants.PROGRESS_STATE_KEY], constants.STATE_RUNNING)

        self.assertEqual(self.state_dict[constants.PROGRESS_STATE_KEY], constants.STATE_COMPLETE)


@skip_broken
class TestSaveRepomdRevision(BaseSyncTest):
    def test_empty_scratchpad(self):
        self.reposync.current_revision = 1234

        self.reposync.save_repomd_revision()

        self.conduit.set_scratchpad.assert_called_once_with({
            constants.REPOMD_REVISION_KEY: 1234,
            constants.PREVIOUS_SKIP_LIST: [],
        })

    def test_existing_scratchpad(self):
        self.conduit.get_scratchpad.return_value = {'a': 2}
        self.reposync.current_revision = 1234

        self.reposync.save_repomd_revision()

        expected = {
            constants.REPOMD_REVISION_KEY: 1234,
            constants.PREVIOUS_SKIP_LIST: [],
            'a': 2,
        }
        self.conduit.set_scratchpad.assert_called_once_with(expected)

    def test_no_existing_scratchpad(self):
        self.conduit.get_scratchpad.return_value = None
        self.reposync.current_revision = 1234

        self.reposync.save_repomd_revision()

        self.conduit.set_scratchpad.assert_called_once_with({
            constants.REPOMD_REVISION_KEY: 1234,
            constants.PREVIOUS_SKIP_LIST: [],
        })

    def test_with_errors(self):
        """
        No update should happen if there were errors
        """
        self.reposync.content_report['error_details'] = [{'a': 2}]

        self.reposync.save_repomd_revision()

        self.assertEqual(self.conduit.set_scratchpad.call_count, 0)

    def test_state_failed(self):
        """
        No update should happen if the task failed
        """
        self.reposync.content_report[constants.PROGRESS_STATE_KEY] = constants.STATE_FAILED

        self.reposync.save_repomd_revision()

        self.assertEqual(self.conduit.set_scratchpad.call_count, 0)

    def test_state_cancelled(self):
        """
        No update should happen if the task was cancelled
        """
        self.reposync.content_report[constants.PROGRESS_STATE_KEY] = constants.STATE_CANCELLED

        self.reposync.save_repomd_revision()

        self.assertEqual(self.conduit.set_scratchpad.call_count, 0)


@skip_broken
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

    def test_nothing_skipped(self):
        self.assertEqual(self.reposync.call_config.get(constants.CONFIG_SKIP, []), [])


@skip_broken
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


@skip_broken
class TestSyncFeed(BaseSyncTest):

    @mock.patch('pulp_rpm.plugins.importers.yum.sync.RepoSync.check_metadata',
                spec_set=RepoSync.check_metadata)
    def test_with_trailing_slash(self, mock_check_metadata):

        ret = self.reposync.sync_feed

        self.assertEqual(ret, [self.url])

    @mock.patch('pulp_rpm.plugins.importers.yum.sync.RepoSync.check_metadata',
                spec_set=RepoSync.check_metadata)
    def test_without_trailing_slash(self, mock_check_metadata):

        # it should add back the trailing slash if not present
        self.config.override_config[importer_constants.KEY_FEED] = self.url.rstrip('/')

        ret = self.reposync.sync_feed

        self.assertEqual(ret, [self.url])

    @mock.patch('pulp_rpm.plugins.importers.yum.sync.RepoSync.check_metadata',
                spec_set=RepoSync.check_metadata)
    def test_query_without_trailing_slash(self, mock_check_metadata):
        # it should add back the trailing slash if not present without changing the query string
        query = '?foo=bar'
        self.config.override_config[importer_constants.KEY_FEED] = self.url.rstrip('/') + query

        ret = self.reposync.sync_feed
        expected = [self.url + query]

        self.assertEqual(ret, expected)

    def test_repo_url_is_none(self):

        self.config.override_config[importer_constants.KEY_FEED] = None

        ret = self.reposync.sync_feed

        self.assertEqual(ret, [None])

    @mock.patch('pulp_rpm.plugins.importers.yum.sync.RepoSync._parse_as_mirrorlist',
                spec_set=RepoSync._parse_as_mirrorlist)
    @mock.patch('pulp_rpm.plugins.importers.yum.sync.RepoSync.check_metadata',
                spec_set=RepoSync.check_metadata)
    def test_repo_url_is_url(self, mock_check_metadata, mock_parse_mirrorlist):

        ret = self.reposync.sync_feed

        self.assertEqual(ret, [self.url])

        mock_check_metadata.assert_called_once_with(self.url)
        self.assertEqual(mock_parse_mirrorlist.call_count, 0)

    @mock.patch('pulp_rpm.plugins.importers.yum.sync.RepoSync.check_metadata',
                spec_set=RepoSync.check_metadata)
    @mock.patch('pulp_rpm.plugins.importers.yum.sync.RepoSync._parse_as_mirrorlist',
                spec_set=RepoSync._parse_as_mirrorlist)
    def test_repo_url_is_mirror(self, mock_parse_mirrorlist, mock_check_metadata):

        mock_check_metadata.side_effect = PulpCodedException()

        ret = self.reposync.sync_feed
        self.assertFalse(ret == [self.url])

        mock_check_metadata.assert_called_once_with(self.url)
        mock_parse_mirrorlist.assert_called_once_with(self.url)

    @mock.patch('shutil.rmtree', autospec=True)
    @mock.patch('tempfile.mkdtemp', autospec=True)
    @mock.patch('pulp_rpm.plugins.importers.yum.sync.RepoSync.check_metadata',
                spec_set=RepoSync.check_metadata)
    def test_removes_tmp_dir(self, mock_check_matadata, mock_mkdtemp, mock_rmtree):

        self.reposync.sync_feed

        mock_rmtree.assert_called_with(mock_mkdtemp.return_value, ignore_errors=True)


@skip_broken
class TestParseMirrorlist(BaseSyncTest):

    @mock.patch('pulp_rpm.plugins.importers.yum.sync.DownloadRequest')
    @mock.patch('pulp_rpm.plugins.importers.yum.sync.nectar_factory')
    @mock.patch('pulp_rpm.plugins.importers.yum.sync.StringIO')
    def test_url_was_parsed(self, mock_string, mock_nectar, mock_request):

        url_list = ['https://some/url/', '#https://some/url/']
        mock_string.return_value.read.return_value.split.return_value = url_list

        ret = self.reposync._parse_as_mirrorlist('http://mirrorlist.mymirrors.org/')

        self.assertEqual(ret, ['https://some/url/'])


@skip_broken
class TestRun(BaseSyncTest):
    def setUp(self):
        super(TestRun, self).setUp()
        self.reposync.check_metadata = mock.MagicMock(spec_set=self.reposync.check_metadata,
                                                      return_value=self.metadata_files)
        self.reposync.get_metadata = mock.MagicMock(spec_set=self.reposync.get_metadata,
                                                    return_value=self.metadata_files)
        self.reposync.update_content = mock.MagicMock(spec_set=self.reposync.update_content)
        self.reposync.get_errata = mock.MagicMock(spec_set=self.reposync.get_errata)
        self.reposync.get_comps_file_units = mock.MagicMock(
            spec_set=self.reposync.get_comps_file_units)

        self.reposync.set_progress = mock.MagicMock(spec_set=self.reposync.set_progress)
        self.reposync.save_repomd_revision = mock.MagicMock(
            spec_set=self.reposync.save_repomd_revision)

    def test_sync_feed_is_empty_list(self):

        self.reposync.check_metadata = mock.MagicMock(spec_set=self.reposync.check_metadata,
                                                      side_effect=PulpCodedException())
        self.reposync._parse_as_mirrorlist = mock.MagicMock(
            spec_set=self.reposync._parse_as_mirrorlist,
            return_value=[])
        with self.assertRaises(PulpCodedException) as e:
            self.reposync.run()
        self.assertEquals(e.exception.error_code, error_codes.RPM1004)
        self.assertEquals(e.exception.error_data['reason'], 'Not found')

    @mock.patch('shutil.rmtree', autospec=True)
    @mock.patch('tempfile.mkdtemp', autospec=True)
    def test_removes_tmp_dir_after_exception(self, mock_mkdtemp, mock_rmtree):
        self.reposync.get_metadata.side_effect = ValueError

        self.reposync.run()

        mock_rmtree.assert_called_with(mock_mkdtemp.return_value, ignore_errors=True)

    @mock.patch('pulp_rpm.plugins.importers.yum.parse.treeinfo.sync', autospec=True)
    @mock.patch('shutil.rmtree', autospec=True)
    @mock.patch('tempfile.mkdtemp', autospec=True)
    def test_calls_workflow(self, mock_mkdtemp, mock_rmtree, mock_treeinfo_sync):
        report = self.reposync.run()

        self.assertTrue(report.success_flag)
        self.assertFalse(report.canceled_flag)

        self.reposync.check_metadata.assert_called_with(self.url)
        self.reposync.get_metadata.assert_called_once_with(self.metadata_files)
        self.reposync.update_content.assert_called_once_with(self.metadata_files, self.url)
        self.reposync.get_errata.assert_called_once_with(self.metadata_files)
        calls = [mock.call(self.metadata_files, group.process_group_element, group.GROUP_TAG),
                 mock.call(self.metadata_files, group.process_environment_element,
                           group.ENVIRONMENT_TAG),
                 mock.call(self.metadata_files, group.process_category_element, group.CATEGORY_TAG)]
        self.reposync.get_comps_file_units.assert_has_calls(calls, any_order=True)
        self.reposync.save_repomd_revision.assert_called_once_with()

        mock_treeinfo_sync.assert_called_once_with(self.conduit, self.url,
                                                   mock_mkdtemp.return_value,
                                                   self.reposync.nectar_config,
                                                   self.reposync.distribution_report,
                                                   self.reposync.set_progress)
        # make sure we cleaned up the temporary directory
        mock_rmtree.assert_called_with(mock_mkdtemp.return_value, ignore_errors=True)

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
            self.assertEqual(report['state'], constants.STATE_COMPLETE, 'step: %s' % step_name)

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

    @mock.patch('shutil.rmtree', autospec=True)
    @mock.patch('tempfile.mkdtemp', autospec=True)
    def test_raise(self, mock_mkdtemp, mock_rmtree):
        self.reposync.get_metadata.side_effect = PulpCodedException(error_codes.RPM1006)
        with self.assertRaises(PulpCodedException) as e:
            self.reposync.run()
        self.assertEquals(len(self.reposync.sync_feed), 1)
        self.assertEquals(e.exception.error_code, error_codes.RPM1006)

    @mock.patch('shutil.rmtree', autospec=True)
    @mock.patch('tempfile.mkdtemp', autospec=True)
    def test_continue(self, mock_mkdtemp, mock_rmtree):
        self.reposync.check_metadata.side_effect = PulpCodedException(error_codes.RPM1006)
        self.reposync.get_metadata.side_effect = PulpCodedException(error_codes.RPM1006)
        self.reposync._parse_as_mirrorlist = mock.MagicMock(
            spec_set=self.reposync._parse_as_mirrorlist,
            return_value=['https://some/url/', 'https://some/url/'])
        with self.assertRaises(PulpCodedException):
            self.reposync.run()
        self.assertEquals(len(self.reposync.sync_feed), 2)

    def test_fail_on_missing_feed(self):
        self.config = PluginCallConfiguration({}, {})
        reposync = RepoSync(self.repo, self.conduit, self.config)
        reposync.call_config.get(importer_constants.KEY_FEED)

        with self.assertRaises(PulpCodedException) as e:
            reposync.run()
        self.assertEquals(e.exception.error_code, error_codes.RPM1005)


@skip_broken
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


@skip_broken
class TestGetMetadata(BaseSyncTest):
    def setUp(self):
        super(TestGetMetadata, self).setUp()
        self.reposync.tmp_dir = '/tmp'

    @mock.patch.object(metadata, 'MetadataFiles', autospec=True)
    def test_metadata_unchanged(self, mock_metadata_files):
        mock_metadata_instance = mock_metadata_files.return_value
        mock_metadata_instance.revision = 1234
        mock_metadata_instance.downloader = mock.MagicMock()
        self.conduit.get_scratchpad.return_value = {constants.REPOMD_REVISION_KEY: 1234}

        ret = self.reposync.get_metadata(self.reposync.check_metadata(self.url))

        self.assertEqual(self.reposync.current_revision, 1234)
        self.assertTrue(self.reposync.skip_repomd_steps is True)
        self.assertEqual(mock_metadata_instance.download_metadata_files.call_count, 0)
        self.assertTrue(ret is mock_metadata_instance)

    @mock.patch.object(metadata, 'MetadataFiles', autospec=True)
    def test_metadata_revision_zero(self, mock_metadata_files):
        """In this case, with the default revision of 0, a full sync should be performed"""
        mock_metadata_instance = mock_metadata_files.return_value
        mock_metadata_instance.revision = 0
        mock_metadata_instance.downloader = mock.MagicMock()
        self.conduit.get_scratchpad.return_value = {constants.REPOMD_REVISION_KEY: 0}
        self.reposync.import_unknown_metadata_files = mock.MagicMock(
            spec_set=self.reposync.import_unknown_metadata_files)

        self.reposync.check_metadata(self.url)
        self.reposync.get_metadata(self.reposync.check_metadata(self.url))

        self.assertTrue(self.reposync.skip_repomd_steps is False)
        self.assertEqual(mock_metadata_instance.download_metadata_files.call_count, 1)

    @mock.patch.object(metadata, 'MetadataFiles', autospec=True)
    def test_metadata_unchanged_but_skip_list_shrank(self, mock_metadata_files):
        """
        Test the case where the metadata didn't change, but the skip list is
        smaller. In that case, the full sync should happen even though the
        metadata didn't change.
        """
        mock_metadata_instance = mock_metadata_files.return_value
        mock_metadata_instance.revision = 1234
        mock_metadata_instance.downloader = mock.MagicMock()
        self.conduit.get_scratchpad.return_value = {
            constants.REPOMD_REVISION_KEY: 1234,
            constants.PREVIOUS_SKIP_LIST: ['foo', 'bar'],
        }
        self.config.override_config[constants.CONFIG_SKIP] = ['foo']
        self.reposync.import_unknown_metadata_files = mock.MagicMock(
            spec_set=self.reposync.import_unknown_metadata_files)

        self.reposync.get_metadata(self.reposync.check_metadata(self.url))

        self.assertTrue(self.reposync.skip_repomd_steps is False)
        self.assertEqual(mock_metadata_instance.download_metadata_files.call_count, 1)

    @mock.patch.object(metadata, 'MetadataFiles', autospec=True)
    def test_failed_download(self, mock_metadata_files):
        mock_metadata_files.return_value = self.metadata_files
        self.metadata_files.download_repomd = mock.MagicMock(side_effect=IOError, autospec=True)

        with self.assertRaises(PulpCodedException) as e:
            self.reposync.check_metadata(self.url)

        self.assertEqual(e.exception.error_code, error_codes.RPM1004)

    @mock.patch.object(metadata, 'MetadataFiles', autospec=True)
    def test_failed_download_repomd(self, mock_metadata_files):
        mock_metadata_files.return_value = self.metadata_files
        self.metadata_files.download_repomd = mock.MagicMock(side_effect=IOError, autospec=True)

        with self.assertRaises(PulpCodedException) as e:
            self.reposync.check_metadata(self.url)

        self.assertEqual(e.exception.error_code, error_codes.RPM1004)

    @mock.patch.object(metadata, 'MetadataFiles', autospec=True)
    def test_failed_parse_repomd(self, mock_metadata_files):
        mock_metadata_files.return_value = self.metadata_files
        self.metadata_files.download_repomd = mock.MagicMock(autospec=True)
        self.metadata_files.parse_repomd = mock.MagicMock(side_effect=ValueError, autospec=True)

        with self.assertRaises(PulpCodedException) as e:
            self.reposync.check_metadata(self.url)

        self.assertEqual(e.exception.error_code, error_codes.RPM1006)

    @mock.patch.object(metadata, 'MetadataFiles', autospec=True)
    def test_success(self, mock_metadata_files):
        mock_metadata_instance = mock_metadata_files.return_value
        mock_metadata_instance.revision = int(time.time()) + 60 * 60 * 24
        mock_metadata_instance.downloader = mock.MagicMock()
        self.reposync.import_unknown_metadata_files = mock.MagicMock(
            spec_set=self.reposync.import_unknown_metadata_files)

        ret = self.reposync.get_metadata(self.reposync.check_metadata(self.url))

        self.assertEqual(ret, mock_metadata_instance)
        self.assertTrue(self.reposync.skip_repomd_steps is False)
        mock_metadata_instance.download_repomd.assert_called_once_with()
        mock_metadata_instance.parse_repomd.assert_called_once_with()
        mock_metadata_instance.download_metadata_files.assert_called_once_with()
        mock_metadata_instance.generate_dbs.assert_called_once_with()
        self.reposync.import_unknown_metadata_files.assert_called_once_with(mock_metadata_instance)


@skip_broken
class TestSaveMetadataChecksum(BaseSyncTest):
    """
    This class contains tests for the save_default_metadata_checksum_on_repo() method.
    """

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

    def test_sanitizes_checksum_type(self):
        """
        Ensure that the method properly sanitizes the checksum type.
        """
        self.conduit.get_repo_scratchpad = mock.Mock(return_value={})
        self.conduit.set_repo_scratchpad = mock.Mock()

        file_info = deepcopy(metadata.FILE_INFO_SKEL)
        file_info['checksum']['algorithm'] = 'sha'
        self.metadata_files.metadata['foo'] = file_info

        self.reposync.save_default_metadata_checksum_on_repo(self.metadata_files)
        self.conduit.set_repo_scratchpad.assert_called_once_with(
            {constants.SCRATCHPAD_DEFAULT_METADATA_CHECKSUM: 'sha1'})


@skip_broken
class ImportUnknownMetadataFiles(BaseSyncTest):
    """
    This class contains tests for the RepoSync.import_unknown_metadata_files function.
    """

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

    @mock.patch('shutil.copyfile', autospec=True)
    def test_sanitizes_checksum_type(self, mock_copy):
        """
        Assert that the method sanitizes the checksum type.
        """
        self.metadata_files.metadata['fake_type'] = {
            'checksum': {'hex_digest': 'checksum_value', 'algorithm': 'sha'},
            'local_path': 'path/to/fake_type.xml'
        }

        self.reposync.import_unknown_metadata_files(self.metadata_files)

        self.conduit.init_unit.assert_called_once_with(
            models.YumMetadataFile.TYPE,
            {'repo_id': self.repo.id, 'data_type': 'fake_type'},
            {'checksum': 'checksum_value', 'checksum_type': 'sha1'},
            '%s/fake_type.xml' % self.repo.id,
        )
        self.conduit.save_unit.assert_called_once_with(self.conduit.init_unit.return_value)
        mock_copy.assert_called_once_with('path/to/fake_type.xml',
                                          self.conduit.init_unit.return_value.storage_path)


@skip_broken
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

        self.reposync.update_content(self.metadata_files, self.url)

        mock_decide.assert_called_once_with(self.metadata_files)
        mock_download.assert_called_once_with(self.metadata_files, rpms, drpms, self.url)
        mock_purge.assert_called_once_with(self.metadata_files, self.conduit, self.config)


@skip_broken
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


@skip_broken
class TestDecideRPMsToDownload(BaseSyncTest):
    def test_skip_rpms(self):
        self.config.override_config[constants.CONFIG_SKIP] = [models.RPM.TYPE]

        ret = self.reposync._decide_rpms_to_download(self.metadata_files)

        self.assertEqual(ret, (set(), 0, 0))

    @mock.patch('__builtin__.open', autospec=True)
    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.packages.package_list_generator',
                autospec=True)
    @mock.patch('pulp_rpm.plugins.importers.yum.sync.RepoSync._identify_wanted_versions',
                spec_set=RepoSync._identify_wanted_versions)
    @mock.patch('pulp_rpm.plugins.importers.yum.existing.check_repo', autospec=True)
    def test_calls_identify_wanted_and_existing(self, mock_check_repo, mock_identify,
                                                mock_generator, mock_open):
        primary_file = StringIO()
        mock_open.return_value = primary_file
        model = model_factory.rpm_models(1)[0]
        self.metadata_files.metadata[primary.METADATA_FILE_NAME] = \
            {'local_path': '/path/to/primary'}
        mock_generator.return_value = [model.as_named_tuple]
        mock_identify.return_value = {model.as_named_tuple: 1024}
        mock_check_repo.return_value = set([model.as_named_tuple])

        with mock.patch.object(self.conduit, 'search_all_units'):
            ret = self.reposync._decide_rpms_to_download(self.metadata_files)

        self.assertEqual(ret, (set([model.as_named_tuple]), 1, 1024))
        mock_open.assert_called_once_with('/path/to/primary', 'r')
        mock_generator.assert_called_once_with(primary_file, primary.PACKAGE_TAG,
                                               primary.process_package_element)
        mock_identify.assert_called_once_with(mock_generator.return_value)
        self.assertTrue(primary_file.closed)

    @mock.patch('__builtin__.open', autospec=True)
    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.packages.package_list_generator',
                autospec=True)
    def test_closes_file_on_exception(self, mock_generator, mock_open):
        primary_file = StringIO()
        mock_open.return_value = primary_file
        self.metadata_files.metadata[primary.METADATA_FILE_NAME] = \
            {'local_path': '/path/to/primary'}
        mock_generator.side_effect = ValueError

        self.assertRaises(ValueError, self.reposync._decide_rpms_to_download,
                          self.metadata_files)

        mock_open.assert_called_once_with('/path/to/primary', 'r')
        self.assertTrue(primary_file.closed)


@skip_broken
class TestDecideDRPMsToDownload(BaseSyncTest):
    def test_skip_drpms(self):
        self.config.override_config[constants.CONFIG_SKIP] = [models.DRPM.TYPE]

        ret = self.reposync._decide_drpms_to_download(self.metadata_files)

        self.assertEqual(ret, (set(), 0, 0))

    def test_no_file_available(self):
        self.assertTrue(
            self.metadata_files.get_metadata_file_handle(presto.METADATA_FILE_NAMES[0]) is None)

        ret = self.reposync._decide_drpms_to_download(self.metadata_files)

        self.assertEqual(ret, (set(), 0, 0))

    @mock.patch('__builtin__.open', autospec=True)
    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.packages.package_list_generator',
                autospec=True)
    @mock.patch('pulp_rpm.plugins.importers.yum.sync.RepoSync._identify_wanted_versions',
                spec_set=RepoSync._identify_wanted_versions)
    @mock.patch('pulp_rpm.plugins.importers.yum.existing.check_repo', autospec=True)
    def test_calls_identify_wanted_and_existing(self, mock_check_repo, mock_identify,
                                                mock_generator, mock_open):
        presto_file = StringIO()
        mock_open.return_value = presto_file
        model = model_factory.drpm_models(1)[0]
        self.metadata_files.metadata[presto.METADATA_FILE_NAMES[0]] = \
            {'local_path': '/path/to/presto'}
        mock_generator.return_value = [model.as_named_tuple]
        mock_identify.return_value = {model.as_named_tuple: 1024}
        mock_check_repo.return_value = set([model.as_named_tuple])

        with mock.patch.object(self.conduit, 'search_all_units'):
            ret = self.reposync._decide_drpms_to_download(self.metadata_files)

        self.assertEqual(ret, (set([model.as_named_tuple]), 1, 1024))
        mock_open.assert_called_once_with('/path/to/presto', 'r')
        mock_generator.assert_called_once_with(presto_file, presto.PACKAGE_TAG,
                                               presto.process_package_element)
        mock_identify.assert_called_once_with(mock_generator.return_value)
        self.assertTrue(presto_file.closed)

    @mock.patch('__builtin__.open', autospec=True)
    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.packages.package_list_generator',
                autospec=True)
    def test_closes_file_on_exception(self, mock_generator, mock_open):
        presto_file = StringIO()
        mock_open.return_value = presto_file
        self.metadata_files.metadata[presto.METADATA_FILE_NAMES[0]] = \
            {'local_path': '/path/to/presto'}
        mock_generator.side_effect = ValueError

        self.assertRaises(ValueError, self.reposync._decide_drpms_to_download,
                          self.metadata_files)

        mock_open.assert_called_once_with('/path/to/presto', 'r')
        self.assertTrue(presto_file.closed)


@skip_broken
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
        # The 2nd/3rd calls are for the prestodelta, deltaninfo files
        mock_package_list_generator.side_effect = iter([model_factory.rpm_models(3),
                                                        model_factory.drpm_models(3),
                                                        None])

        report = self.reposync.download(self.metadata_files, set(), set(), self.url)

        self.assertTrue(report.success_flag)
        self.assertEqual(report.added_count, 0)
        self.assertEqual(report.removed_count, 0)
        self.assertEqual(report.updated_count, 0)

    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.alternate.ContentContainer')
    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.nectar_factory.create_downloader',
                autospec=True)
    @mock.patch.object(packages, 'package_list_generator', autospec=True)
    def test_rpms_to_download(self, mock_package_list_generator, mock_create_downloader,
                              mock_container):
        """
        test with only RPMs specified to download
        """
        file_handle = StringIO()
        self.metadata_files.get_metadata_file_handle = mock.MagicMock(
            spec_set=self.metadata_files.get_metadata_file_handle,
            side_effect=[file_handle, None, None],  # None means it will skip DRPMs
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

        fake_container = mock.Mock()
        fake_container.refresh.return_value = {}
        mock_container.return_value = fake_container

        # call download, passing in only two of the 3 rpms as units we want
        self.reposync.download(self.metadata_files,
                               set(m.as_named_tuple for m in rpms[:2]), set(), self.url)

        # make sure we skipped DRPMs
        self.assertEqual(self.downloader.download.call_count, 0)
        self.assertEqual(mock_package_list_generator.call_count, 1)

        # verify that the download requests were correct
        requests = list(fake_container.download.call_args[0][2])
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0].url, os.path.join(self.url, self.RELATIVEPATH))
        self.assertEqual(requests[0].destination,
                         os.path.join(self.reposync.tmp_dir, self.RELATIVEPATH))
        self.assertTrue(requests[0].data is rpms[0])
        self.assertEqual(requests[1].url, os.path.join(self.url, self.RELATIVEPATH))
        self.assertEqual(requests[1].destination,
                         os.path.join(self.reposync.tmp_dir, self.RELATIVEPATH))
        self.assertTrue(requests[1].data is rpms[1])
        self.assertTrue(file_handle.closed)

    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.alternate.ContentContainer')
    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.nectar_factory.create_downloader',
                autospec=True)
    @mock.patch.object(packages, 'package_list_generator', autospec=True)
    def test_drpms_to_download(self, mock_package_list_generator, mock_create_downloader,
                               mock_container):
        """
        test with only DRPMs specified to download
        """
        file_handle = StringIO()
        self.metadata_files.get_metadata_file_handle = mock.MagicMock(
            spec_set=self.metadata_files.get_metadata_file_handle,
            # The second and third time this method is called are to get the deltainfo/prestodelta
            # files
            side_effect=[StringIO(), file_handle, file_handle],
        )
        drpms = model_factory.drpm_models(3)
        for drpm in drpms:
            drpm.metadata['relativepath'] = ''

        # including drpms twice catches both possible prestodelta file names
        mock_package_list_generator.side_effect = iter([[], drpms, drpms])
        self.downloader.download = mock.MagicMock(spec_set=self.downloader.download)
        mock_create_downloader.return_value = self.downloader

        fake_container = mock.Mock()
        fake_container.refresh.return_value = {}
        mock_container.return_value = fake_container

        # call download, passing in only two of the 3 rpms as units we want
        self.reposync.download(self.metadata_files, set(),
                               set(m.as_named_tuple for m in drpms[:2]), self.url)

        # check download call twice since each drpm metadata file referenced 1 drpm
        self.assertEqual(self.downloader.download.call_count, 2)
        # Package list generator gets called 3 time, once for the rpms and twice for drpms
        self.assertEqual(mock_package_list_generator.call_count, 3)

        # verify that the download requests were correct
        requests = list(self.downloader.download.call_args[0][0])
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0].url, os.path.join(self.url, drpms[0].filename))
        self.assertEqual(requests[0].destination,
                         os.path.join(self.reposync.tmp_dir, drpms[0].filename))
        self.assertTrue(requests[0].data is drpms[0])
        self.assertEqual(requests[1].url, os.path.join(self.url, drpms[1].filename))
        self.assertEqual(requests[1].destination,
                         os.path.join(self.reposync.tmp_dir, drpms[1].filename))
        self.assertTrue(requests[1].data is drpms[1])
        self.assertTrue(file_handle.closed)


@skip_broken
class TestQueryAuthToken(BaseSyncTest):
    def setUp(self):
        super(TestQueryAuthToken, self).setUp()
        self.qstring = '?letmein'
        self.config = PluginCallConfiguration({}, {importer_constants.KEY_FEED: self.url,
                                                   'query_auth_token': self.qstring[1:]})
        self.reposync = RepoSync(self.repo, self.conduit, self.config)
        self.reposync.tmp_dir = '/dev/null/tmp'

    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.alternate.ContentContainer')
    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.nectar_factory.create_downloader',
                autospec=True)
    @mock.patch.object(packages, 'package_list_generator', autospec=True)
    def test_query_auth_token_append(
            self, mock_package_list_generator, mock_create_downloader, mock_container):
        """
        test RPMs to download with auth token

        tests the main feed URL and individual package URLs have the auth token applied
        """
        file_handle = StringIO()
        self.metadata_files = metadata.MetadataFiles(self.url, '/foo/bar', DownloaderConfig(),
                                                     self.reposync._url_modify)
        self.assertEqual(self.metadata_files.repo_url, self.url + self.qstring)
        self.metadata_files.get_metadata_file_handle = mock.MagicMock(
            spec_set=self.metadata_files.get_metadata_file_handle,
            side_effect=[file_handle, None, None],  # None means it will skip DRPMs
        )

        package_names = []
        rpms = model_factory.rpm_models(3)
        for i, rpm in enumerate(rpms):
            package = 'package-{0}.rpm'.format(i)
            package_names.append(package)
            rpm.metadata['filename'] = rpm.metadata['relativepath'] = package

        mock_package_list_generator.return_value = rpms
        self.downloader.download = mock.MagicMock(spec_set=self.downloader.download)
        mock_create_downloader.return_value = self.downloader

        fake_container = mock.Mock()
        fake_container.refresh.return_value = {}
        mock_container.return_value = fake_container

        self.reposync.download(self.metadata_files, set(m.as_named_tuple for m in rpms), set(),
                               self.url)

        requests = list(fake_container.download.call_args[0][2])
        # the individual package urls
        for i, request in enumerate(requests):
            self.assertEqual(request.url, os.path.join(self.url, package_names[i]) + self.qstring)

    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles', autospec=True)
    def test_reposync_copies_url_modify(self, mock_metadata_files):
        # test that RepoSync properly passes its URL modifier to MetadataFiles
        self.assertTrue(mock_metadata_files.call_args is None)
        self.reposync.check_metadata('blah')

        # should only be one call
        self.assertEqual(mock_metadata_files.call_count, 1)
        self.assertTrue(mock_metadata_files.call_args[0][3] is self.reposync._url_modify)

    def test_reposync_skip_config(self):
        skip_config = self.reposync.call_config.get(constants.CONFIG_SKIP)
        self.assertTrue(skip_config is not None)
        for type_id in ids.QUERY_AUTH_TOKEN_UNSUPPORTED:
            self.assertTrue(type_id in skip_config)

    def test_units_skipped(self):
        # If query_auth_token is in the importer config, the skip config must exist...
        skip_config = self.reposync.call_config.get(constants.CONFIG_SKIP)
        self.assertTrue(skip_config is not None)

        # ...and all of the unsupported types must be configured to skip
        for unit_type in ids.QUERY_AUTH_TOKEN_UNSUPPORTED:
            self.assertTrue(unit_type in skip_config)


@skip_broken
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

        def cancel_side_effect(*args, **kwargs):
            self.reposync.cancel()

        self.reposync.check_metadata = mock.MagicMock(spec_set=self.reposync.check_metadata)
        self.reposync.get_metadata = mock.MagicMock(side_effect=cancel_side_effect,
                                                    spec_set=self.reposync.get_metadata)
        self.reposync.save_default_metadata_checksum_on_repo = mock.MagicMock()
        report = self.reposync.run()

        # this proves that the progress was correctly set and a corresponding report
        # was made
        self.assertTrue(report.canceled_flag)
        self.assertEqual(report.details['metadata']['state'], constants.STATE_CANCELLED)


@skip_broken
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
                                          updateinfo.process_package_element,
                                          additive_type=True)


@skip_broken
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


@skip_broken
class TestSaveFilelessUnits(BaseSyncTest):
    @mock.patch('pulp_rpm.plugins.importers.yum.existing.check_repo', autospec=True)
    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.packages.package_list_generator',
                autospec=True)
    def test_save_fileless_units(self, mock_generator, mock_check_repo):
        """
        test the "base" use case for save_fileless_units.

        Note that we are using errata as the unit here, but errata are typically
        saved with "additive_type" set to True.

        """
        errata = tuple(model_factory.errata_models(3))
        mock_generator.return_value = errata
        mock_check_repo.return_value = [g.as_named_tuple for g in errata]
        self.conduit.init_unit = mock.MagicMock(spec_set=self.conduit.init_unit)
        self.conduit.save_unit = mock.MagicMock(spec_set=self.conduit.save_unit)
        file_handle = StringIO()

        self.reposync.save_fileless_units(file_handle, updateinfo.PACKAGE_TAG,
                                          updateinfo.process_package_element)

        mock_generator.assert_any_call(file_handle, updateinfo.PACKAGE_TAG,
                                       updateinfo.process_package_element)
        self.assertEqual(mock_generator.call_count, 2)
        self.assertEqual(mock_check_repo.call_count, 1)
        self.assertEqual(list(mock_check_repo.call_args[0][0]), [g.as_named_tuple for g in errata])
        self.assertEqual(mock_check_repo.call_args[0][1], self.conduit.get_units)

        for model in errata:
            self.conduit.init_unit.assert_any_call(model.TYPE, model.unit_key, model.metadata, None)
        self.conduit.save_unit.assert_any_call(self.conduit.init_unit.return_value)
        self.assertEqual(self.conduit.save_unit.call_count, 3)

    def test_save_fileless_units_bad_args(self):
        """
        Ensure that an error is raised if save_fileless_units is called with
        mutually exclusive args
        """
        self.assertRaises(PulpCodedException, self.reposync.save_fileless_units,
                          None, None, None, mutable_type=True, additive_type=True)

    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.packages.'
                'package_list_generator', autospec=True)
    @mock.patch('pulp.plugins.conduits.mixins.SearchUnitsMixin.'
                'find_unit_by_unit_key', autospec=True)
    @mock.patch('pulp_rpm.plugins.importers.yum.sync.RepoSync._concatenate_units', autospec=True)
    def test_save_erratas_none_existing(self, mock_concat, mock_find_unit, mock_generator):
        """
        test where no errata already exist, so all should be saved
        """
        errata = tuple(model_factory.errata_models(3))
        mock_generator.return_value = errata
        self.conduit.init_unit = mock.MagicMock(spec_set=self.conduit.init_unit)
        self.conduit.save_unit = mock.MagicMock(spec_set=self.conduit.save_unit)
        # all of these units are new, find_unit_by_unit_key will return None
        mock_find_unit.return_value = None
        file_handle = StringIO()

        # errata are saved with the "additive=True" flag
        self.reposync.save_fileless_units(file_handle, updateinfo.PACKAGE_TAG,
                                          updateinfo.process_package_element, additive_type=True)

        mock_generator.assert_any_call(file_handle, updateinfo.PACKAGE_TAG,
                                       updateinfo.process_package_element)
        self.assertEqual(mock_generator.call_count, 1)

        for model in errata:
            self.conduit.init_unit.assert_any_call(model.TYPE, model.unit_key, model.metadata, None)
        self.conduit.save_unit.assert_any_call(self.conduit.init_unit.return_value)
        self.assertEqual(self.conduit.save_unit.call_count, 3)

    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.packages.'
                'package_list_generator', autospec=True)
    @mock.patch('pulp.plugins.conduits.mixins.SearchUnitsMixin.'
                'find_unit_by_unit_key', autospec=True)
    @mock.patch('pulp_rpm.plugins.importers.yum.sync.RepoSync._concatenate_units', autospec=True)
    def test_save_erratas_some_existing(self, mock_concat, mock_find_unit, mock_generator):
        """
        test where some errata already exist. When "additive_type" is set, we
        will always init and save a unit since it may have been modified.
        """
        errata = tuple(model_factory.errata_models(3))
        mock_generator.return_value = errata
        self.conduit.init_unit = mock.MagicMock(spec_set=self.conduit.init_unit)
        self.conduit.save_unit = mock.MagicMock(spec_set=self.conduit.save_unit)
        # all of these units are new, find_unit_by_unit_key will return None
        mock_find_unit.return_value = None
        file_handle = StringIO()

        find_unit_retvals = [mock.Mock(), None, mock.Mock()]

        def _find_unit_return(*args):
            return find_unit_retvals.pop()

        mock_find_unit.side_effect = _find_unit_return

        concat_unit_retvals = ["fake-unit-b", "fake-unit-a"]

        def _concat_unit_return(*args):
            return concat_unit_retvals.pop()

        mock_concat.side_effect = _concat_unit_return

        # errata are saved with the "additive=True" flag
        self.reposync.save_fileless_units(file_handle, updateinfo.PACKAGE_TAG,
                                          updateinfo.process_package_element, additive_type=True)

        mock_generator.assert_any_call(file_handle, updateinfo.PACKAGE_TAG,
                                       updateinfo.process_package_element)
        # the generator is called only once since we are not rewinding the file
        # handle or checking the repo for existing elements.
        self.assertEqual(mock_generator.call_count, 1)

        for model in errata:
            self.conduit.init_unit.assert_any_call(model.TYPE, model.unit_key, model.metadata, None)

        self.conduit.save_unit.assert_any_call("fake-unit-a")
        self.conduit.save_unit.assert_any_call("fake-unit-b")
        self.conduit.save_unit.assert_any_call(self.conduit.init_unit.return_value)
        self.assertEqual(self.conduit.save_unit.call_count, 3)

    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.packages.'
                'package_list_generator', autospec=True)
    @mock.patch('pulp_rpm.plugins.importers.yum.sync.RepoSync._concatenate_units', autospec=True)
    @mock.patch('pulp.plugins.conduits.mixins.SearchUnitsMixin.'
                'find_unit_by_unit_key', autospec=True)
    def test_save_erratas_update_pkglist(self, mock_find_unit, mock_concat, mock_generator):
        """
        test that we call _concatenate_units when we find an existing errata
        """
        errata = tuple(model_factory.errata_models(3))
        mock_generator.return_value = errata
        self.conduit.init_unit = mock.MagicMock(spec_set=self.conduit.init_unit)
        self.conduit.save_unit = mock.MagicMock(spec_set=self.conduit.save_unit)
        mock_find_unit.return_value = "fake unit"
        file_handle = StringIO()

        self.reposync.save_fileless_units(file_handle, updateinfo.PACKAGE_TAG,
                                          updateinfo.process_package_element, additive_type=True)

        self.assertEqual(mock_concat.call_count, 3)

    @mock.patch('pulp_rpm.plugins.importers.yum.existing.check_repo', autospec=True)
    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.packages.package_list_generator',
                autospec=True)
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
    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.packages.'
                'package_list_generator', autospec=True)
    @mock.patch('pulp.plugins.conduits.mixins.SearchUnitsMixin.'
                'find_unit_by_unit_key', autospec=True)
    @mock.patch('pulp_rpm.plugins.importers.yum.sync.RepoSync._concatenate_units', autospec=True)
    def test_save_erratas_all_existing(self, mock_concat, mock_find_unit, mock_generator,
                                       mock_check_repo):
        """
        test where all errata already exist
        """
        errata = tuple(model_factory.errata_models(3))
        mock_generator.return_value = errata
        mock_check_repo.return_value = []
        self.conduit.init_unit = mock.MagicMock(spec_set=self.conduit.init_unit)
        self.conduit.save_unit = mock.MagicMock(spec_set=self.conduit.save_unit)
        file_handle = StringIO()

        self.reposync.save_fileless_units(file_handle, updateinfo.PACKAGE_TAG,
                                          updateinfo.process_package_element, additive_type=True)

        mock_generator.assert_any_call(file_handle, updateinfo.PACKAGE_TAG,
                                       updateinfo.process_package_element)
        self.assertEqual(mock_generator.call_count, 1)

        self.assertEqual(self.conduit.save_unit.call_count, 3)

    def test_concatenate_units_wrong_type_id(self):
        """
        Ensure that we get an exception if we try to concatenate units of different types!
        """
        mock_erratum_model = models.Errata('RHBA-1234', metadata={})
        mock_existing_unit = Unit(ids.TYPE_ID_ERRATA, mock_erratum_model.unit_key,
                                  mock_erratum_model.metadata, "/fake/path")

        mock_dist_model = models.Distribution('fake family', 'server', '3.11',
                                              'baroque', metadata={})
        mock_new_unit = Unit(ids.TYPE_ID_DISTRO, mock_dist_model.unit_key,
                             mock_dist_model.metadata, "/fake/path")

        self.assertRaises(PulpCodedException, self.reposync._concatenate_units,
                          mock_existing_unit, mock_new_unit)

    def test_concatenate_units_wrong_unit_keys(self):
        """
        Ensure that we get an exception if we try to concatenate units with different unit_keys.
        """
        mock_existing_erratum_model = models.Errata('RHBA-1234', metadata={})
        mock_existing_unit = Unit(ids.TYPE_ID_ERRATA, mock_existing_erratum_model.unit_key,
                                  mock_existing_erratum_model.metadata, "/fake/path")

        mock_new_erratum_model = models.Errata('RHBA-5678', metadata={})
        mock_new_unit = Unit(ids.TYPE_ID_ERRATA, mock_new_erratum_model.unit_key,
                             mock_new_erratum_model.metadata, "/fake/path")

        self.assertRaises(PulpCodedException, self.reposync._concatenate_units,
                          mock_existing_unit, mock_new_unit)

    def test_concatenate_units_unsupported_type(self):
        """
        Ensure that we get an exception if we try to concatenate unsupported units
        """
        mock_existing_dist_model = models.Distribution('fake family', 'server', '3.11',
                                                       'baroque', metadata={})
        mock_existing_dist_unit = Unit(ids.TYPE_ID_DISTRO, mock_existing_dist_model.unit_key,
                                       mock_existing_dist_model.metadata, "/fake/path")
        mock_new_dist_model = models.Distribution('fake family', 'server', '3.11',
                                                  'baroque', metadata={})
        mock_new_dist_unit = Unit(ids.TYPE_ID_DISTRO, mock_new_dist_model.unit_key,
                                  mock_new_dist_model.metadata, "/fake/path")

        self.assertRaises(PulpCodedException, self.reposync._concatenate_units,
                          mock_existing_dist_unit, mock_new_dist_unit)

    def test_concatenate_units_errata(self):
        """
        Ensure that concatenation works
        """
        mock_existing_erratum_pkglist = [{'packages': [{"name": "some_package v1"},
                                                       {"name": "another_package v1"}],
                                          'name': 'v1 packages'}]
        mock_existing_erratum_model = models.Errata(
            'RHBA-1234', metadata={'pkglist': mock_existing_erratum_pkglist})
        mock_existing_unit = Unit(ids.TYPE_ID_ERRATA, mock_existing_erratum_model.unit_key,
                                  mock_existing_erratum_model.metadata, "/fake/path")

        mock_new_erratum_pkglist = [{'packages': [{"name": "some_package v2"},
                                                  {"name": "another_package v2"}],
                                     'name': 'v2 packages'}]
        mock_new_erratum_model = models.Errata('RHBA-1234',
                                               metadata={'pkglist': mock_new_erratum_pkglist})
        mock_new_unit = Unit(ids.TYPE_ID_ERRATA, mock_new_erratum_model.unit_key,
                             mock_new_erratum_model.metadata, "/fake/path")

        concat_unit = self.reposync._concatenate_units(mock_existing_unit, mock_new_unit)

        self.assertEquals(concat_unit.metadata, {'pkglist':
                                                 [{'packages': [{'name': 'some_package v1'},
                                                                {'name': 'another_package v1'}],
                                                   'name': 'v1 packages'},
                                                  {'packages': [{'name': 'some_package v2'},
                                                                {'name': 'another_package v2'}],
                                                   'name': 'v2 packages'}],
                                                 'pulp_user_metadata': {}})

    def test_concatenate_units_errata_same_errata(self):
        """
        Ensure that we do not alter existing package lists when there is no new info
        """
        mock_existing_erratum_pkglist = [{'packages': [{"name": "some_package v1"},
                                                       {"name": "another_package v1"}],
                                          'name': 'v1 packages'}]
        mock_existing_erratum_model = models.Errata('RHBA-1234',
                                                    metadata={'pkglist':
                                                              mock_existing_erratum_pkglist})
        mock_existing_unit = Unit(ids.TYPE_ID_ERRATA, mock_existing_erratum_model.unit_key,
                                  mock_existing_erratum_model.metadata, "/fake/path")

        # new erratum has the same package list and same ID
        mock_new_erratum_pkglist = [{'packages': [{"name": "some_package v1"},
                                                  {"name": "another_package v1"}],
                                     'name': 'v1 packages'}]

        mock_new_erratum_model = models.Errata('RHBA-1234', metadata={'pkglist':
                                                                      mock_new_erratum_pkglist})
        mock_new_unit = Unit(ids.TYPE_ID_ERRATA, mock_new_erratum_model.unit_key,
                             mock_new_erratum_model.metadata, "/fake/path")

        concat_unit = self.reposync._concatenate_units(mock_existing_unit, mock_new_unit)

        self.assertEquals(concat_unit.metadata,
                          {'pkglist': [{'packages': [{'name': 'some_package v1'},
                                                     {'name': 'another_package v1'}],
                                        'name': 'v1 packages'}],
                           'pulp_user_metadata': {}})

    def test_concatenate_units_errata_avoid_double_concat(self):
        """
        Ensure that we do not append a package list to an errata a second time
        """
        mock_existing_erratum_pkglist = [{'packages': [{'name': 'some_package v1'},
                                                       {'name': 'another_package v1'}],
                                          'name': 'v1 packages'},
                                         {'packages': [{'name': 'some_package v2'},
                                                       {'name': 'another_package v2'}],
                                          'name': 'v2 packages'}]

        mock_existing_erratum_model = models.Errata('RHBA-1234',
                                                    metadata={'pkglist':
                                                              mock_existing_erratum_pkglist})
        mock_existing_unit = Unit(ids.TYPE_ID_ERRATA, mock_existing_erratum_model.unit_key,
                                  mock_existing_erratum_model.metadata, "/fake/path")

        # new erratum has a subset of what we already know
        mock_new_erratum_pkglist = [{'packages': [{"name": "some_package v1"},
                                                  {"name": "another_package v1"}],
                                     'name': 'v1 packages'}]

        mock_new_erratum_model = models.Errata('RHBA-1234',
                                               metadata={'pkglist': mock_new_erratum_pkglist})
        mock_new_unit = Unit(ids.TYPE_ID_ERRATA, mock_new_erratum_model.unit_key,
                             mock_new_erratum_model.metadata, "/fake/path")

        concat_unit = self.reposync._concatenate_units(mock_existing_unit, mock_new_unit)

        self.assertEquals(concat_unit.metadata,
                          {'pkglist': [{'packages': [{'name': 'some_package v1'},
                                                     {'name': 'another_package v1'}],
                                        'name': 'v1 packages'},
                                       {'packages': [{'name': 'some_package v2'},
                                                     {'name': 'another_package v2'}],
                                        'name': 'v2 packages'}],
                           'pulp_user_metadata': {}})


@skip_broken
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


@skip_broken
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


@skip_broken
class TestAlreadyDownloadedUnits(BaseSyncTest):
    @mock.patch('pulp.plugins.conduits.repo_sync.RepoSyncConduit.search_all_units', autospec=True)
    @mock.patch('pulp.plugins.conduits.repo_sync.RepoSyncConduit.save_unit', autospec=True)
    @mock.patch('os.path.isfile', autospec=True)
    def test_rpms_check_all_and_associate_positive(self, mock_isfile, mock_save,
                                                   mock_search_all_units):
        units = model_factory.rpm_models(3)
        mock_search_all_units.return_value = units
        mock_isfile.return_value = True
        input_units = set([unit.as_named_tuple for unit in units])
        for unit in units:
            unit.metadata['filename'] = 'test-filename'
            unit.storage_path = "existing_storage_path"
        result = check_all_and_associate(input_units, self.conduit)
        self.assertEqual(len(list(result)), 0)
        # verify we are saving the storage path
        for c in mock_save.mock_calls:
            (conduit, unit) = c[1]
            self.assertEquals(unit.storage_path, "existing_storage_path")

    @mock.patch('pulp.plugins.conduits.repo_sync.RepoSyncConduit.search_all_units', autospec=True)
    @mock.patch('pulp.plugins.conduits.repo_sync.RepoSyncConduit.save_unit', autospec=True)
    @mock.patch('os.path.isfile', autospec=True)
    def test_rpms_check_all_and_associate_negative(self, mock_isfile, mock_save,
                                                   mock_search_all_units):
        mock_search_all_units.return_value = []
        mock_isfile.return_value = True
        units = model_factory.rpm_models(3)
        input_units = set([unit.as_named_tuple for unit in units])
        result = check_all_and_associate(input_units, self.conduit)
        self.assertEqual(len(list(result)), 3)

    @mock.patch('pulp.plugins.conduits.repo_sync.RepoSyncConduit.search_all_units', autospec=True)
    @mock.patch('pulp.plugins.conduits.repo_sync.RepoSyncConduit.save_unit', autospec=True)
    @mock.patch('os.path.isfile', autospec=True)
    def test_srpms_check_all_and_associate_positive(self, mock_isfile, mock_save,
                                                    mock_search_all_units):
        units = model_factory.srpm_models(3)
        mock_search_all_units.return_value = units
        mock_isfile.return_value = True
        input_units = set([unit.as_named_tuple for unit in units])
        for unit in units:
            unit.metadata['filename'] = 'test-filename'
            unit.storage_path = "existing_storage_path"
        result = check_all_and_associate(input_units, self.conduit)
        self.assertEqual(len(list(result)), 0)

    @mock.patch('pulp.plugins.conduits.repo_sync.RepoSyncConduit.search_all_units', autospec=True)
    @mock.patch('pulp.plugins.conduits.repo_sync.RepoSyncConduit.save_unit', autospec=True)
    @mock.patch('os.path.isfile', autospec=True)
    def test_srpms_check_all_and_associate_negative(self, mock_isfile, mock_save,
                                                    mock_search_all_units):
        mock_search_all_units.return_value = []
        mock_isfile.return_value = True
        units = model_factory.srpm_models(3)
        input_units = set([unit.as_named_tuple for unit in units])
        result = check_all_and_associate(input_units, self.conduit)
        self.assertEqual(len(list(result)), 3)

    @mock.patch('pulp.plugins.conduits.repo_sync.RepoSyncConduit.search_all_units', autospec=True)
    @mock.patch('pulp.plugins.conduits.repo_sync.RepoSyncConduit.save_unit', autospec=True)
    @mock.patch('os.path.isfile', autospec=True)
    def test_drpms_check_all_and_associate_positive(self, mock_isfile, mock_save,
                                                    mock_search_all_units):
        units = model_factory.drpm_models(3)
        mock_search_all_units.return_value = units
        mock_isfile.return_value = True
        input_units = set([unit.as_named_tuple for unit in units])
        for unit in units:
            unit.metadata['filename'] = 'test-filename'
            unit.storage_path = "existing_storage_path"
        result = check_all_and_associate(input_units, self.conduit)
        self.assertEqual(len(list(result)), 0)

    @mock.patch('pulp.plugins.conduits.repo_sync.RepoSyncConduit.search_all_units', autospec=True)
    @mock.patch('pulp.plugins.conduits.repo_sync.RepoSyncConduit.save_unit', autospec=True)
    @mock.patch('os.path.isfile', autospec=True)
    def test_drpms_check_all_and_associate_negative(self, mock_isfile, mock_save,
                                                    mock_search_all_units):
        mock_search_all_units.return_value = []
        mock_isfile.return_value = True
        units = model_factory.drpm_models(3)
        input_units = set([unit.as_named_tuple for unit in units])
        result = check_all_and_associate(input_units, self.conduit)
        self.assertEqual(len(list(result)), 3)


@skip_broken
class TestTreeinfoAlterations(BaseSyncTest):
    TREEINFO_NO_REPOMD = """
[general]
name = Some-treeinfo
family = mockdata

[stage2]
mainimage = LiveOS/squashfs.img

[images-x86_64]
kernel = images/pxeboot/vmlinuz
initrd = images/pxeboot/initrd.img

[checksums]
images/efiboot.img = sha256:12345
"""
    TREEINFO_WITH_REPOMD = """
[general]
name = Some-treeinfo
family = mockdata

[stage2]
mainimage = LiveOS/squashfs.img

[images-x86_64]
kernel = images/pxeboot/vmlinuz
initrd = images/pxeboot/initrd.img

[checksums]
images/efiboot.img = sha256:12345
repodata/repomd.xml = sha256:9876
"""

    @mock.patch('__builtin__.open', autospec=True)
    def test_treeinfo_unaltered(self, mock_open):
        mock_file = mock.MagicMock(spec=file)
        mock_file.readlines.return_value = StringIO(self.TREEINFO_NO_REPOMD).readlines()
        mock_context = mock.MagicMock()
        mock_context.__enter__.return_value = mock_file
        mock_open.return_value = mock_context
        treeinfo.strip_treeinfo_repomd("/mock/treeinfo/path")

        mock_file.writelines.assert_called_once_with(['\n', '[general]\n', 'name = Some-treeinfo\n',
                                                      'family = mockdata\n', '\n', '[stage2]\n',
                                                      'mainimage = LiveOS/squashfs.img\n', '\n',
                                                      '[images-x86_64]\n',
                                                      'kernel = images/pxeboot/vmlinuz\n',
                                                      'initrd = images/pxeboot/initrd.img\n',
                                                      '\n', '[checksums]\n',
                                                      'images/efiboot.img = sha256:12345\n'])

    @mock.patch('__builtin__.open', autospec=True)
    def test_treeinfo_altered(self, mock_open):
        mock_file = mock.MagicMock(spec=file)
        mock_file.readlines.return_value = StringIO(self.TREEINFO_WITH_REPOMD).readlines()
        mock_context = mock.MagicMock()
        mock_context.__enter__.return_value = mock_file
        mock_open.return_value = mock_context
        treeinfo.strip_treeinfo_repomd("/mock/treeinfo/path")

        mock_file.writelines.assert_called_once_with(['\n', '[general]\n', 'name = Some-treeinfo\n',
                                                      'family = mockdata\n', '\n', '[stage2]\n',
                                                      'mainimage = LiveOS/squashfs.img\n', '\n',
                                                      '[images-x86_64]\n',
                                                      'kernel = images/pxeboot/vmlinuz\n',
                                                      'initrd = images/pxeboot/initrd.img\n',
                                                      '\n', '[checksums]\n',
                                                      'images/efiboot.img = sha256:12345\n'])


# these tests are specifically to test bz #1150714
@skip_broken
@mock.patch('os.chmod', autospec=True)
@mock.patch('pulp_rpm.plugins.importers.yum.parse.treeinfo.pulp_copytree', autospec=True)
@mock.patch('pulp_rpm.plugins.importers.yum.parse.treeinfo.get_treefile', autospec=True)
@mock.patch('pulp_rpm.plugins.importers.yum.parse.treeinfo.parse_treefile', autospec=True)
@mock.patch('pulp_rpm.plugins.importers.yum.report.DistributionReport', autospec=True)
@mock.patch('shutil.rmtree', autospec=True)
@mock.patch('tempfile.mkdtemp', autospec=True)
@mock.patch('pulp_rpm.plugins.importers.yum.repomd.nectar_factory.create_downloader', autospec=True)
class TestTreeinfoSync(BaseSyncTest):
    def setUp(self, *mocks):
        super(TestTreeinfoSync, self).setUp()
        self.conduit.remove_unit = mock.MagicMock(spec_set=self.conduit.remove_unit)
        self.conduit.init_unit = mock.MagicMock(spec_set=self.conduit.init_unit)
        self.conduit.save_unit = mock.MagicMock(spec_set=self.conduit.save_unit)

    # This is the case when we are syncing for the first time, or a treeinfo
    # appeared for the first time
    def test_treeinfo_sync_no_unit_removal(self, mock_nectar, mock_tempfile, mock_rmtree,
                                           mock_report, mock_parse_treefile, mock_get_treefile,
                                           mock_move, mock_chmod):
        mock_model = models.Distribution('fake family', 'server', '3.11', 'baroque', metadata={})
        mock_parse_treefile.return_value = (mock_model, ["fake file 1"])
        mock_get_treefile.return_value = "/a/fake/path/to/the/treefile"
        treeinfo.sync(self.conduit, "http://some/url", "/some/tempdir", "fake-nectar-conf",
                      mock_report, lambda x: x)
        self.assertEqual(self.conduit.remove_unit.call_count, 0)

    # The "usual" case of one existing distribution unit on the repo. Ensure
    # that we didn't try to remove anything.
    def test_treeinfo_sync_one_unit_removal(self, mock_nectar, mock_tempfile, mock_rmtree,
                                            mock_report, mock_parse_treefile, mock_get_treefile,
                                            mock_move, mock_chmod):
        # return one unit that is the same as what we saved. No removal should occur
        mock_model = models.Distribution('fake family', 'server', '3.11', 'baroque', metadata={})
        mock_unit = Unit(ids.TYPE_ID_DISTRO, mock_model.unit_key, mock_model.metadata, "/fake/path")
        self.conduit.get_units = mock.MagicMock(spec_set=self.conduit.get_units)
        self.conduit.get_units.return_value = [mock_unit]
        self.conduit.init_unit = mock.MagicMock(spec_set=self.conduit.init_unit)
        self.conduit.init_unit.return_value = mock_unit
        mock_parse_treefile.return_value = (mock_model, ["fake file 1"])
        mock_get_treefile.return_value = "/a/fake/path/to/the/treefile"
        treeinfo.sync(self.conduit, "http://some/url", "/some/tempdir", "fake-nectar-conf",
                      mock_report, lambda x: x)
        self.assertEqual(self.conduit.remove_unit.call_count, 0)

    # The "usual" case of one existing distribution unit on the repo. Ensure
    # that we didn't try to remove anything.
    def test_treeinfo_sync_unchanged(self, mock_nectar, mock_tempfile, mock_rmtree,
                                     mock_report, mock_parse_treefile, mock_get_treefile,
                                     mock_move, mock_chmod):
        # return one unit that is the same as what we saved. No removal should occur
        metadata = {treeinfo.KEY_TIMESTAMP: 1354213090.94}
        mock_model = models.Distribution('fake family', 'server', '3.11', 'baroque',
                                         metadata=metadata.copy())
        mock_unit = Unit(ids.TYPE_ID_DISTRO, mock_model.unit_key, metadata.copy(),
                         "/fake/path")
        self.conduit.get_units = mock.MagicMock(spec_set=self.conduit.get_units)
        self.conduit.get_units.return_value = [mock_unit]
        self.conduit.init_unit = mock.MagicMock(spec_set=self.conduit.init_unit)
        self.conduit.init_unit.return_value = mock_unit
        mock_parse_treefile.return_value = (mock_model, ["fake file 1"])
        mock_get_treefile.return_value = "/a/fake/path/to/the/treefile"
        treeinfo.sync(self.conduit, "http://some/url", "/some/tempdir", "fake-nectar-conf",
                      mock_report, lambda x: x)
        self.assertEqual(self.conduit.remove_unit.call_count, 0)
        # make sure the workflow did not proceed by making sure this call didn't happen
        self.assertEqual(mock_report.set_initial_values.call_count, 0)

    # This is the case that occurs when symlinks like "6Server" are updated for
    # a new release. Pulp will have created a new distribution unit and we need
    # to remove any old units
    def test_treeinfo_sync_two_unit_removal(self, mock_nectar, mock_tempfile, mock_rmtree,
                                            mock_report, mock_parse_treefile, mock_get_treefile,
                                            mock_move, mock_chmod):
        # return one unit that is the same as what we saved. No removal should occur
        mock_model = models.Distribution('fake family', 'server', '3.11', 'baroque', metadata={})
        mock_model_old = models.Distribution('fake family', 'server', '3.10', 'baroque',
                                             metadata={})
        mock_unit = Unit(ids.TYPE_ID_DISTRO, mock_model.unit_key, mock_model.metadata, "/fake/path")
        mock_unit_old = Unit(ids.TYPE_ID_DISTRO, mock_model_old.unit_key, mock_model_old.metadata,
                             "/fake/path")
        self.conduit.get_units = mock.MagicMock(spec_set=self.conduit.get_units)
        self.conduit.get_units.return_value = [mock_unit, mock_unit_old]
        self.conduit.init_unit = mock.MagicMock(spec_set=self.conduit.init_unit)
        self.conduit.init_unit.return_value = mock_unit
        mock_parse_treefile.return_value = (mock_model, ["fake file 1"])
        mock_get_treefile.return_value = "/a/fake/path/to/the/treefile"
        treeinfo.sync(self.conduit, "http://some/url", "/some/tempdir", "fake-nectar-conf",
                      mock_report, lambda x: x)
        self.conduit.remove_unit.assert_called_once_with(mock_unit_old)
