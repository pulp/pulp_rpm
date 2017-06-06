from setuptools import setup, find_packages

setup(
    name='pulp-rpm-common',
    version='3.0.0a1.dev0',
    license='GPLv2+',
    packages=find_packages(exclude=['test', 'test.*']),
    author='Pulp Team',
    author_email='pulp-list@redhat.com'
)
