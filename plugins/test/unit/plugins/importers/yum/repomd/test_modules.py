import os
import unittest

from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.importers.yum.repomd import modules


DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                        '..', '..', '..', '..', '..', 'data'))


class TestProcessModulemdDocument(unittest.TestCase):
    def test_modulemd_data(self):
        file_path = os.path.join(DATA_DIR, 'django-module.yaml')
        res, _ = modules.from_file(file_path)
        module = res[0]
        modulemd = modules.process_modulemd_document(module)
        self.assertTrue(isinstance(modulemd, models.Modulemd))
        self.assertEqual(modulemd.name, 'django')
        self.assertEqual(modulemd.stream, '1.6')
        self.assertEqual(modulemd.version, 20180307130104)
        self.assertEqual(modulemd.context, 'c2c572ec')
        self.assertEqual(modulemd.arch, 'x64_86')
        self.assertEqual(modulemd.summary, 'A high-level Python Web framework')
        description = """Django is a high-level Python Web framework that encourages rapid \
development and a clean, pragmatic design. It focuses on automating as much as possible and \
adhering to the DRY (Don't Repeat Yourself) principle."""
        self.assertEqual(modulemd.description, description)
        profiles = {'default': ['python2-django'],
                    'python2_development': ['python2-django']}
        self.assertEqual(modulemd.profiles, profiles)
        self.assertEqual(modulemd.artifacts, [
            'python-django-bash-completion-0:1.6.11.7-1.module_1560+089ce146.noarch',
            'python2-django-0:1.6.11.7-1.module_1560+089ce146.noarch'])


class TestProcessModulemdDefaultsDocument(unittest.TestCase):
    def test_modulemd_defaults_one_stream(self):
        """
        Test processing of one default profile for one stream
        """
        file_path = os.path.join(DATA_DIR, 'modulemd-defaults-examples.yaml')
        _, res = modules.from_file(file_path)
        module = res[0]
        modulemd_defaults = modules.process_defaults_document(module)
        self.assertTrue(isinstance(modulemd_defaults, models.ModulemdDefaults))
        self.assertEqual(modulemd_defaults.name, 'postgresql')
        self.assertEqual(modulemd_defaults.stream, '8.0')
        profiles = {'8.0': ['server']}
        self.assertEqual(modulemd_defaults.profiles.decode(), profiles)

    def test_modulemd_defaults_multiple_streams(self):
        """
        Test processing of default profiles for multiple streams
        """
        file_path = os.path.join(DATA_DIR, 'modulemd-defaults-examples.yaml')
        _, res = modules.from_file(file_path)
        module = res[1]
        modulemd_defaults = modules.process_defaults_document(module)
        self.assertTrue(isinstance(modulemd_defaults, models.ModulemdDefaults))
        self.assertEqual(modulemd_defaults.name, 'nodejs')
        self.assertEqual(modulemd_defaults.stream, '8.0')
        profiles = {'6.0': ['default'],
                    '8.0': ['super']}
        self.assertEqual(modulemd_defaults.profiles.decode(), profiles)

    def test_modulemd_defaults_multiple_profiles(self):
        """
        Test processing of multiple default profiles for one stream.

        Intents are ignored and don't break processing.
        """
        file_path = os.path.join(DATA_DIR, 'modulemd-defaults-examples.yaml')
        _, res = modules.from_file(file_path)
        module = res[2]
        modulemd_defaults = modules.process_defaults_document(module)
        self.assertTrue(isinstance(modulemd_defaults, models.ModulemdDefaults))
        self.assertEqual(modulemd_defaults.name, 'httpd')
        self.assertEqual(modulemd_defaults.stream, None)
        profiles = {'2.6': ['client', 'server']}
        self.assertEqual(modulemd_defaults.profiles.decode(), profiles)
