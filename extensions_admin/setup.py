from setuptools import setup, find_packages

setup(
    name='pulp_rpm_extensions_admin',
    version='2.10.0b1',
    license='GPLv2+',
    packages=find_packages(exclude=['test', 'test.*']),
    author='Pulp Team',
    author_email='pulp-list@redhat.com',
    entry_points={
        'pulp.extensions.admin': [
            'iso_admin = pulp_rpm.extensions.admin.iso.pulp_cli:initialize',
            'rpm_admin = pulp_rpm.extensions.admin.rpm_admin_consumer.pulp_cli:initialize',
            'rpm_repo_admin = pulp_rpm.extensions.admin.rpm_repo.pulp_cli:initialize',
        ]
    }
)
