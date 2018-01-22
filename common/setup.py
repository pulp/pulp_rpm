from setuptools import setup, find_packages

setup(
    name='pulp_rpm_common',
    version='2.15.1b2',
    license='GPLv2+',
    packages=find_packages(exclude=['test', 'test.*']),
    author='Pulp Team',
    author_email='pulp-list@redhat.com'
)
