from setuptools import setup, find_packages

requirements = [
    'pulp-rpm-common'
]

setup(
    name='pulp-rpm-cli',
    version='3.0.0a1.dev0',
    license='GPLv2+',
    packages=find_packages(exclude=['test']),
    author='Pulp Team',
    author_email='pulp-list@redhat.com',
    install_requires=requirements,
    entry_points={
        'pulp.extensions.admin': [
            'iso_admin = pulp_rpm.extensions.admin.iso.pulp_cli:initialize',
            'rpm_admin = pulp_rpm.extensions.admin.rpm_admin_consumer.pulp_cli:initialize',
            'rpm_repo_admin = pulp_rpm.extensions.admin.rpm_repo.pulp_cli:initialize',
        ]
    }
)
