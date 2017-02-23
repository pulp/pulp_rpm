from setuptools import setup, find_packages

setup(
    name='pulp_rpm_common',
    version='2.12.2a1',
    license='GPLv2+',
    packages=find_packages(exclude=['test', 'test.*']),
    author='Pulp Team',
    author_email='pulp-list@redhat.com'
)
