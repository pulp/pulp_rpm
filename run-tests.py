#!/usr/bin/env python2

import os
import subprocess

from pulp.devel.test_runner import run_tests


# Find and eradicate any existing .pyc files, so they do not eradicate us!
PROJECT_DIR = os.path.dirname(__file__)
subprocess.call(['find', PROJECT_DIR, '-name', '*.pyc', '-delete'])

PACKAGES = [
    PROJECT_DIR,
    'pulp_rpm',
    'rpm_repo',
    'rpm_sync',
    'rpm_units_copy',
    'rpm_units_search',
    'rpm_upload',
    'yum_distributor',
    'yum_importer'
]

TESTS = [
    'common/test/unit',
    'handlers/test/unit',
    'extensions_consumer/test/unit/',
]
PLUGIN_TESTS = [
    'plugins/test/unit',
    'extensions_admin/test/unit/',
    'devel/test/unit'
]

dir_safe_all_platforms = [os.path.join(os.path.dirname(__file__), x) for x in TESTS]
dir_safe_non_rhel5 = [os.path.join(os.path.dirname(__file__), x) for x in PLUGIN_TESTS]

run_tests(PACKAGES, dir_safe_all_platforms, dir_safe_non_rhel5, flake8_paths=[PROJECT_DIR])
