# -*- coding: utf-8 -*-
#
# Copyright © 2012 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

from urlparse import urljoin
import os
import shutil
import unittest

from pulp.server import config
from pulp.server.managers.auth.cert.cert_generator import SerialNumber
from pulp.server.db import connection
from pulp.server.logs import start_logging, stop_logging
from pulp.server.managers import factory as manager_factory
import pulp_rpm.common.constants as constants


SerialNumber.PATH = '/tmp/sn.dat'
TEMP_DISTRO_STORAGE_DIR = '/tmp/pulp/var/lib/pulp/content/distribution/'


TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), '../../../pulp_rpm/test/unit/data')
DEMO_REPOS_PATH = os.path.join(TEST_DATA_DIR, 'repos.fedorapeople.org', 'repos', 'pulp',
                               'pulp', 'demo_repos')

PULP_UNITTEST_REPO_PATH = os.path.join(DEMO_REPOS_PATH, 'pulp_unittest')
PULP_UNITTEST_REPO_URL = urljoin('file://', PULP_UNITTEST_REPO_PATH)
TEST_SRPM_REPO_URL = urljoin(
    'file://', os.path.join(TEST_DATA_DIR, 'pkilambi.fedorapeople.org',
                            'test_srpm_repo'))
REPO_MULTIPLE_VERSIONS_URL = urljoin(
    'file://', os.path.join(TEST_DATA_DIR, 'jmatthews.fedorapeople.org',
                            'repo_multiple_versions'))
ZOO_REPO_URL = urljoin('file://', os.path.join(DEMO_REPOS_PATH, 'zoo'))


class PulpRPMTests(unittest.TestCase):
    """
    Base unit test class for all rpm synchronization related unit tests.
    """

    @classmethod
    def setUpClass(cls):
        if not os.path.exists('/tmp/pulp'):
            os.makedirs('/tmp/pulp')
        stop_logging()
        config_filename = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                                       '../../../pulp_rpm/test/unit/data', 'test-override-pulp.conf')
        config.config.read(config_filename)
        start_logging()
        name = config.config.get('database', 'name')
        connection.initialize(name)
        manager_factory.initialize()
        constants.DISTRIBUTION_STORAGE_PATH = TEMP_DISTRO_STORAGE_DIR

    @classmethod
    def tearDownClass(cls):
        name = config.config.get('database', 'name')
        connection._CONNECTION.drop_database(name)
        shutil.rmtree('/tmp/pulp')

    def setUp(self):
        super(PulpRPMTests, self).setUp()

    def simulate_sync(self, repo, src):
        # Simulate a repo sync, copy the source contents to the repo.working_dir
        dst = os.path.join(repo.working_dir, repo.id)
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)


