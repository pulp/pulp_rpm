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
import sys
import unittest

import mock

from pulp.plugins.conduits.repo_publish import RepoPublishConduit
from pulp.plugins.config import PluginCallConfiguration
from pulp.plugins.model import Repository, Unit

PACKAGE_PATH = os.path.join(os.path.dirname(__file__), '../../')
sys.path.insert(0, PACKAGE_PATH)

from pulp_rpm.common.ids import TYPE_ID_RPM, YUM_DISTRIBUTOR_ID
from pulp_rpm.plugins.distributors.yum import publish


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

        config_defaults = {'http': True,
                           'https': True,
                           'relative_url': None,
                           'http_publish_dir': self.published_dir + 'http/',
                           'https_publish_dir': self.published_dir + 'https/'}
        config = PluginCallConfiguration(None, None)
        config.default_config.update(config_defaults)

        self.publisher = publish.Publisher(repo, conduit, config)


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

        step = publish.PUBLISH_STEPS[0]

        self.publisher._init_step_progress_report(step)

        self.assertEqual(self.publisher.progress_report[step], publish.PROGRESS_SUB_REPORT)

    def test_init_step_progress_not_a_step(self):
        self._init_publisher()

        step = 'not_a_step'

        self.assertRaises(AssertionError, self.publisher._init_step_progress_report, step)

    @mock.patch('pulp.plugins.conduits.repo_publish.RepoPublishConduit.set_progress')
    def test_report_progress(self, mock_set_progress):
        self._init_publisher()

        step = publish.PUBLISH_STEPS[1]

        updates = {publish.STATE: publish.PUBLISH_FINISHED_STATE,
                   publish.TOTAL: 1,
                   publish.PROCESSED: 1,
                   publish.SUCCESSES: 1}

        self.publisher._report_progress(step, **updates)

        self.assertEqual(self.publisher.progress_report[step], updates)

        mock_set_progress.assert_called_once_with(self.publisher.progress_report)

    def test_record_failure(self):
        self._init_publisher()
        step = publish.PUBLISH_STEPS[2]
        self.publisher._init_step_progress_report(step)

        error_msg = 'Too bad, so sad'

        try:
            raise Exception(error_msg)

        except Exception, e:
            self.publisher._record_failure(step, e)

        self.assertEqual(self.publisher.progress_report[step][publish.FAILURES], 1)
        self.assertEqual(self.publisher.progress_report[step][publish.ERROR_DETAILS][0], error_msg)

    def test_build_final_report_success(self):
        self._init_publisher()

        for step in publish.PUBLISH_STEPS:
            self.publisher._init_step_progress_report(step)
            self.publisher.progress_report[step][publish.STATE] = publish.PUBLISH_FINISHED_STATE

        report = self.publisher._build_final_report()

        self.assertTrue(report.success_flag)

    def test_build_final_report_failure(self):
        self._init_publisher()

        for step in publish.PUBLISH_STEPS:
            self.publisher._init_step_progress_report(step)
            self.publisher.progress_report[step][publish.STATE] = publish.PUBLISH_FAILED_STATE
            self.publisher.progress_report[step][publish.ERROR_DETAILS].append('boo hoo')

        report = self.publisher._build_final_report()

        self.assertFalse(report.success_flag)

    # -- http/https publishing testing -----------------------------------------

    def test_publish_http(self):
        self._init_publisher()

        units = [self._generate_rpm(u) for u in ('one', 'two', 'three')]

        self.publisher._init_step_progress_report(publish.PUBLISH_OVER_HTTP_STEP)
        self.publisher._publish_over_http()

        for u in units:
            path = os.path.join(self.published_dir, 'http', self.publisher.repo.id, 'content', u.unit_key['name'])
            self.assertTrue(os.path.exists(path))

        self.assertEqual(self.publisher.progress_report[publish.PUBLISH_OVER_HTTP_STEP][publish.PROCESSED], 1)
        self.assertEqual(self.publisher.progress_report[publish.PUBLISH_OVER_HTTP_STEP][publish.FAILURES], 0)
        self.assertEqual(self.publisher.progress_report[publish.PUBLISH_OVER_HTTP_STEP][publish.SUCCESSES], 1)
        self.assertEqual(self.publisher.progress_report[publish.PUBLISH_OVER_HTTP_STEP][publish.STATE], publish.PUBLISH_FINISHED_STATE)

    def test_publish_http_skipped(self):
        self._init_publisher()

        self.publisher.config.default_config['http'] = False

        self.publisher._publish_over_http()

        self.assertEqual(self.publisher.progress_report[publish.PUBLISH_OVER_HTTP_STEP][publish.STATE], publish.PUBLISH_SKIPPED_STATE)

    def test_publish_https(self):
        self._init_publisher()

        units = [self._generate_rpm(u) for u in ('one', 'two', 'three')]

        self.publisher._init_step_progress_report(publish.PUBLISH_OVER_HTTPS_STEP)
        self.publisher._publish_over_https()

        for u in units:
            path = os.path.join(self.published_dir, 'https', self.publisher.repo.id, 'content', u.unit_key['name'])
            self.assertTrue(os.path.exists(path))

        self.assertEqual(self.publisher.progress_report[publish.PUBLISH_OVER_HTTPS_STEP][publish.PROCESSED], 1)
        self.assertEqual(self.publisher.progress_report[publish.PUBLISH_OVER_HTTPS_STEP][publish.FAILURES], 0)
        self.assertEqual(self.publisher.progress_report[publish.PUBLISH_OVER_HTTPS_STEP][publish.SUCCESSES], 1)
        self.assertEqual(self.publisher.progress_report[publish.PUBLISH_OVER_HTTPS_STEP][publish.STATE], publish.PUBLISH_FINISHED_STATE)

    def test_publish_https_skipped(self):
        self._init_publisher()

        self.publisher.config.default_config['https'] = False

        self.publisher._publish_over_https()

        self.assertEqual(self.publisher.progress_report[publish.PUBLISH_OVER_HTTPS_STEP][publish.STATE], publish.PUBLISH_SKIPPED_STATE)

    # -- rpm publishing testing ------------------------------------------------

    @mock.patch('pulp.plugins.conduits.repo_publish.RepoPublishConduit.get_units')
    def test_publish_rpms(self, mock_get_units):
        self._init_publisher()

        units = [self._generate_rpm(u) for u in ('one', 'two', 'tree')]
        mock_get_units.return_value = units

        self.publisher._publish_rpms()

        for u in units:
            path = os.path.join(self.working_dir, u.unit_key['name'])
            self.assertTrue(os.path.exists(path))
            self.assertTrue(os.path.islink(path))

        self.assertTrue(os.path.exists(os.path.join(self.working_dir, 'repodata/primary.xml.gz')))

        self.assertEqual(self.publisher.progress_report[publish.PUBLISH_RPMS_STEP][publish.STATE], publish.PUBLISH_FINISHED_STATE)
        self.assertEqual(self.publisher.progress_report[publish.PUBLISH_RPMS_STEP][publish.TOTAL], 3)
        self.assertEqual(self.publisher.progress_report[publish.PUBLISH_RPMS_STEP][publish.PROCESSED], 3)
        self.assertEqual(self.publisher.progress_report[publish.PUBLISH_RPMS_STEP][publish.FAILURES], 0)
        self.assertEqual(self.publisher.progress_report[publish.PUBLISH_RPMS_STEP][publish.SUCCESSES], 3)

    def test_publish_rpms_skipped(self):
        self._init_publisher()

        self.publisher.config.default_config['skip'] = {TYPE_ID_RPM: 1}

        self.publisher._publish_rpms()

        self.assertEqual(self.publisher.progress_report[publish.PUBLISH_RPMS_STEP][publish.STATE], publish.PUBLISH_SKIPPED_STATE)

    # -- publish api testing ---------------------------------------------------

    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._build_final_report')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._publish_over_https')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._publish_over_http')
    @mock.patch('pulp_rpm.plugins.distributors.yum.publish.Publisher._publish_rpms')
    def test_publish(self, mock_publish_rpms, mock_publish_over_http,
                     mock_publish_over_https, mock_build_final_report):
        self._init_publisher()

        self.publisher.publish()

        mock_publish_rpms.assert_called_once()
        mock_publish_over_http.assert_called_once()
        mock_publish_over_https.assert_called_once()
        mock_build_final_report.assert_called_once()

        self.assertTrue(os.path.exists(self.publisher.repo.working_dir))

    def test_cancel(self):
        self._init_publisher()
        step = publish.PUBLISH_STEPS[0]

        self.publisher._init_step_progress_report(step)

        self.publisher.cancel()

        self.assertTrue(self.publisher.canceled)
        self.assertEqual(self.publisher.progress_report[step][publish.STATE], publish.PUBLISH_CANCELED_STATE)

        for s in publish.PUBLISH_STEPS[1:]:
            self.assertEqual(self.publisher.progress_report[s][publish.STATE], publish.PUBLISH_SKIPPED_STATE)

