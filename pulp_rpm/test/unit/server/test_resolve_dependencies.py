#!/usr/bin/python
#
# Copyright (c) 2012 Red Hat, Inc.
#
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

import mock
import os
import shutil
import sys
import tempfile
import time
import unittest
import itertools

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)) + "/../../../plugins/importers/")
import importer_mocks
from yum_importer.importer import YumImporter
from pulp_rpm.yum_plugin import util
from pulp.plugins.model import Repository, Unit
from yum_importer.importer_rpm import RPM_TYPE_ID
import rpm_support_base

class TestResolveDeps(rpm_support_base.PulpRPMTests):

    def setUp(self):
        super(TestResolveDeps, self).setUp()
        self.temp_dir = tempfile.mkdtemp()
        self.working_dir = os.path.join(self.temp_dir, "working")
        self.pkg_dir = os.path.join(self.temp_dir, "packages")
        self.data_dir = os.path.abspath(os.path.join(os.path.abspath(os.path.dirname(__file__)), "../data"))

    def tearDown(self):
        super(TestResolveDeps, self).tearDown()
        self.clean()

    def clean(self):
        shutil.rmtree(self.temp_dir)
        # clean up dir created by yum's repostorage
        if os.path.exists("./test_resolve_deps"):
            shutil.rmtree("test_resolve_deps")
        if os.path.exists("/tmp/test_resolve_deps"):
            shutil.rmtree("/tmp/test_resolve_deps")

    def test_resolve_deps(self):
        repo = mock.Mock(spec=Repository)
        repo.working_dir = "/tmp/test_resolve_deps"
        repo.id = "test_resolve_deps"

        unit_key_a = {'id' : '','name' :'pulp-server', 'version' :'0.0.309', 'release' : '1.fc17', 'epoch':'0', 'arch' : 'noarch', 'checksumtype' : 'sha256',
                      'checksum': 'ee5afa0aaf8bd2130b7f4a9b35f4178336c72e95358dd33bda8acaa5f28ea6e9', 'type_id' : 'rpm'}

        metadata = {'repodata' : {"primary" : """<package type="rpm">
  <name>pulp-server</name>
  <arch>noarch</arch>
  <version epoch="0" ver="0.0.309" rel="1.fc17"/>
  <checksum type="sha256" pkgid="YES">ee5afa0aaf8bd2130b7f4a9b35f4178336c72e95358dd33bda8acaa5f28ea6e9</checksum>
  <summary>The pulp platform server</summary>
  <description>Pulp provides replication, access, and accounting for software repositories.</description>
  <packager></packager>
  <url>https://fedorahosted.org/pulp/</url>
  <time file="1341234352" build="1340999291"/>
  <size package="499257" installed="2333988" archive="2445208"/>
<location href="pulp-server-0.0.309-1.fc17.noarch.rpm"/>
  <format>
    <rpm:license>GPLv2</rpm:license>
    <rpm:vendor/>
    <rpm:group>Development/Languages</rpm:group>
    <rpm:buildhost>localhost</rpm:buildhost>
    <rpm:sourcerpm>pulp-0.0.309-1.fc17.src.rpm</rpm:sourcerpm>
    <rpm:header-range start="280" end="111621"/>
    <rpm:provides>
      <rpm:entry name="config(pulp-server)" flags="EQ" epoch="0" ver="0.0.309" rel="1.fc17"/>
      <rpm:entry name="pulp-server" flags="EQ" epoch="0" ver="0.0.309" rel="1.fc17"/>
    </rpm:provides>
    <rpm:requires>
      <rpm:entry name="/bin/bash"/>
      <rpm:entry name="/usr/bin/python"/>
      <rpm:entry name="acl"/>
      <rpm:entry name="crontabs"/>
      <rpm:entry name="genisoimage"/>
      <rpm:entry name="grinder" flags="GE" epoch="0" ver="0.1.3" rel="1"/>
      <rpm:entry name="httpd"/>
      <rpm:entry name="m2crypto" flags="GE" epoch="0" ver="0.21.1.pulp" rel="7"/>
      <rpm:entry name="mod_ssl"/>
      <rpm:entry name="mod_wsgi" flags="GE" epoch="0" ver="3.3" rel="3.pulp"/>
      <rpm:entry name="mongodb"/>
      <rpm:entry name="mongodb-server"/>
      <rpm:entry name="openssl"/>
      <rpm:entry name="pymongo" flags="GE" epoch="0" ver="1.9"/>
      <rpm:entry name="python(abi)" flags="EQ" epoch="0" ver="2.7"/>
      <rpm:entry name="python-BeautifulSoup"/>
      <rpm:entry name="python-gofer" flags="GE" epoch="0" ver="0.70"/>
      <rpm:entry name="python-httplib2"/>
      <rpm:entry name="python-isodate" flags="GE" epoch="0" ver="0.4.4" rel="3.pulp"/>
      <rpm:entry name="python-ldap"/>
      <rpm:entry name="python-oauth2" flags="GE" epoch="0" ver="1.5.170" rel="2.pulp"/>
      <rpm:entry name="python-pulp-common" flags="EQ" epoch="0" ver="0.0.309"/>
      <rpm:entry name="python-setuptools"/>
      <rpm:entry name="python-simplejson" flags="GE" epoch="0" ver="2.0.9"/>
      <rpm:entry name="python-webpy"/>
      <rpm:entry name="qpid-cpp-server"/>
    </rpm:requires>
    <rpm:obsoletes>
      <rpm:entry name="pulp"/>
    </rpm:obsoletes>
    <file>/etc/httpd/conf.d/pulp.conf</file>
    <file>/etc/pki/pulp/ca.crt</file>
    <file>/etc/pki/pulp/ca.key</file>
    <file>/etc/pulp/logging/basic.cfg</file>
    <file>/etc/pulp/logging/unit_tests.cfg</file>
    <file>/etc/pulp/server.conf</file>
    <file>/etc/rc.d/init.d/pulp-server</file>
    <file>/usr/bin/pulp-migrate</file>
    <file type="dir">/etc/pki/pulp</file>
    <file type="dir">/etc/pki/pulp/consumer</file>
    <file type="dir">/etc/pulp/logging</file>
  </format>
</package>"""}}
        unit_key_a_obj = Unit(RPM_TYPE_ID, unit_key_a, {}, '')
        unit_key_a_obj.metadata = metadata
        unit_key_b = {'id' : '', 'name' :'pulp-rpm-server', 'version' :'0.0.309', 'release' :'1.fc17', 'epoch':'0','arch' : 'noarch', 'checksumtype' :'sha256',
                      'checksum': '1e6c3a3bae26423fe49d26930b986e5f5ee25523c13f875dfcd4bf80f770bf56', 'type_id' : 'rpm', }
        metadata = {'repodata' : {"primary" : """<package type="rpm">
  <name>pulp-rpm-server</name>
  <arch>noarch</arch>
  <version epoch="0" ver="0.0.309" rel="1.fc17"/>
  <checksum type="sha256" pkgid="YES">1e6c3a3bae26423fe49d26930b986e5f5ee25523c13f875dfcd4bf80f770bf56</checksum>
  <summary>The Pulp (plus) RPM server metapackage</summary>
  <description>The Pulp (plus) RPM metapackage used to install packages needed
to provide the Pulp platform (plus) RPM support packages.</description>
  <packager></packager>
  <url>https://fedorahosted.org/pulp/</url>
  <time file="1341234359" build="1340999306"/>
  <size package="2482" installed="0" archive="124"/>
<location href="pulp-rpm-server-0.0.309-1.fc17.noarch.rpm"/>
  <format>
    <rpm:license>GPLv2</rpm:license>
    <rpm:vendor/>
    <rpm:group>Virtual groups/Pulp</rpm:group>
    <rpm:buildhost>localhost</rpm:buildhost>
    <rpm:sourcerpm>pulp-rpm-product-0.0.309-1.fc17.src.rpm</rpm:sourcerpm>
    <rpm:header-range start="280" end="2366"/>
    <rpm:provides>
      <rpm:entry name="pulp-rpm-server" flags="EQ" epoch="0" ver="0.0.309" rel="1.fc17"/>
    </rpm:provides>
    <rpm:requires>
      <rpm:entry name="pulp-rpm-plugins" flags="EQ" epoch="0" ver="0.0.309"/>
      <rpm:entry name="pulp-server" flags="EQ" epoch="0" ver="0.0.309"/>
    </rpm:requires>
  </format>
</package>"""}}
        unit_key_b_obj = Unit(RPM_TYPE_ID, unit_key_b, metadata, '')
        unit_key_b_obj.metadata = metadata
        existing_units = []
        for unit in [unit_key_a_obj, unit_key_b_obj]:
            existing_units.append(unit)
        conduit = importer_mocks.get_dependency_conduit(type_id=RPM_TYPE_ID, existing_units=existing_units, pkg_dir=self.pkg_dir)
        config = importer_mocks.get_basic_config()
        importer = YumImporter()
        units = [Unit(RPM_TYPE_ID, unit_key_b, {}, '')]
        result = importer.resolve_dependencies(repo, units, conduit, config)
        self.assertEqual(len(list(itertools.chain(*result['resolved'].values()))), 1)
        self.assertEqual(len(list(itertools.chain(*result['unresolved'].values()))), 0)
