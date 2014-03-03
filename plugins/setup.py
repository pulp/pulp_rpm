#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

from setuptools import setup, find_packages

setup(
    name='pulp_rpm_plugins',
    version='2.4.0',
    license='GPLv2+',
    packages=find_packages(),
    author='Pulp Team',
    author_email='pulp-list@redhat.com',
    entry_points={
        'pulp.importers': [
            'importer = pulp_rpm.plugins.importers.yum.importer:entry_point',
            'isoImporter = pulp_rpm.plugins.importers.iso_importer.importer:entry_point'
        ],
        'pulp.profilers': [
            'profiler = pulp_rpm.plugins.profilers.yum:entry_point',
        ],
        'pulp.catalogers': [
            'profiler = pulp_rpm.plugins.catalogers.yum:entry_point',
        ],
        'pulp.distributors': [
            'distributor = pulp_rpm.plugins.distributors.yum.distributor:entry_point',
            'ExportDistributor = pulp_rpm.plugins.distributors.export_distributor.distributor:entry_point',
            'IsoDistributor = pulp_rpm.plugins.distributors.iso_distributor.distributor:entry_point'
        ],
        'pulp.group_distributors': [
            'rpm_export = pulp_rpm.plugins.distributors.export_distributor.groupdistributor:entry_point',
        ]
    }
)
