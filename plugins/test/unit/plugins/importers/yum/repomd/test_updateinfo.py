# -*- coding: utf-8 -*-

import os
import unittest

from StringIO import StringIO

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

    def test_multiple_pkglist_multiple_collections(self):
        """
        Test that multiple pkglist and collections in erratum are imported correctly
        """
        erratum_xml = '<updates>' \
                      '  <update from="errata@redhat.com" status="stable" type="security"' \
                      '          version="1">' \
                      '    <id>RHEA-2012:0055</id>' \
                      '    <title>Sea_Erratum</title>' \
                      '    <release>1</release>' \
                      '    <issued date="2012-01-27 16:08:06"/>' \
                      '    <updated date="2012-01-27 16:08:06"/>' \
                      '    <description>Sea_Erratum</description>' \
                      '    <pkglist>' \
                      '      <collection short="">' \
                      '        <name>1</name>' \
                      '        <package arch="noarch" epoch="0" name="shark" release="1"' \
                      '                 src="http://www.fedoraproject.org" version="0.1">' \
                      '          <filename>shark-0.1-1.noarch.rpm</filename>' \
                      '        </package>' \
                      '      </collection>' \
                      '      <collection short="">' \
                      '        <name>2</name>' \
                      '        <package arch="noarch" epoch="0" name="walrus" release="1"' \
                      '                 src="http://www.fedoraproject.org" version="5.21">' \
                      '          <filename>walrus-5.21-1.noarch.rpm</filename>' \
                      '        </package>' \
                      '      </collection>' \
                      '    </pkglist>' \
                      '    <pkglist>' \
                      '      <collection short="">' \
                      '        <name>2</name>' \
                      '        <package arch="noarch" epoch="0" name="penguin" release="1"' \
                      '                 src="http://www.fedoraproject.org" version="0.9.1">' \
                      '           <filename>penguin-0.9.1-1.noarch.rpm</filename>' \
                      '        </package>' \
                      '      </collection>' \
                      '    </pkglist>' \
                      '  </update>' \
                      '</updates>'

        f = StringIO(erratum_xml)
        errata = packages.package_list_generator(f,
                                                 updateinfo.PACKAGE_TAG,
                                                 updateinfo.process_package_element)
        errata = list(errata)
        self.assertEqual(len(errata), 1)
        erratum = errata[0]

        # all collections are in pkglist
        self.assertEqual(len(erratum.pkglist), 3)

        # each collection contains one package
        for collection in erratum.pkglist:
            self.assertEqual(len(collection['packages']), 1)

    def test_module_present(self):
        """
        Check that module is populated from the xml feed.
        """
        erratum_xml = '<updates>' \
                      '  <update from="errata@redhat.com" status="stable" type="security"' \
                      '          version="1">' \
                      '    <id>RHEA-2018:0042</id>' \
                      '    <title>Origami Wolf</title>' \
                      '    <release>1</release>' \
                      '    <issued date="2018-08-29 11:40:28"/>' \
                      '    <updated date="2012-08-29 11:40:28"/>' \
                      '    <description>...in a single module</description>' \
                      '    <pkglist>' \
                      '      <collection short="">' \
                      '        <name>1</name>' \
                      '        <module name="wolf" version="1535542828" stream="woods" '\
                      '                context="deadbeef" arch="noarch"/>' \
                      '        <package arch="noarch" epoch="0" name="wolf" release="1"' \
                      '                 src="http://www.fedoraproject.org" version="0.1">' \
                      '          <filename>shark-0.1-1.noarch.rpm</filename>' \
                      '        </package>' \
                      '      </collection>' \
                      '    </pkglist>' \
                      '  </update>' \
                      '</updates>'
        f = StringIO(erratum_xml)
        errata = packages.package_list_generator(f,
                                                 updateinfo.PACKAGE_TAG,
                                                 updateinfo.process_package_element)
        errata = list(errata)
        self.assertEqual(len(errata), 1)
        erratum = errata[0]
        self.assertEqual(len(erratum.pkglist), 1)
        collection = erratum.pkglist[0]
        self.assertIn('module', collection)
        module = collection['module']
        self.assertEqual('wolf', module['name'])
        self.assertEqual('1535542828', module['version'])
        self.assertEqual('woods', module['stream'])
        self.assertEqual('deadbeef', module['context'])
        self.assertEqual('noarch', module['arch'])
        self.assertEqual(len(collection['packages']), 1)

    def test_no_module(self):
        """
        Check collection doesn't contain a module if there's no module in the xml.
        """
        erratum_xml = '<updates>' \
                      '  <update from="errata@redhat.com" status="stable" type="security"' \
                      '          version="1">' \
                      '    <id>RHEA-2018:0042</id>' \
                      '    <title>Origami Wolf</title>' \
                      '    <release>1</release>' \
                      '    <issued date="2018-08-29 11:40:28"/>' \
                      '    <updated date="2012-08-29 11:40:28"/>' \
                      '    <description>...in a single module</description>' \
                      '    <pkglist>' \
                      '      <collection short="">' \
                      '        <name>1</name>' \
                      '        <package arch="noarch" epoch="0" name="wolf" release="1"' \
                      '                 src="http://www.fedoraproject.org" version="0.1">' \
                      '          <filename>shark-0.1-1.noarch.rpm</filename>' \
                      '        </package>' \
                      '      </collection>' \
                      '    </pkglist>' \
                      '  </update>' \
                      '</updates>'
        f = StringIO(erratum_xml)
        errata = packages.package_list_generator(f,
                                                 updateinfo.PACKAGE_TAG,
                                                 updateinfo.process_package_element)
        errata = list(errata)
        self.assertEqual(len(errata), 1)
        erratum = errata[0]
        self.assertEqual(len(erratum.pkglist), 1)
        collection = erratum.pkglist[0]
        self.assertNotIn('module', collection)
        self.assertEqual(len(collection['packages']), 1)

    def test_multiple_modules(self):
        """
        Check multiple module elements in a collection break the parsing
        """
        erratum_xml = '<updates>' \
                      '  <update from="errata@redhat.com" status="stable" type="security"' \
                      '          version="1">' \
                      '    <id>RHEA-2018:0042</id>' \
                      '    <title>Origami Wolf</title>' \
                      '    <release>1</release>' \
                      '    <issued date="2018-08-29 11:40:28"/>' \
                      '    <updated date="2012-08-29 11:40:28"/>' \
                      '    <description>...in a single module</description>' \
                      '    <pkglist>' \
                      '      <collection short="">' \
                      '        <module name="wolf" version="1535542828" stream="woods" ' \
                      '                context="deadbeef" arch="noarch" />' \
                      '        <name>1</name>' \
                      '        <package arch="noarch" epoch="0" name="wolf" release="1"' \
                      '                 src="http://www.fedoraproject.org" version="0.1">' \
                      '          <filename>shark-0.1-1.noarch.rpm</filename>' \
                      '        </package>' \
                      '        <module name="fox" version="1535542870" stream="woods"' \
                      '                context="deadbeef" arch="noarch" />' \
                      '      </collection>' \
                      '    </pkglist> '\
                      '  </update>' \
                      '</updates>'
        f = StringIO(erratum_xml)
        with self.assertRaises(ValueError) as ctx:
            list(packages.package_list_generator(
                f, updateinfo.PACKAGE_TAG, updateinfo.process_package_element))
        self.assertIn('Collection contains multiple module elements', str(ctx.exception))

    def test_mandatory_module_fields(self):
        """
        Check that missing mandatory fields breaks the parsing.
        """
        erratum_xml0 = '<updates>' \
                       '  <update from="errata@redhat.com" status="stable" type="security"' \
                       '          version="1">' \
                       '    <id>RHEA-2018:0042</id>' \
                       '    <title>Origami Wolf</title>' \
                       '    <release>1</release>' \
                       '    <issued date="2018-08-29 11:40:28"/>' \
                       '    <updated date="2012-08-29 11:40:28"/>' \
                       '    <description>...in a single module</description>' \
                       '    <pkglist>' \
                       '      <collection short="">' \
                       '        <name>1</name>'
        erratum_xml1 = '        <package arch="noarch" epoch="0" name="wolf" release="1"' \
                       '                 src="http://www.fedoraproject.org" version="0.1">' \
                       '          <filename>shark-0.1-1.noarch.rpm</filename>' \
                       '        </package>' \
                       '      </collection>' \
                       '    </pkglist>'\
                       '  </update>' \
                       '</updates>'
        module_data = {
            'name': 'wolf',
            'version': '1535542828',
            'stream': 'woods',
            'context': 'deadbeef',
            'arch': 'noarch',
        }
        fields = set(module_data.keys())
        # every time remove a mandatory module element attribute and assert such an erratum won't
        # parse
        for field in fields:
            module_data_copy = module_data.copy()
            del(module_data_copy[field])
            module_xml = '<module '
            for check_field in fields - set([field]):
                module_xml += '{}="{}" '.format(check_field, module_data_copy[check_field])
            module_xml += '/>'
            f = StringIO('{}\n{}\n{}'.format(erratum_xml0, module_xml, erratum_xml1))
            with self.assertRaises(KeyError) as ctx:
                # the returned parsing generator has to be exhausted to trigger the exception
                list(packages.package_list_generator(
                    f, updateinfo.PACKAGE_TAG, updateinfo.process_package_element
                ))
            self.assertIn(field, str(ctx.exception))
