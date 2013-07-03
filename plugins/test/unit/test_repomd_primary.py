# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the License
# (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied, including the
# implied warranties of MERCHANTABILITY, NON-INFRINGEMENT, or FITNESS FOR A
# PARTICULAR PURPOSE.
# You should have received a copy of GPLv2 along with this software; if not,
# see http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt

from cStringIO import StringIO
import unittest

from pulp_rpm.common import models
from pulp_rpm.plugins.importers.yum.repomd import primary, packages


class TestProcessSRPMElement(unittest.TestCase):
    def test_fedora18_real_data(self):
        rpms = packages.package_list_generator(StringIO(F18_SOURCE_XML),
                                                 primary.PACKAGE_TAG,
                                                 primary.process_package_element)
        rpms = list(rpms)

        self.assertEqual(len(rpms), 1)
        model = rpms[0]
        self.assertTrue(isinstance(model, models.SRPM))
        self.assertEqual(model.name, 'openhpi-subagent')
        self.assertEqual(model.epoch, '0')
        self.assertEqual(model.version, '2.3.4')
        self.assertEqual(model.release, '20.fc18')
        self.assertEqual(model.arch, 'src')
        self.assertEqual(model.checksum, '2d46d2c03e36583370d203e7ae63b00cfcd739421b58f8f00a89c56ac74654fa')
        self.assertEqual(model.checksumtype, 'sha256')


class TestProcessRPMElement(unittest.TestCase):
    def test_fedora18_real_data(self):
        rpms = packages.package_list_generator(StringIO(F18_XML),
                                               primary.PACKAGE_TAG,
                                               primary.process_package_element)
        rpms = list(rpms)

        self.assertEqual(len(rpms), 1)
        model = rpms[0]
        self.assertTrue(isinstance(model, models.RPM))
        self.assertEqual(model.name, 'opensm-libs')
        self.assertEqual(model.epoch, '0')
        self.assertEqual(model.version, '3.3.15')
        self.assertEqual(model.release, '3.fc18')
        self.assertEqual(model.arch, 'x86_64')
        self.assertEqual(model.checksum, 'c2c85a567d1b92dd6131bd326611b162ed485f6f97583e46459b430006908d66')
        self.assertEqual(model.checksumtype, 'sha256')


F18_SOURCE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<metadata xmlns="http://linux.duke.edu/metadata/common" xmlns:rpm="http://linux.duke.edu/metadata/rpm" packages="1">
<package type="rpm">
  <name>openhpi-subagent</name>
  <arch>src</arch>
  <version epoch="0" ver="2.3.4" rel="20.fc18"/>
  <checksum type="sha256" pkgid="YES">2d46d2c03e36583370d203e7ae63b00cfcd739421b58f8f00a89c56ac74654fa</checksum>
  <summary>NetSNMP subagent for OpenHPI</summary>
  <description>The openhpi-subagent package contains the Service Availability Forum's
Hardware Platform Interface SNMP sub-agent.</description>
  <packager>Fedora Project</packager>
  <url>http://www.openhpi.org</url>
  <time file="1344659367" build="1342841542"/>
  <size package="869418" installed="898608" archive="899592"/>
<location href="o/openhpi-subagent-2.3.4-20.fc18.src.rpm"/>
  <format>
    <rpm:license>BSD</rpm:license>
    <rpm:vendor>Fedora Project</rpm:vendor>
    <rpm:group>System Environment/Base</rpm:group>
    <rpm:buildhost>buildvm-02.phx2.fedoraproject.org</rpm:buildhost>
    <rpm:sourcerpm/>
    <rpm:header-range start="1384" end="5833"/>
    <rpm:requires>
      <rpm:entry name="docbook-utils"/>
      <rpm:entry name="net-snmp-devel"/>
      <rpm:entry name="openhpi-devel"/>
      <rpm:entry name="openssl-devel"/>
      <rpm:entry name="systemd-units"/>
    </rpm:requires>
  </format>
</package>
</metadata>
"""


F18_XML = """<?xml version="1.0" encoding="UTF-8"?>
<metadata xmlns="http://linux.duke.edu/metadata/common" xmlns:rpm="http://linux.duke.edu/metadata/rpm" packages="1">
<package type="rpm">
  <name>opensm-libs</name>
  <arch>x86_64</arch>
  <version epoch="0" ver="3.3.15" rel="3.fc18"/>
  <checksum type="sha256" pkgid="YES">c2c85a567d1b92dd6131bd326611b162ed485f6f97583e46459b430006908d66</checksum>
  <summary>Libraries used by opensm and included utilities</summary>
  <description>Shared libraries for Infiniband user space access</description>
  <packager>Fedora Project</packager>
  <url>http://www.openfabrics.org/</url>
  <time file="1354738068" build="1354735351"/>
  <size package="62796" installed="176600" archive="177640"/>
<location href="Packages/o/opensm-libs-3.3.15-3.fc18.x86_64.rpm"/>
  <format>
    <rpm:license>GPLv2 or BSD</rpm:license>
    <rpm:vendor>Fedora Project</rpm:vendor>
    <rpm:group>System Environment/Libraries</rpm:group>
    <rpm:buildhost>buildvm-21.phx2.fedoraproject.org</rpm:buildhost>
    <rpm:sourcerpm>opensm-3.3.15-3.fc18.src.rpm</rpm:sourcerpm>
    <rpm:header-range start="1384" end="8104"/>
    <rpm:provides>
      <rpm:entry name="libopensm.so.5()(64bit)"/>
      <rpm:entry name="libopensm.so.5(OPENSM_1.5)(64bit)"/>
      <rpm:entry name="libosmcomp.so.3()(64bit)"/>
      <rpm:entry name="libosmcomp.so.3(OSMCOMP_2.3)(64bit)"/>
      <rpm:entry name="libosmvendor.so.3()(64bit)"/>
      <rpm:entry name="libosmvendor.so.3(OSMVENDOR_2.0)(64bit)"/>
      <rpm:entry name="opensm-libs" flags="EQ" epoch="0" ver="3.3.15" rel="3.fc18"/>
      <rpm:entry name="opensm-libs(x86-64)" flags="EQ" epoch="0" ver="3.3.15" rel="3.fc18"/>
    </rpm:provides>
    <rpm:requires>
      <rpm:entry name="/sbin/ldconfig"/>
      <rpm:entry name="/sbin/ldconfig" pre="1"/>
      <rpm:entry name="libc.so.6(GLIBC_2.14)(64bit)"/>
      <rpm:entry name="libdl.so.2()(64bit)"/>
      <rpm:entry name="libgcc_s.so.1()(64bit)"/>
      <rpm:entry name="libgcc_s.so.1(GCC_3.0)(64bit)"/>
      <rpm:entry name="libgcc_s.so.1(GCC_3.3.1)(64bit)"/>
      <rpm:entry name="libibumad.so.3()(64bit)"/>
      <rpm:entry name="libibumad.so.3(IBUMAD_1.0)(64bit)"/>
      <rpm:entry name="libpthread.so.0()(64bit)"/>
      <rpm:entry name="libpthread.so.0(GLIBC_2.2.5)(64bit)"/>
      <rpm:entry name="libpthread.so.0(GLIBC_2.3.2)(64bit)"/>
      <rpm:entry name="rtld(GNU_HASH)"/>
    </rpm:requires>
  </format>
</package>
</metadata>
"""