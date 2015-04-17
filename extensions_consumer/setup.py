from setuptools import setup, find_packages

setup(
    name='pulp_rpm_extensions_consumer',
    version='2.7.0a2',
    license='GPLv2+',
    packages=find_packages(exclude=['test', 'test.*']),
    author='Pulp Team',
    author_email='pulp-list@redhat.com',
    entry_points={
        'pulp.extensions.consumer': [
            'consumer_cli = pulp_rpm.extensions.consumer.pulp_cli:initialize',
        ]
    }
)
