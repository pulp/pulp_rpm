import pickle
import os
from StringIO import StringIO
import unittest

import mock
from pulp.plugins.model import Unit

from pulp_rpm.plugins.db import models
from pulp_rpm.yum_plugin import updateinfo
from pulp_rpm.yum_plugin.updateinfo import encode_epoch


DATA_DIR = os.path.join(os.path.dirname(__file__), '../../data')


class TestEpochEncoding(unittest.TestCase):
    def setUp(self):
        path = os.path.join(DATA_DIR, 'erratum.pickle')
        self.erratum = pickle.load(open(path))
        unit_key = {'id': self.erratum['id']}
        metadata = dict((k, v) for k, v in self.erratum.items() if not k.startswith('_'))
        del metadata['id']
        self.unit = Unit(models.Errata.TYPE, unit_key, metadata, '')

    @mock.patch.object(updateinfo.log, 'error')
    @mock.patch('__builtin__.open')
    def test_yum_bug_worked_around(self, mock_open, mock_error):
        mock_open.return_value = StringIO()

        # The following will fail for yum version 3.4.3-111 without pulp's
        # workaround in place.
        updateinfo.updateinfo([self.unit], '/a/b/c')

        # Sadly, the only way we have to detect a failure is that it gets logged.
        self.assertEqual(mock_error.call_count, 0)

        # make sure some data was written
        self.assertTrue(mock_open.return_value.len > 0)

    def test_encode_epoch(self):
        self.assertTrue(isinstance(
            self.unit.metadata['pkglist'][0]['packages'][0]['epoch'], unicode))

        encode_epoch(self.unit)

        # make sure there are no unicode epochs
        for packages_dict in self.unit.metadata['pkglist']:
            for package in packages_dict['packages']:
                self.assertFalse(isinstance(package['epoch'], unicode))
