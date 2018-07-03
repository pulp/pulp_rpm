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
