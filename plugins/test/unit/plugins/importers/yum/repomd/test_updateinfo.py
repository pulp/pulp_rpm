# -*- coding: utf-8 -*-

import os
import unittest

from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.importers.yum.repomd import packages, updateinfo


DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                        '..', '..', '..', '..', '..', 'data'))


class TestProcessErratumElement(unittest.TestCase):
    def test_rhel6_real_data(self):
        with open(os.path.join(DATA_DIR, 'RHBA-2010-0836.erratum.xml')) as f:
            errata = packages.package_list_generator(f,
                                                     updateinfo.PACKAGE_TAG,
                                                     updateinfo.process_package_element)
            errata = list(errata)

        self.assertEqual(len(errata), 1)
        erratum = errata[0]
        self.assertTrue(isinstance(erratum, models.Errata))
        self.assertEqual(erratum.rights, 'Copyright 2010 Red Hat Inc')
        description = """NetworkManager is a system network service that manages network devices and
connections, attempting to keep active network connectivity when available. It
manages Ethernet, wireless, mobile broadband (WWAN), and PPPoE devices, and
provides VPN integration with a variety of different VPN services.

This update fixes the following bug:

* Under certain circumstances, the "Enable Networking" and "Enable Wireless"
menu items in the panel applet may have been insensitive. This error no longer
occurs, and both options are now available as expected. (BZ#638598)

Also, this update adds the following enhancements:

* In enterprise wireless networks, the proactive key caching can now be used
along with the PEAP-GTC authentication mechanism.

* Punjabi translation of the network applet has been updated.

Users are advised to upgrade to these updated packages, which resolve this
issue, and add these enhancements.
"""
        self.assertEqual(erratum.description, description)
        self.assertTrue(erratum.summary is not None)
        self.assertEqual(erratum.errata_id, 'RHBA-2010:0836')
        self.assertEqual(erratum.type, 'bugfix')
        self.assertEqual(erratum.issued, '2010-11-10 00:00:00')
        self.assertEqual(erratum.updated, '2010-11-10 00:00:00')
        self.assertEqual(erratum.reboot_suggested, False)
        self.assertEqual(erratum.severity, '')

        rpms = erratum.rpm_search_dicts
        self.assertEqual(len(rpms), 4)
        for rpm in rpms:
            # make sure all of the correct keys are present
            model = models.RPM(**rpm)
            self.assertEqual(model.checksumtype, 'sha256')
            self.assertTrue(len(model.checksum) > 0)
            self.assertTrue(model.name.startswith('NetworkManager'))
            self.assertEqual(model.version, '0.8.1')
            self.assertEqual(model.release, '5.el6_0.1')

    def test_scientific_linux_real_data(self):
        with open(os.path.join(DATA_DIR, 'scientific_linux_erratum.xml')) as f:
            errata = packages.package_list_generator(f,
                                                     updateinfo.PACKAGE_TAG,
                                                     updateinfo.process_package_element)
            errata = list(errata)

        self.assertEqual(len(errata), 1)
        erratum = errata[0]
        self.assertTrue(isinstance(erratum, models.Errata))
        self.assertEqual(erratum.rights, '')
        self.assertEqual(erratum.description, '')
        self.assertTrue(erratum.summary is not None)
        self.assertEqual(erratum.errata_id, 'SLBA-2011:1512-2')
        self.assertEqual(erratum.type, 'bugfix')
        self.assertEqual(erratum.issued, '')
        self.assertEqual(erratum.updated, '')
        self.assertEqual(erratum.reboot_suggested, False)
        self.assertEqual(erratum.severity, '')

        rpms = erratum.rpm_search_dicts
        self.assertEqual(len(rpms), 14)
