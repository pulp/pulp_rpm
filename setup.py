#!/usr/bin/env python3

from setuptools import setup, find_packages

with open("requirements.txt") as requirements:
    requirements = requirements.readlines()

with open('README.rst') as f:
    long_description = f.read()

setup(
    name='pulp-rpm',
    version='3.4.0',
    description='RPM plugin for the Pulp Project',
    long_description=long_description,
    license='GPLv2+',
    author='Pulp Project Developers',
    author_email='pulp-list@redhat.com',
    url='http://www.pulpproject.org',
    python_requires='>=3.6',
    install_requires=requirements,
    include_package_data=True,
    packages=find_packages(exclude=['test']),
    classifiers=(
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
        'Operating System :: POSIX :: Linux',
        'Development Status :: 5 - Production/Stable',
        'Framework :: Django',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ),
    entry_points={
        'pulpcore.plugin': [
            'pulp_rpm = pulp_rpm:default_app_config',
        ]
    }
)
