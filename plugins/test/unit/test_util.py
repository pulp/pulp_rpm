import re
import unittest
from xml.etree import cElementTree as ET

from pulp_rpm.plugins.importers.yum import utils
from pulp_rpm.plugins.importers.yum.repomd import primary


class TestElementToRawXML(unittest.TestCase):
    def setUp(self):
        self.rpm_element = ET.fromstring(PRIMARY_XML)[0]
        self.other_element = ET.fromstring(OTHER_XML)[0]
        self.filelists_element = ET.fromstring(FILELIST_XML)[0]

    def test_rpm(self):
        namespaces = [
            utils.Namespace('rpm', primary.RPM_SPEC_URL),
        ]
        raw_xml = utils.element_to_raw_xml(self.rpm_element, namespaces, primary.COMMON_SPEC_URL)

        # make sure it stripped out any namespace declarations and root elements
        self.assertTrue(re.match(r'^<package +type="rpm">', raw_xml))
        # make sure there are no stray closing elements, like </metadata>
        self.assertTrue(raw_xml.rstrip().endswith('</package>'))
        # make sure it preserved the "rpm" prefix
        self.assertTrue(re.search(r'<rpm:license *>GPLv2</rpm:license>', raw_xml))
        # make sure it got the requires and provides entries
        self.assertTrue(raw_xml.find('dolphin') >= 0)
        self.assertTrue(raw_xml.find('penguin') >= 0)
        # these should all be stripped out
        self.assertTrue(raw_xml.find('xmlns') == -1)
        # had this problem on python 2.6 where it treated the default namespace
        # as a namespace with prefix ''
        self.assertTrue(raw_xml.find('<:') == -1)

        # try to re-parse the XML to make sure it's valid. fake tag is necessary
        # to declare the prefix "rpm"
        fake_xml = '<fake xmlns:rpm="http://pulpproject.org">%s</fake>' % raw_xml
        reparsed = ET.fromstring(fake_xml)

    def test_other(self):
        utils.strip_ns(self.other_element)
        raw_xml = utils.element_to_raw_xml(self.other_element)

        self.assertTrue(raw_xml.startswith('<package '))
        self.assertTrue(raw_xml.find('<version ') >= 0)
        self.assertEqual(raw_xml.count('<changelog '), 10)
        self.assertEqual(raw_xml.count('author="Doug Ledford'), 7)

        # re-parse just to make sure this is valid
        reparsed = ET.fromstring(raw_xml)

    def test_filelists(self):
        utils.strip_ns(self.filelists_element)
        raw_xml = utils.element_to_raw_xml(self.filelists_element)

        self.assertTrue(raw_xml.startswith('<package '))
        self.assertTrue(raw_xml.find('<version ') >= 0)
        self.assertTrue(raw_xml.find('name="opensm-libs"') >= 0)
        self.assertTrue(raw_xml.find('<file>/usr/lib64/libosmcomp.so.3</file>') >= 0)
        self.assertEqual(raw_xml.count('<file>'), 6)

        # re-parse just to make sure this is valid
        reparsed = ET.fromstring(raw_xml)


class TestRegisterNamespace(unittest.TestCase):
    DUMMY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<dummyroot xmlns:foo="http://pulpproject.org/foo">
<foo:dummyelement>hi</foo:dummyelement>
</dummyroot>
"""

    def test_register(self):
        utils.register_namespace('foo', 'http://pulpproject.org/foo')
        root = ET.fromstring(self.DUMMY_XML)

        # if the registration didn't work, the namespace "foo" will instead
        # show up as "ns0"
        self.assertTrue(ET.tostring(root).find('<foo:dummyelement') >= 0)
        self.assertEqual(ET.tostring(root).find('ns0'), -1)


class TestStripNS(unittest.TestCase):
    def setUp(self):
        self.element = ET.fromstring(PRIMARY_XML)[0]

    def test_strip_all(self):
        utils.strip_ns(self.element)

        self._check_all_elements(self.element)

    def test_strip_common_ns_only(self):
        utils.strip_ns(self.element, primary.COMMON_SPEC_URL)

        self.assertTrue(self._check_for_one_ns(self.element, primary.RPM_SPEC_URL))

    def _check_for_one_ns(self, element, uri):
        """
        check the element and all descendants to make sure the tag either has
        the allowed namespace or no namespace
        """
        if element.tag.startswith('{%s}' % uri):
            found = True
        else:
            found = False
            self.assertFalse(element.tag.startswith('{'))

        for child in element:
            found = found or self._check_for_one_ns(child, uri)

        return found

    def _check_all_elements(self, element):
        """
        check the element and all descendants to make sure their tags do not have
        any namespace
        """
        self.assertFalse(element.tag.startswith('{'))
        for child in element:
            self._check_all_elements(child)


PRIMARY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<metadata xmlns="http://linux.duke.edu/metadata/common" xmlns:rpm="http://linux.duke.edu/metadata/rpm" packages="32">
<package type="rpm">
  <name>penguin</name>
  <arch>noarch</arch>
  <version epoch="0" ver="0.9.1" rel="1"/>
  <checksum type="sha256" pkgid="YES">57d314cc6f5322484cdcd33f4173374de95c53034de5b1168b9291ca0ad06dec</checksum>
  <summary>A dummy package of penguin</summary>
  <description>A dummy package of penguin</description>
  <packager></packager>
  <url>http://tstrachota.fedorapeople.org</url>
  <time file="1331832459" build="1331831373"/>
  <size package="2464" installed="42" archive="296"/>
<location href="penguin-0.9.1-1.noarch.rpm"/>
  <format>
    <rpm:license>GPLv2</rpm:license>
    <rpm:vendor/>
    <rpm:group>Internet/Applications</rpm:group>
    <rpm:buildhost>smqe-ws15</rpm:buildhost>
    <rpm:sourcerpm>penguin-0.9.1-1.src.rpm</rpm:sourcerpm>
    <rpm:header-range start="872" end="2313"/>
    <rpm:provides>
      <rpm:entry name="penguin" flags="EQ" epoch="0" ver="0.9.1" rel="1"/>
    </rpm:provides>
    <rpm:requires>
      <rpm:entry name="dolphin"/>
    </rpm:requires>
  </format>
</package>
</metadata>
"""

