# -*- coding: utf-8 -*-

import os
import unittest

from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.importers.yum.repomd import packages, updateinfo


class TestProcessErratumElement(unittest.TestCase):
    def test_rhel6_real_data(self):
        with open(os.path.join(os.path.dirname(__file__),
                               '../data/RHBA-2010-0836.erratum.xml')) as f:
            errata = packages.package_list_generator(f,
                                                     updateinfo.PACKAGE_TAG,
                                                     updateinfo.process_package_element)
            errata = list(errata)

        self.assertEqual(len(errata), 1)
        erratum = errata[0]
        self.assertTrue(isinstance(erratum, models.Errata))
        self.assertEqual(erratum.metadata.get('rights'), 'Copyright 2010 Red Hat Inc')
        self.assertTrue(erratum.metadata.get('summary') is not None)
        self.assertEqual(erratum.id, 'RHBA-2010:0836')
        self.assertEqual(erratum.metadata.get('type'), 'bugfix')
        self.assertEqual(erratum.metadata.get('updated'), '2010-11-10 00:00:00')
        self.assertEqual(erratum.metadata.get('reboot_suggested'), False)
        self.assertEqual(erratum.metadata.get('severity'), '')

        rpms = erratum.rpm_search_dicts
        self.assertEqual(len(rpms), 4)
        for rpm in rpms:
            # make sure all of the correct keys are present
            model = models.RPM.from_package_info(rpm)
            self.assertEqual(model.checksumtype, 'sha256')
            self.assertTrue(len(model.checksum) > 0)
            self.assertTrue(model.name.startswith('NetworkManager'))
            self.assertEqual(model.version, '0.8.1')
            self.assertEqual(model.release, '5.el6_0.1')
