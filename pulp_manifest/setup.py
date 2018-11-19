from setuptools import setup, find_packages

setup(
    name='pulp_manifest',
    version='2.18b1',
    license='GPLv2+',
    packages=find_packages(exclude=['test', 'test.*']),
    author='Pulp Team',
    author_email='pulp-list@redhat.com',
    description="Tool to generate a PULP_MANIFEST file for a given directory,"
                " so the directory can be recognized by Pulp.",
    entry_points={
        'console_scripts': [
            'pulp-manifest = pulp_manifest.build_manifest:main',
        ]
    },
)