# from Fedora 18
OTHER_XML = """<?xml version="1.0" encoding="UTF-8"?>
<otherdata xmlns="http://linux.duke.edu/metadata/other" packages="33868">
<package pkgid="c2c85a567d1b92dd6131bd326611b162ed485f6f97583e46459b430006908d66" name="opensm-libs" arch="x86_64">
    <version epoch="0" ver="3.3.15" rel="3.fc18"/>

<changelog author="Fedora Release Engineering &lt;rel-eng@lists.fedoraproject.org&gt; - 3.3.5-2" date="1297166400">- Rebuilt for https://fedoraproject.org/wiki/Fedora_15_Mass_Rebuild</changelog>
<changelog author="Doug Ledford &lt;dledford@redhat.com&gt; - 3.3.9-1" date="1311163200">- Update to latest upstream version
- Add /etc/sysconfig/opensm for use by opensm init script
- Enable the ability to start more than one instance of opensm for multiple
  fabric support
- Enable the ability to start opensm with a priority other than default for
  support of backup opensm instances</changelog>
<changelog author="Kalev Lember &lt;kalevlember@gmail.com&gt; - 3.3.9-2" date="1313409600">- Rebuilt for rpm bug #728707</changelog>
<changelog author="Doug Ledford &lt;dledford@redhat.com&gt; - 3.3.12-1" date="1325592000">- Update to latest upstream version</changelog>
<changelog author="Doug Ledford &lt;dledford@redhat.com&gt; - 3.3.13-1" date="1330430400">- Update to latest upstream version
- Fix a minor issue in init scripts that would cause systemd to try and
  start/stop things in the wrong order
- Add a patch to allow us to specify the subnet prefix on the command line</changelog>
<changelog author="Doug Ledford &lt;dledford@redhat.com&gt; - 3.3.13-2" date="1331640000">- Fix the config file comment in the opensm init script
- Resolves: bz802727</changelog>
<changelog author="Fedora Release Engineering &lt;rel-eng@lists.fedoraproject.org&gt; - 3.3.13-3" date="1342785600">- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild</changelog>
<changelog author="Doug Ledford &lt;dledford@redhat.com&gt; - 3.3.15-1" date="1354017600">- Update to latest upstream release
- Update to systemd startup</changelog>
<changelog author="Doug Ledford &lt;dledford@redhat.com&gt; - 3.3.15-2" date="1354708800">- More tweaks to systemd setup (proper scriptlets now)
- More tweaks to old sysv init script support (fix Requires)</changelog>
<changelog author="Doug Ledford &lt;dledford@redhat.com&gt; - 3.3.15-3" date="1354708801">- Fix startup on read only root
- Update default config file
- Resolves: bz817591</changelog>

</package>
</otherdata>
"""

# from Fedora 18
FILELIST_XML = """<?xml version="1.0" encoding="UTF-8"?>
<filelists xmlns="http://linux.duke.edu/metadata/filelists" packages="33868">
<package pkgid="c2c85a567d1b92dd6131bd326611b162ed485f6f97583e46459b430006908d66" name="opensm-libs" arch="x86_64">
    <version epoch="0" ver="3.3.15" rel="3.fc18"/>

    <file>/usr/lib64/libopensm.so.5</file>
    <file>/usr/lib64/libopensm.so.5.1.0</file>
    <file>/usr/lib64/libosmcomp.so.3</file>
    <file>/usr/lib64/libosmcomp.so.3.0.6</file>
    <file>/usr/lib64/libosmvendor.so.3</file>
    <file>/usr/lib64/libosmvendor.so.3.0.8</file>
</package>
</filelists>
"""
