#!/usr/bin/env python2

from setuptools import setup, find_packages

setup(
    name='pulp_rpm_plugins',
    version='2.8.7b1',
    license='GPLv2+',
    packages=find_packages(exclude=['test', 'test.*']),
    author='Pulp Team',
    author_email='pulp-list@redhat.com',
    entry_points={
        'pulp.importers': [
            'importer = pulp_rpm.plugins.importers.yum.importer:entry_point',
            'isoImporter = pulp_rpm.plugins.importers.iso.importer:entry_point'
        ],
        'pulp.profilers': [
            'profiler = pulp_rpm.plugins.profilers.yum:entry_point',
        ],
        'pulp.catalogers': [
            'yum_cataloger = pulp_rpm.plugins.catalogers.yum:entry_point',
            'rhui_cataloger = pulp_rpm.plugins.catalogers.rhui:entry_point',
        ],
        'pulp.distributors': [
            'distributor = pulp_rpm.plugins.distributors.yum.distributor:entry_point',
            'ExportDistributor = pulp_rpm.plugins.distributors.export_distributor.distributor:'
            'entry_point',
            'IsoDistributor = pulp_rpm.plugins.distributors.iso_distributor.distributor:entry_point'
        ],
        'pulp.group_distributors': [
            'rpm_export = pulp_rpm.plugins.distributors.export_distributor.groupdistributor:'
            'entry_point',
        ],
        'pulp.server.db.migrations': [
            'pulp_rpm = pulp_rpm.plugins.migrations'
        ],
        'pulp.unit_models': [
            'rpm=pulp_rpm.plugins.db.models:RPM',
            'srpm=pulp_rpm.plugins.db.models:SRPM',
            'drpm=pulp_rpm.plugins.db.models:DRPM',
            'distribution=pulp_rpm.plugins.db.models:Distribution',
            'erratum=pulp_rpm.plugins.db.models:Errata',
            'package_group=pulp_rpm.plugins.db.models:PackageGroup',
            'package_category=pulp_rpm.plugins.db.models:PackageCategory',
            'package_environment=pulp_rpm.plugins.db.models:PackageEnvironment',
            'yum_repo_metadata_file=pulp_rpm.plugins.db.models:YumMetadataFile',
            'iso=pulp_rpm.plugins.db.models:ISO'
        ]
    }
)
