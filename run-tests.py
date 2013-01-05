#!/usr/bin/env python
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

import subprocess
import sys 

PACKAGES = [ 
    'pulp_rpm',
    'rpm_admin_consumer',
    'rpm_repo',
    'rpm_sync',
    'rpm_units_copy',
    'rpm_units_search',
    'rpm_upload',
    'yum_distributor',
    'yum_importer'
]

TESTS = 'pulp_rpm/test/unit'

args = [ 
    'nosetests',
    '--with-coverage',
    '--cover-html',
    '--cover-erase',
    '--cover-package',
    ','.join(PACKAGES),
    TESTS
]

# don't run the server tests in RHEL5.
if sys.version_info < (2, 6): 
    args.extend(['-e', 'server'])

subprocess.call(args)
