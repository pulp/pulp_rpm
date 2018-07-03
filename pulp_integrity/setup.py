from setuptools import setup, find_packages

setup(
    name='pulp_rpm_integrity',
    version='2.16',
    license='GPLv2+',
    packages=find_packages(exclude=['test', 'test.*']),
    author='Pulp Team',
    author_email='pulp-list@redhat.com',
    description="An rpm-specific plug-in to pulp_integrity",
    entry_points={
        'validators': [
            'broken_rpm_symlinks = pulp_rpm_integrity.validator:BrokenSymlinksValidator',
        ],
    },
)
