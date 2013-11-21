# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the License
# (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied, including the
# implied warranties of MERCHANTABILITY, NON-INFRINGEMENT, or FITNESS FOR A
# PARTICULAR PURPOSE.
# You should have received a copy of GPLv2 along with this software;
# if not, see http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt

import os
import shutil
import unittest

import mock

from pulp.plugins.conduits.repo_publish import RepoPublishConduit
from pulp.plugins.config import PluginCallConfiguration
from pulp.plugins.model import Repository, Unit
from pulp.server.exceptions import InvalidValue

from pulp_rpm.common.ids import (
    TYPE_ID_PKG_GROUP, TYPE_ID_PKG_CATEGORY, TYPE_ID_DISTRO, TYPE_ID_DRPM, TYPE_ID_RPM,
    TYPE_ID_YUM_REPO_METADATA_FILE, YUM_DISTRIBUTOR_ID)
from pulp_rpm.plugins.distributors.yum import publish, reporting


DATA_DIR = os.path.join(os.path.dirname(__file__), '../data/')


class YumDistributorPublishTests(unittest.TestCase):

    def setUp(self):
        super(YumDistributorPublishTests, self).setUp()

        self.published_dir = '/tmp/published_dir/'
        self.working_dir = '/tmp/working_dir/'

        self.publisher = None

    def tearDown(self):
        super(YumDistributorPublishTests, self).tearDown()

        if os.path.exists(self.published_dir):
            shutil.rmtree(self.published_dir)

        if os.path.exists(self.working_dir):
            shutil.rmtree(self.working_dir)

        self.publisher = None

    def _init_publisher(self):

        repo = Repository('yum-distributor-publish-tests', working_dir=self.working_dir)

        conduit = RepoPublishConduit(repo.id, YUM_DISTRIBUTOR_ID)
        conduit.get_repo_scratchpad = mock.Mock(return_value={})

        config_defaults = {'http': True,
                           'https': True,
                           'relative_url': None,
                           'http_publish_dir': self.published_dir + 'http/',
                           'https_publish_dir': self.published_dir + 'https/'}
        config = PluginCallConfiguration(None, None)
        config.default_config.update(config_defaults)

        self.publisher = publish.Publisher(repo, conduit, config)

        # mock out the repomd_file_context, so _publish_<step> can be called 
        # outside of the publish() method
        self.publisher.repomd_file_context = mock.MagicMock()

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

    def _generate_metadata_file_unit(self, data_type, repo_id):

        unit_key = {'data_type' : data_type,
                    'repo_id' : repo_id}

        unit_metadata = {}

        storage_path = os.path.join(self.working_dir, 'content', 'metadata_files', data_type)
        self._touch(storage_path)

        return Unit(TYPE_ID_YUM_REPO_METADATA_FILE, unit_key, unit_metadata, storage_path)

    @staticmethod
    def _touch(path):

        parent = os.path.dirname(path)

        if not os.path.exists(parent):
            os.makedirs(parent)

        with open(path, 'w'):
            pass

    # -- cleanup testing -------------------------------------------------------

    def test_clear_directory(self):

        for file_name in ('one', 'two', 'three'):
            self._touch(os.path.join(self.working_dir, file_name))

        self.assertEqual(len(os.listdir(self.working_dir)), 3)

        publish.Publisher._clear_directory(self.working_dir)

        self.assertEqual(len(os.listdir(self.working_dir)), 0)

    # -- linking testing -------------------------------------------------------

    def test_create_symlink(self):
        source_path = os.path.join(self.working_dir, 'source')
        link_path = os.path.join(self.published_dir, 'link')

        self._touch(source_path)
        self.assertFalse(os.path.exists(link_path))

        publish.Publisher._create_symlink(source_path, link_path)

        self.assertTrue(os.path.exists(link_path))
        self.assertTrue(os.path.islink(link_path))
        self.assertEqual(os.readlink(link_path), source_path)

    def test_create_symlink_no_source(self):
        source_path = os.path.join(self.working_dir, 'source')
        link_path = os.path.join(self.published_dir, 'link')

        self.assertRaises(RuntimeError, publish.Publisher._create_symlink, source_path, link_path)

    def test_create_symlink_no_link_parent(self):
        source_path = os.path.join(self.working_dir, 'source')
        link_path = os.path.join(self.published_dir, 'foo/bar/baz/link')

        self._touch(source_path)
        self.assertFalse(os.path.exists(os.path.dirname(link_path)))

        publish.Publisher._create_symlink(source_path, link_path)

        self.assertTrue(os.path.exists(link_path))

    def test_create_symlink_link_parent_bad_permissions(self):
        source_path = os.path.join(self.working_dir, 'source')
        link_path = os.path.join(self.published_dir, 'foo/bar/baz/link')

        self._touch(source_path)
        os.makedirs(os.path.dirname(link_path))
        os.chmod(os.path.dirname(link_path), 0000)

        self.assertRaises(RuntimeError, publish.Publisher._create_symlink, source_path, link_path)

        os.chmod(os.path.dirname(link_path), 0777)

    def test_create_symlink_link_exists(self):
        old_source_path = os.path.join(self.working_dir, 'old_source')
        new_source_path = os.path.join(self.working_dir, 'new_source')
        link_path = os.path.join(self.published_dir, 'link')

        self._touch(old_source_path)
        self._touch(new_source_path)

        os.makedirs(self.published_dir)
        os.symlink(old_source_path, link_path)

        self.assertEqual(os.readlink(link_path), old_source_path)

        publish.Publisher._create_symlink(new_source_path, link_path)

        self.assertEqual(os.readlink(link_path), new_source_path)

    def test_create_symlink_link_exists_not_link(self):
        source_path = os.path.join(self.working_dir, 'source')
        link_path = os.path.join(self.published_dir, 'link')

        self._touch(source_path)
        self._touch(link_path)

        self.assertRaises(RuntimeError, publish.Publisher._create_symlink, source_path, link_path)

    def test_symlink_content(self):
        self._init_publisher()
        unit_name = 'test.rpm'
        unit = self._generate_rpm(unit_name)

        self.publisher._symlink_content(unit, self.published_dir)

        self.assertTrue(os.path.exists(os.path.join(self.published_dir, unit_name)),
                        str(os.listdir(self.published_dir)))
        self.assertTrue(os.path.islink(os.path.join(self.published_dir, unit_name)))

    # -- progress testing ------------------------------------------------------

    def test_init_step_progress(self):
        self._init_publisher()

        step = reporting.PUBLISH_STEPS[0]

        self.publisher._init_step_progress_report(step)

        self.assertEqual(self.publisher.progress_report[step], reporting.PROGRESS_SUB_REPORT)

    def test_init_step_progress_not_a_step(self):
        self._init_publisher()

        step = 'not_a_step'

        self.assertRaises(AssertionError, self.publisher._init_step_progress_report, step)

    @mock.patch('pulp.plugins.conduits.repo_publish.RepoPublishConduit.set_progress')
    def test_report_progress(self, mock_set_progress):
        self._init_publisher()

        step = reporting.PUBLISH_STEPS[1]

        updates = {reporting.STATE: reporting.PUBLISH_FINISHED_STATE,
                   reporting.TOTAL: 1,
                   reporting.PROCESSED: 1,
                   reporting.SUCCESSES: 1}

        self.publisher._report_progress(step, **updates)

        self.assertEqual(self.publisher.progress_report[step], updates)

        mock_set_progress.assert_called_once_with(self.publisher.progress_report)

    def test_record_failure(self):
        self._init_publisher()
        step = reporting.PUBLISH_STEPS[2]
        self.publisher._init_step_progress_report(step)

        error_msg = 'Too bad, so sad'

        try:
            raise Exception(error_msg)

        except Exception, e:
            self.publisher._record_failure(step, e)

        self.assertEqual(self.publisher.progress_report[step][reporting.FAILURES], 1)
        self.assertEqual(self.publisher.progress_report[step][reporting.ERROR_DETAILS][0], error_msg)

    def test_build_final_report_success(self):
        self._init_publisher()

        for step in reporting.PUBLISH_STEPS:
            self.publisher._init_step_progress_report(step)
            self.publisher.progress_report[step][reporting.STATE] = reporting.PUBLISH_FINISHED_STATE

        report = self.publisher._build_final_report()

        self.assertTrue(report.success_flag)

    def test_build_final_report_failure(self):
        self._init_publisher()

        for step in reporting.PUBLISH_STEPS:
            self.publisher._init_step_progress_report(step)
            self.publisher.progress_report[step][reporting.STATE] = reporting.PUBLISH_FAILED_STATE
            self.publisher.progress_report[step][reporting.ERROR_DETAILS].append('boo hoo')

        report = self.publisher._build_final_report()

        self.assertFalse(report.success_flag)

    # -- http/https publishing testing -----------------------------------------

    def test_publish_http(self):
        self._init_publisher()

        units = [self._generate_rpm(u) for u in ('one', 'two', 'three')]

        self.publisher._init_step_progress_report(reporting.PUBLISH_OVER_HTTP_STEP)
        self.publisher._publish_over_http()

        for u in units:
            path = os.path.join(self.published_dir, 'http', self.publisher.repo.id, 'content', u.unit_key['name'])
            self.assertTrue(os.path.exists(path))

        listing_path = os.path.join(self.published_dir, 'http', 'listing')
        self.assertTrue(os.path.exists(listing_path))

        listing_content = open(listing_path, 'r').read()
        self.assertEqual(listing_content, self.publisher.repo.id)

        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_OVER_HTTP_STEP][reporting.PROCESSED], 1)
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_OVER_HTTP_STEP][reporting.FAILURES], 0)
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_OVER_HTTP_STEP][reporting.SUCCESSES], 1)
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_OVER_HTTP_STEP][reporting.STATE], reporting.PUBLISH_FINISHED_STATE)

    def test_publish_http_skipped(self):
        self._init_publisher()

        self.publisher.config.default_config['http'] = False

        self.publisher._publish_over_http()

        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_OVER_HTTP_STEP][reporting.STATE], reporting.PUBLISH_SKIPPED_STATE)

    def test_publish_https(self):
        self._init_publisher()

        units = [self._generate_rpm(u) for u in ('one', 'two', 'three')]

        self.publisher._init_step_progress_report(reporting.PUBLISH_OVER_HTTPS_STEP)
        self.publisher._publish_over_https()

        for u in units:
            path = os.path.join(self.published_dir, 'https', self.publisher.repo.id, 'content', u.unit_key['name'])
            self.assertTrue(os.path.exists(path))

        listing_path= os.path.join(self.published_dir, 'https', 'listing')
        self.assertTrue(os.path.exists(listing_path))

        listing_content = open(listing_path, 'r').read()
        self.assertEqual(listing_content, self.publisher.repo.id)

        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_OVER_HTTPS_STEP][reporting.PROCESSED], 1)
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_OVER_HTTPS_STEP][reporting.FAILURES], 0)
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_OVER_HTTPS_STEP][reporting.SUCCESSES], 1)
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_OVER_HTTPS_STEP][reporting.STATE], reporting.PUBLISH_FINISHED_STATE)

    def test_publish_https_skipped(self):
        self._init_publisher()

        self.publisher.config.default_config['https'] = False

        self.publisher._publish_over_https()

        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_OVER_HTTPS_STEP][reporting.STATE], reporting.PUBLISH_SKIPPED_STATE)

    # -- rpm publishing testing ------------------------------------------------

    @mock.patch('pulp.plugins.conduits.repo_publish.RepoPublishConduit.get_units')
    def test_publish_rpms(self, mock_get_units):
        self._init_publisher()
        self.publisher.repo.content_unit_counts = {TYPE_ID_RPM: 3}

        units = [self._generate_rpm(u) for u in ('one', 'two', 'tree')]
        mock_get_units.return_value = units

        self.publisher._publish_rpms()

        for u in units:
            path = os.path.join(self.working_dir, u.unit_key['name'])
            self.assertTrue(os.path.exists(path))
            self.assertTrue(os.path.islink(path))

        self.assertTrue(os.path.exists(os.path.join(self.working_dir, 'repodata/filelists.xml.gz')))
        self.assertTrue(os.path.exists(os.path.join(self.working_dir, 'repodata/other.xml.gz')))
        self.assertTrue(os.path.exists(os.path.join(self.working_dir, 'repodata/primary.xml.gz')))

        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_RPMS_STEP][reporting.STATE], reporting.PUBLISH_FINISHED_STATE)
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_RPMS_STEP][reporting.TOTAL], 3)
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_RPMS_STEP][reporting.PROCESSED], 3)
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_RPMS_STEP][reporting.FAILURES], 0)
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_RPMS_STEP][reporting.SUCCESSES], 3)

    def test_publish_rpms_skipped(self):
        self._init_publisher()

        self.publisher.config.default_config['skip'] = {TYPE_ID_RPM: 1}

        self.publisher._publish_rpms()

        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_RPMS_STEP][reporting.STATE], reporting.PUBLISH_SKIPPED_STATE)

    # -- publish api testing ---------------------------------------------------

    def test_skip_list_with_list(self):
        self._init_publisher()
        mock_config = mock.Mock()
        mock_config.get.return_value = ['foo', 'bar']
        self.publisher.config = mock_config
        skip_list = self.publisher.skip_list
        self.assertEquals(2, len(skip_list))
        self.assertEquals(skip_list[0], 'foo')
        self.assertEquals(skip_list[1], 'bar')

    def test_skip_list_with_dict(self):
        self._init_publisher()
        mock_config = mock.Mock()
        mock_config.get.return_value = {'rpm': True, 'distro': False, 'errata': True}
        self.publisher.config = mock_config
        skip_list = self.publisher.skip_list
        self.assertEquals(2, len(skip_list))
        self.assertEquals(skip_list[0], 'rpm')
        self.assertEquals(skip_list[1], 'errata')

    @mock.patch('pulp.server.managers.factory.repo_distributor_manager')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._publish_packages_step')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._build_final_report')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._clear_directory')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._publish_over_https')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._publish_over_http')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._publish_errata')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._publish_drpms')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._publish_rpms')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._publish_distribution')
    def test_publish(self, mock_publish_distribution, mock_publish_rpms, mock_publish_drpms,
                     mock_publish_errata, mock_publish_over_http, mock_publish_over_https,
                     mock_clear_directory, mock_build_final_report, mock_packages_step,
                     mock_distribution_manager):

        self._init_publisher()
        self.publisher.repo.content_unit_counts = {}
        self.publisher.publish()

        mock_publish_distribution.assert_called_once()
        mock_publish_rpms.assert_called_once()
        mock_publish_drpms.assert_called_once()
        mock_publish_errata.assert_called_once()
        mock_publish_over_http.assert_called_once()
        mock_publish_over_https.assert_called_once()
        mock_clear_directory.assert_called_once_with(self.publisher.repo.working_dir)
        mock_build_final_report.assert_called_once()

        self.assertEquals(TYPE_ID_PKG_GROUP, mock_packages_step.call_args_list[0][0][0])
        self.assertEquals(reporting.PUBLISH_PACKAGE_GROUPS_STEP,
                          mock_packages_step.call_args_list[0][0][1])
        self.assertEquals(TYPE_ID_PKG_CATEGORY, mock_packages_step.call_args_list[1][0][0])
        self.assertEquals(reporting.PUBLISH_PACKAGE_CATEGORIES_STEP,
                          mock_packages_step.call_args_list[1][0][1])

        self.assertTrue(os.path.exists(self.publisher.repo.working_dir))
        # repomd.xml should have been automatically created
        self.assertTrue(os.path.exists(os.path.join(self.publisher.repo.working_dir, 'repodata', 'repomd.xml')))

    def test_cancel(self):
        self._init_publisher()
        step = reporting.PUBLISH_STEPS[0]

        self.publisher._init_step_progress_report(step)

        self.publisher.cancel()

        self.assertTrue(self.publisher.canceled)
        self.assertEqual(self.publisher.progress_report[step][reporting.STATE], reporting.PUBLISH_CANCELED_STATE)

        for s in reporting.PUBLISH_STEPS[1:]:
            self.assertEqual(self.publisher.progress_report[s][reporting.STATE], reporting.PUBLISH_NOT_STARTED_STATE)

    # -- distribution publishing testing ------------------------------------------------

    def _generate_distribution_unit(self, name, metadata = {}):
        storage_path = os.path.join(self.working_dir, 'content', name)
        if not os.path.exists(storage_path):
            os.makedirs(storage_path)

        unit_key = {"id": name}
        unit_metadata = {"files": [
            {
              "downloadurl": "http://download-01.eng.brq.redhat.com/pub/rhel/released/RHEL-6/6.4/Server/x86_64/os/images/boot.iso",
              "item_type": "distribution",
              "savepath": "/var/lib/pulp/working/repos/distro/importers/yum_importer/tmpGn5a2b/tmpE7TPuQ/images/boot.iso",
              "checksumtype": "sha256",
              "relativepath": "images/boot.iso",
              "checksum": "929669e1203117f2b6a0d94f963af11db2eafe84f05c42c7e582d285430dc7a4",
              "pkgpath": "/var/lib/pulp/content/distribution/ks-Red Hat Enterprise Linux-Server-6.4-x86_64/images",
              "filename": "boot.iso"
            }
        ]}
        unit_metadata.update(metadata)
        self._touch(os.path.join(storage_path, 'images', 'boot.iso'))

        return Unit(TYPE_ID_DISTRO, unit_key, unit_metadata, storage_path)

    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._publish_distribution_packages_link')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._publish_distribution_treeinfo')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._publish_distribution_files')
    @mock.patch('pulp.plugins.conduits.repo_publish.RepoPublishConduit.get_units')
    def test_publish_distribution(self, mock_get_units, mock_files, mock_treeinfo, mock_packages):
        self._init_publisher()
        self.publisher.repo.content_unit_counts = {TYPE_ID_DISTRO: 1}
        units = [self._generate_distribution_unit(u) for u in ('one', )]
        mock_get_units.return_value = units

        self.publisher._publish_distribution()

        mock_files.assert_called_once_with(units[0])
        mock_treeinfo.assert_called_once_with(units[0])
        mock_packages.assert_called_once_with(units[0])
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_DISTRIBUTION_STEP][reporting.STATE], reporting.PUBLISH_FINISHED_STATE)

    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._init_step_progress_report')
    def test_publish_distribution_canceled(self, mock_progress_report):
        self._init_publisher()

        self.publisher.canceled = True
        self.publisher._publish_distribution()
        self.assertFalse(mock_progress_report.called)


    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._record_failure')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._publish_distribution_treeinfo')
    @mock.patch('pulp.plugins.conduits.repo_publish.RepoPublishConduit.get_units')
    def test_publish_distribution_error(self, mock_get_units, mock_treeinfo, mock_record_failure):
        self._init_publisher()
        self.publisher.repo.content_unit_counts = {TYPE_ID_DISTRO: 1}
        units = [self._generate_distribution_unit(u) for u in ('one', )]
        mock_get_units.return_value = units
        error = Exception('Test Error')
        mock_treeinfo.side_effect = error

        self.publisher._publish_distribution()

        mock_record_failure.assert_called_once_with(reporting.PUBLISH_DISTRIBUTION_STEP, error)
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_DISTRIBUTION_STEP][reporting.STATE], reporting.PUBLISH_FAILED_STATE)

    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._publish_distribution_packages_link')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._publish_distribution_treeinfo')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._publish_distribution_files')
    @mock.patch('pulp.plugins.conduits.repo_publish.RepoPublishConduit.get_units')
    def test_publish_distribution_multiple_distribution(self, mock_get_units,
                                                        mock_treeinfo, mock_files, mock_packages):
        self._init_publisher()
        self.publisher.repo.content_unit_counts = {TYPE_ID_DISTRO: 2}
        units = [self._generate_distribution_unit(u) for u in ('one', 'two')]
        mock_get_units.return_value = units

        self.publisher._publish_distribution()
        self.assertFalse(mock_files.called)
        self.assertFalse(mock_treeinfo.called)
        self.assertFalse(mock_packages.called)
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_DISTRIBUTION_STEP][reporting.STATE], reporting.PUBLISH_FAILED_STATE)

    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._publish_distribution_packages_link')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._publish_distribution_treeinfo')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._publish_distribution_files')
    @mock.patch('pulp.plugins.conduits.repo_publish.RepoPublishConduit.get_units')
    def test_publish_distribution_no_distribution(self, mock_get_units,
                                                  mock_treeinfo, mock_files,
                                                  mock_packages):
        self._init_publisher()
        mock_get_units.return_value = []
        self.publisher.repo.content_unit_counts = {TYPE_ID_DISTRO: 0}


        self.publisher._publish_distribution()
        self.assertFalse(mock_files.called)
        self.assertFalse(mock_treeinfo.called)
        self.assertFalse(mock_packages.called)
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_DISTRIBUTION_STEP][reporting.STATE], reporting.PUBLISH_FINISHED_STATE)

    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher.skip_list')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._publish_distribution_packages_link')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._publish_distribution_treeinfo')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._publish_distribution_files')
    @mock.patch('pulp.plugins.conduits.repo_publish.RepoPublishConduit.get_units')
    def test_publish_distribution_skipped(self, mock_get_units,
                                          mock_treeinfo, mock_files,
                                          mock_packages, mock_skip_list):
        self._init_publisher()
        units = [self._generate_distribution_unit(u) for u in ('one', 'two')]
        mock_get_units.return_value = units

        mock_skip_list.__get__ = mock.Mock(return_value=[TYPE_ID_DISTRO])

        self.publisher._publish_distribution()
        self.assertFalse(mock_files.called)
        self.assertFalse(mock_treeinfo.called)
        self.assertFalse(mock_packages.called)
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_DISTRIBUTION_STEP][reporting.STATE], reporting.PUBLISH_SKIPPED_STATE)

    def test_publish_distribution_treeinfo_does_nothing_if_no_treeinfo_file(self):
        self._init_publisher()
        unit = self._generate_distribution_unit('one')
        self.publisher._init_step_progress_report(reporting.PUBLISH_DISTRIBUTION_STEP)

        self.publisher._publish_distribution_treeinfo(unit)
        self.assertEquals(
            self.publisher.progress_report[reporting.PUBLISH_DISTRIBUTION_STEP][reporting.PROCESSED], 0)

    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._create_symlink')
    def _perform_treeinfo_success_test(self, treeinfo_name, mock_symlink):
        self._init_publisher()
        unit = self._generate_distribution_unit('one')
        self.publisher._init_step_progress_report(reporting.PUBLISH_DISTRIBUTION_STEP)
        file_name = os.path.join(unit.storage_path, treeinfo_name)
        open(file_name, 'a').close()
        target_directory = os.path.join(self.publisher.repo.working_dir, treeinfo_name)

        self.publisher._publish_distribution_treeinfo(unit)

        mock_symlink.assert_called_once_with(file_name, target_directory)
        self.assertEquals(
            self.publisher.progress_report[reporting.PUBLISH_DISTRIBUTION_STEP][reporting.PROCESSED], 1)
        self.assertEquals(
            self.publisher.progress_report[reporting.PUBLISH_DISTRIBUTION_STEP][reporting.SUCCESSES], 1)

    def test_publish_distribution_treeinfo_finds_treeinfo(self):
        self._perform_treeinfo_success_test('treeinfo')

    def test_publish_distribution_treeinfo_finds_dot_treeinfo(self):
        self._perform_treeinfo_success_test('.treeinfo')

    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._create_symlink')
    def test_publish_distribution_treeinfo_error(self, mock_symlink):
        self._init_publisher()
        unit = self._generate_distribution_unit('one')
        self.publisher._init_step_progress_report(reporting.PUBLISH_DISTRIBUTION_STEP)
        file_name = os.path.join(unit.storage_path, 'treeinfo')
        open(file_name, 'a').close()
        target_directory = os.path.join(self.publisher.repo.working_dir, 'treeinfo')
        mock_symlink.side_effect = Exception("Test Error")

        self.assertRaises(Exception, self.publisher._publish_distribution_treeinfo, unit)

        mock_symlink.assert_called_once_with(file_name, target_directory)
        self.assertEquals(
            self.publisher.progress_report[reporting.PUBLISH_DISTRIBUTION_STEP][reporting.PROCESSED], 0)
        self.assertEquals(
            self.publisher.progress_report[reporting.PUBLISH_DISTRIBUTION_STEP][reporting.SUCCESSES], 0)

    def test_publish_distribution_files(self):
        self._init_publisher()
        unit = self._generate_distribution_unit('one')
        self.publisher._init_step_progress_report(reporting.PUBLISH_DISTRIBUTION_STEP)
        self.publisher._publish_distribution_files(unit)

        self.assertEquals(
            self.publisher.progress_report[reporting.PUBLISH_DISTRIBUTION_STEP][reporting.TOTAL], 1)
        self.assertEquals(
            self.publisher.progress_report[reporting.PUBLISH_DISTRIBUTION_STEP][reporting.SUCCESSES], 1)
        self.assertEquals(
            self.publisher.progress_report[reporting.PUBLISH_DISTRIBUTION_STEP][reporting.PROCESSED], 1)

        content_file = os.path.join(unit.storage_path, 'images', 'boot.iso')
        created_link = os.path.join(self.publisher.repo.working_dir, "images", 'boot.iso')
        self.assertTrue(os.path.islink(created_link))
        self.assertEquals(os.path.realpath(created_link), os.path.realpath(content_file))

    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._create_symlink')
    def test_publish_distribution_files_error(self, mock_symlink):
        self._init_publisher()
        unit = self._generate_distribution_unit('one')
        self.publisher._init_step_progress_report(reporting.PUBLISH_DISTRIBUTION_STEP)
        mock_symlink.side_effect = Exception('Test Error')
        self.assertRaises(Exception, self.publisher._publish_distribution_files, unit)
        self.assertEquals(
            self.publisher.progress_report[reporting.PUBLISH_DISTRIBUTION_STEP][reporting.TOTAL], 1)
        self.assertEquals(
            self.publisher.progress_report[reporting.PUBLISH_DISTRIBUTION_STEP][reporting.SUCCESSES], 0)
        self.assertEquals(
            self.publisher.progress_report[reporting.PUBLISH_DISTRIBUTION_STEP][reporting.PROCESSED], 0)

    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._create_symlink')
    def test_publish_distribution_files_no_files(self, mock_symlink):
        self._init_publisher()
        unit = self._generate_distribution_unit('one')
        unit.metadata.pop('files', None)
        self.publisher._publish_distribution_files(unit)
        #This would throw an exception if it didn't work properly

    def test_publish_distribution_packages_link(self):
        self._init_publisher()
        self.publisher._init_step_progress_report(reporting.PUBLISH_DISTRIBUTION_STEP)
        unit = self._generate_distribution_unit('one')
        self.publisher._publish_distribution_packages_link(unit)

        created_link = os.path.join(self.publisher.repo.working_dir, 'Packages')
        self.assertTrue(os.path.islink(created_link))
        self.assertEquals(os.path.realpath(created_link),
                          os.path.realpath(self.publisher.repo.working_dir))

    def test_publish_distribution_packages_link_with_packagedir(self):
        self._init_publisher()
        self.publisher._init_step_progress_report(reporting.PUBLISH_DISTRIBUTION_STEP)
        unit = self._generate_distribution_unit('one', {'packagedir': 'Server'})
        self.publisher._publish_distribution_packages_link(unit)
        self.assertEquals('Server', self.publisher.package_dir)

    def test_publish_distribution_packages_link_with_invalid_packagedir(self):
        self._init_publisher()
        self.publisher._init_step_progress_report(reporting.PUBLISH_DISTRIBUTION_STEP)
        unit = self._generate_distribution_unit('one', {'packagedir': 'Server/../../foo'})
        self.assertRaises(InvalidValue, self.publisher._publish_distribution_packages_link, unit)

    def test_publish_distribution_packages_link_with_packagedir_equals_Packages(self):
        self._init_publisher()
        self.publisher._init_step_progress_report(reporting.PUBLISH_DISTRIBUTION_STEP)
        unit = self._generate_distribution_unit('one', {'packagedir': 'Packages'})
        self.publisher._publish_distribution_packages_link(unit)
        packages_dir = os.path.join(self.publisher.repo.working_dir, 'Packages')
        self.assertEquals('Packages', self.publisher.package_dir)
        self.assertFalse(os.path.isdir(packages_dir))

    def test_publish_distribution_packages_link_with_packagedir_delete_existing_Packages(self):
        self._init_publisher()
        self.publisher._init_step_progress_report(reporting.PUBLISH_DISTRIBUTION_STEP)
        packages_dir = os.path.join(self.publisher.repo.working_dir, 'Packages')
        self.publisher._create_symlink("./", packages_dir)
        unit = self._generate_distribution_unit('one', {'packagedir': 'Packages'})
        self.publisher._publish_distribution_packages_link(unit)
        packages_dir = os.path.join(self.publisher.repo.working_dir, 'Packages')
        self.assertFalse(os.path.isdir(packages_dir))

    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._create_symlink')
    def test_publish_distribution_packages_link_error(self, mock_symlink):
        self._init_publisher()
        self.publisher._init_step_progress_report(reporting.PUBLISH_DISTRIBUTION_STEP)
        mock_symlink.side_effect = Exception("Test Error")
        self.assertRaises(Exception, self.publisher._publish_distribution_packages_link)

    # -- publish drpms testing -------------------------------------------------

    @mock.patch('pulp.plugins.conduits.repo_publish.RepoPublishConduit.get_units')
    def test_publish_drpms(self, mock_get_units):
        self._init_publisher()
        self.publisher.repo.content_unit_counts = {TYPE_ID_DRPM: 2}

        units = [self._generate_drpm(u) for u in ('A', 'B')]
        mock_get_units.return_value = units

        self.publisher._publish_drpms()

        for u in units:
            path = os.path.join(self.working_dir, 'drpms', u.unit_key['filename'])
            self.assertTrue(os.path.exists(path))
            self.assertTrue(os.path.islink(path))

        self.assertTrue(os.path.exists(os.path.join(self.working_dir, 'repodata/prestodelta.xml.gz')))

        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_DELTA_RPMS_STEP][reporting.STATE],
                         reporting.PUBLISH_FINISHED_STATE,
                         self.publisher.progress_report[reporting.PUBLISH_DELTA_RPMS_STEP][reporting.ERROR_DETAILS])
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_DELTA_RPMS_STEP][reporting.TOTAL], 2)
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_DELTA_RPMS_STEP][reporting.PROCESSED], 2)
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_DELTA_RPMS_STEP][reporting.FAILURES], 0)
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_DELTA_RPMS_STEP][reporting.SUCCESSES], 2)

    def test_publish_drpms_skipped(self):
        self._init_publisher()

        self.publisher.config.default_config['skip'] = [TYPE_ID_DRPM]

        self.publisher._publish_drpms()

        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_DELTA_RPMS_STEP][reporting.STATE], reporting.PUBLISH_SKIPPED_STATE)

    # -- publish metadata files testing ---------------------------------------

    @mock.patch('pulp.plugins.conduits.repo_publish.RepoPublishConduit.get_units')
    def test_publish_metadata(self, mock_get_units):
        # Setup
        units = [self._generate_metadata_file_unit(dt, 'test-repo') for dt in ('A', 'B')]
        mock_get_units.return_value = units
        self._init_publisher()
        self.publisher.repo.content_unit_counts = {TYPE_ID_YUM_REPO_METADATA_FILE : len(units)}

        # Test
        self.publisher._publish_metadata()

        # Verify
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_METADATA_STEP][reporting.STATE], reporting.PUBLISH_FINISHED_STATE)
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_METADATA_STEP][reporting.TOTAL], len(units))
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_METADATA_STEP][reporting.FAILURES], 0)
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_METADATA_STEP][reporting.SUCCESSES], len(units))

        for u in units:
            data_type = u.unit_key['data_type']
            path = os.path.join(self.working_dir, publish.REPO_DATA_DIR_NAME, data_type)
            self.assertTrue(os.path.exists(path))
            self.assertTrue(os.path.islink(path))
            self.assertTrue(os.path.exists(os.path.join(self.working_dir, 'repodata/%s' % data_type)))

    @mock.patch('pulp.plugins.conduits.repo_publish.RepoPublishConduit.get_units')
    def test_publish_metadata_failed(self, mock_get_units):
        # Setup
        units = [self._generate_metadata_file_unit(dt, 'test-repo') for dt in ('A', 'B')]
        mock_get_units.return_value = units
        self._init_publisher()
        self.publisher.repo.content_unit_counts = {TYPE_ID_YUM_REPO_METADATA_FILE : len(units)}

        mock_error_raiser = mock.MagicMock()
        mock_error_raiser.side_effect = Exception('foo')
        self.publisher.repomd_file_context.add_metadata_file_metadata = mock_error_raiser

        # Test
        self.publisher._publish_metadata()

        # Verify
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_METADATA_STEP][reporting.STATE], reporting.PUBLISH_FAILED_STATE)
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_METADATA_STEP][reporting.TOTAL], len(units))
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_METADATA_STEP][reporting.FAILURES], len(units))
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_METADATA_STEP][reporting.SUCCESSES], 0)

    def test_publish_metadata_canceled(self):
        # Setup
        self._init_publisher()
        self.publisher.canceled = True
        mock_report_progress = mock.MagicMock()
        self.publisher._report_progress = mock_report_progress

        # Test
        self.publisher._publish_metadata()

        # Verify
        self.assertEqual(0, mock_report_progress.call_count)

    def test_publish_metadata_skipped(self):
        # Setup
        self._init_publisher()
        self.publisher.config.repo_plugin_config['skip'] = [TYPE_ID_YUM_REPO_METADATA_FILE]
        mock_report_progress = mock.MagicMock()
        self.publisher._report_progress = mock_report_progress

        # Test
        self.publisher._publish_metadata()

        # Verify
        mock_report_progress.assert_called_once_with(publish.PUBLISH_METADATA_STEP,
                                                     state=publish.PUBLISH_SKIPPED_STATE)

    def test_publish_metadata_zero_count(self):
        # Setup
        self._init_publisher()
        mock_report_progress = mock.MagicMock()
        self.publisher._report_progress = mock_report_progress

        # Test
        self.publisher._publish_metadata()

        # Verify
        mock_report_progress.assert_called_once_with(publish.PUBLISH_METADATA_STEP,
                                                     state=publish.PUBLISH_FINISHED_STATE,
                                                     total=0)
    # -- _publish_packages_step testing ---------------------------------------

    def test_publish_packages_step_skip_units(self):
        self._init_publisher()
        mock_method = mock.Mock()
        self.publisher.config = PluginCallConfiguration(None, {'skip': [TYPE_ID_PKG_GROUP]})
        self.publisher._publish_packages_step(TYPE_ID_PKG_GROUP,
                                              reporting.PUBLISH_PACKAGE_GROUPS_STEP,
                                              mock_method)
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_PACKAGE_GROUPS_STEP]
                         [reporting.STATE],
                         reporting.PUBLISH_SKIPPED_STATE)

    def test_publish_packages_step_no_units(self):
        self._init_publisher()
        self.publisher.repo.content_unit_counts = {TYPE_ID_PKG_GROUP: 0}
        mock_method = mock.Mock()
        self.publisher._publish_packages_step(TYPE_ID_PKG_GROUP,
                                              reporting.PUBLISH_PACKAGE_GROUPS_STEP,
                                              mock_method)
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_PACKAGE_GROUPS_STEP]
                         [reporting.STATE],
                         reporting.PUBLISH_FINISHED_STATE)
        self.assertFalse(mock_method.called)

    @mock.patch('pulp.plugins.conduits.repo_publish.RepoPublishConduit.get_units')
    def test_publish_packages_step_single_unit(self, mock_get_units):
        self._init_publisher()
        self.publisher.repo.content_unit_counts = {TYPE_ID_PKG_GROUP: 1}
        mock_method = mock.Mock()
        mock_get_units.return_value = ['mock_unit']
        self.publisher._publish_packages_step(TYPE_ID_PKG_GROUP,
                                              reporting.PUBLISH_PACKAGE_GROUPS_STEP,
                                              mock_method)
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_PACKAGE_GROUPS_STEP]
                         [reporting.STATE],
                         reporting.PUBLISH_FINISHED_STATE)
        mock_method.assert_called_once_with('mock_unit')
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_PACKAGE_GROUPS_STEP][
                         reporting.TOTAL], 1)
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_PACKAGE_GROUPS_STEP][
                         reporting.PROCESSED], 1)
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_PACKAGE_GROUPS_STEP][
                         reporting.FAILURES], 0)
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_PACKAGE_GROUPS_STEP][
                         reporting.SUCCESSES], 1)

    @mock.patch('pulp.plugins.conduits.repo_publish.RepoPublishConduit.get_units')
    def test_publish_packages_step_single_unit_exception(self, mock_get_units):
        self._init_publisher()
        self.publisher.repo.content_unit_counts = {TYPE_ID_PKG_GROUP: 1}
        mock_method = mock.Mock()
        mock_method.side_effect = Exception()
        mock_get_units.return_value = ['mock_unit']
        self.publisher._publish_packages_step(TYPE_ID_PKG_GROUP,
                                              reporting.PUBLISH_PACKAGE_GROUPS_STEP,
                                              mock_method)
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_PACKAGE_GROUPS_STEP]
                         [reporting.STATE],
                         reporting.PUBLISH_FAILED_STATE)
        mock_method.assert_called_once_with('mock_unit')
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_PACKAGE_GROUPS_STEP][
                         reporting.TOTAL], 1)
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_PACKAGE_GROUPS_STEP][
                         reporting.PROCESSED], 1)
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_PACKAGE_GROUPS_STEP][
                         reporting.FAILURES], 1)
        self.assertEqual(self.publisher.progress_report[reporting.PUBLISH_PACKAGE_GROUPS_STEP][
                         reporting.SUCCESSES], 0)
