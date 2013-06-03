# -*- coding: utf-8 -*-
# Copyright (c) 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

import copy
import json
import unittest

import mock
from pulp.server.db.migrate.models import _import_all_the_way

from pulp_rpm.common.models import RPM, SRPM

migration = _import_all_the_way('pulp_rpm.migrations.0010_new_importer')


class TestMigrateNewImporter(unittest.TestCase):
    def setUp(self):
        self.rpm_unit = copy.deepcopy(RPM_UNIT)
        self.srpm_unit = copy.deepcopy(SRPM_UNIT)

    @mock.patch.object(migration, '_migrate_collection')
    def test_types(self, mock_add):
        migration.migrate()
        self.assertEqual(mock_add.call_count, 2)
        mock_add.assert_any_call(RPM.TYPE)
        mock_add.assert_any_call(SRPM.TYPE)

    @mock.patch('pulp.plugins.types.database.type_units_collection')
    def test_adds_size(self, mock_collection):
        mock_collection.return_value.find.return_value = [self.rpm_unit]
        self.assertFalse('size' in self.rpm_unit)

        migration._migrate_collection(RPM.TYPE)
        result = mock_collection.return_value.save.call_args[0][0]

        self.assertTrue('size' in result)
        self.assertEqual(result['size'], 88136)

    @mock.patch('pulp.plugins.types.database.type_units_collection')
    def test_adds_sourcerpm(self, mock_collection):
        mock_collection.return_value.find.return_value = [self.rpm_unit]
        self.assertFalse('sourcerpm' in self.rpm_unit)

        migration._migrate_collection(RPM.TYPE)
        result = mock_collection.return_value.save.call_args[0][0]

        self.assertTrue('sourcerpm' in result)
        self.assertEqual(result['sourcerpm'], 'pulp-2.1.1-1.el6.src.rpm')

    @mock.patch('pulp.plugins.types.database.type_units_collection')
    def test_adds_summary(self, mock_collection):
        mock_collection.return_value.find.return_value = [self.rpm_unit]
        self.assertFalse('summary' in self.rpm_unit)

        migration._migrate_collection(RPM.TYPE)
        result = mock_collection.return_value.save.call_args[0][0]

        self.assertTrue('summary' in result)
        self.assertEqual(result['summary'], 'The Pulp agent')

    @mock.patch('pulp.plugins.types.database.type_units_collection')
    def test_removes_xml_namespace(self, mock_collection):
        mock_collection.return_value.find.return_value = [self.rpm_unit]

        migration._migrate_collection(RPM.TYPE)
        result = mock_collection.return_value.save.call_args[0][0]

        primary_xml = result['repodata']['primary']
        self.assertEqual(primary_xml.find('<rpm:'), -1)

    @mock.patch('pulp.plugins.types.database.type_units_collection')
    def test_reformats_provides(self, mock_collection):
        mock_collection.return_value.find.return_value = [self.rpm_unit]

        migration._migrate_collection(RPM.TYPE)
        result = mock_collection.return_value.save.call_args[0][0]

        provides = result['provides']
        found_pulp_agent = False
        self.assertTrue(len(provides) > 1)
        for entry in provides:
            self.assertTrue(isinstance(entry, dict))
            for name in ('name', 'flags', 'epoch', 'version', 'release'):
                self.assertTrue(name in entry)
            if entry['name'] == 'pulp-agent':
                found_pulp_agent = True
                self.assertEqual(entry['flags'], 'EQ')
                self.assertEqual(entry['epoch'], '0')
                self.assertEqual(entry['version'], '2.1.1')
                self.assertEqual(entry['release'], '1.el6')
        self.assertTrue(found_pulp_agent)

    @mock.patch('pulp.plugins.types.database.type_units_collection')
    def test_reformats_requires(self, mock_collection):
        mock_collection.return_value.find.return_value = [self.rpm_unit]

        migration._migrate_collection(RPM.TYPE)
        result = mock_collection.return_value.save.call_args[0][0]

        requires = result['requires']
        self.assertTrue(len(requires) > 1)
        for entry in requires:
            self.assertTrue(isinstance(entry, dict))
            for name in ('name', 'flags', 'epoch', 'version', 'release'):
                self.assertTrue(name in entry)

    @mock.patch('pulp.plugins.types.database.type_units_collection')
    def test_srpm_doesnt_have_sourcerpm_or_summary(self, mock_collection):
        self.assertTrue('sourcerpm' not in self.srpm_unit)
        self.assertTrue('summary' not in self.srpm_unit)
        mock_collection.return_value.find.return_value = [self.srpm_unit]

        migration._migrate_collection(SRPM.TYPE)
        result = mock_collection.return_value.save.call_args[0][0]
        self.assertTrue('sourcerpm' not in result)
        self.assertTrue('summary' not in result)


RPM_UNIT = json.loads("""
{
    "_content_type_id": "rpm",
    "_id": "a7c1e6cf-55d9-4c96-b96b-0806b8d06cea",
    "_ns": "units_rpm",
    "_storage_path": "/var/lib/pulp/content/rpm/.//pulp-agent/2.1.1/1.el6/noarch/708261189d2dfdb40144f607f6a36430c6b246fb81994f5a1dfd4302a2b18c24/pulp-agent-2.1.1-1.el6.noarch.rpm",
    "arch": "noarch",
    "buildhost": "rhel6-builder",
    "changelog": [
        [
            1367928000,
            "Jeff Ortel <jortel@redhat.com> 2.1.1-1",
            "-"
        ],
        [
            1367928000,
            "Jeff Ortel <jortel@redhat.com> 2.1.1-0.10.beta",
            "-"
        ],
        [
            1367323200,
            "Jeff Ortel <jortel@redhat.com> 2.1.1-0.9.beta",
            "- 957890 - removing duplicate units in case when consumer is bound to copies of\\n  same repo (skarmark@redhat.com)\\n- 957890 - fixed duplicate unit listing in the applicability report and\\n  performance improvement fix to avoid loading unnecessary units\\n  (skarmark@redhat.com)"
        ],
        [
            1366977600,
            "Jeff Ortel <jortel@redhat.com> 2.1.1-0.8.beta",
            "- 954038 - updating applicability api to send unit ids instead of translated\\n  plugin unit objects to profilers and fixing a couple of performance issues\\n  (skarmark@redhat.com)"
        ],
        [
            1366804800,
            "Jeff Ortel <jortel@redhat.com> 2.1.1-0.7.beta",
            "-"
        ],
        [
            1366804800,
            "Jeff Ortel <jortel@redhat.com> 2.1.1-0.6.beta",
            "-"
        ],
        [
            1366372800,
            "Jeff Ortel <jortel@redhat.com> 2.1.1-0.5.beta",
            "- 953665 - added ability for copy commands to specify the fields of their units\\n  that should be fetched, so as to avoid loading the entirety of every unit in\\n  the source repository into RAM. Also added the ability to provide a custom\\n  \\"override_config\\" based on CLI options. (mhrivnak@redhat.com)"
        ],
        [
            1365768000,
            "Jeff Ortel <jortel@redhat.com> 2.1.1-0.4.beta",
            "-"
        ],
        [
            1365768000,
            "Jeff Ortel <jortel@redhat.com> 2.1.1-0.3.beta",
            "-"
        ],
        [
            1365768000,
            "Jeff Ortel <jortel@redhat.com> 2.1.1-0.2.beta",
            "-"
        ]
    ],
    "checksum": "708261189d2dfdb40144f607f6a36430c6b246fb81994f5a1dfd4302a2b18c24",
    "checksumtype": "sha256",
    "description": "The pulp agent, used to provide remote command & control and\\nscheduled actions such as reporting installed content profiles\\non a defined interval.",
    "epoch": "0",
    "filelist": [
        "/etc/pulp/agent/agent.conf",
        "/etc/gofer/plugins/pulpplugin.conf",
        "/usr/lib64/gofer/plugins/pulpplugin.py",
        "/usr/lib64/gofer/plugins/pulpplugin.pyc",
        "/usr/lib64/gofer/plugins/pulpplugin.pyo",
        "/etc/rc.d/init.d/pulp-agent"
    ],
    "filename": "pulp-agent-2.1.1-1.el6.noarch.rpm",
    "files": {
        "file": [
            "/etc/pulp/agent/agent.conf",
            "/etc/gofer/plugins/pulpplugin.conf",
            "/usr/lib64/gofer/plugins/pulpplugin.py",
            "/usr/lib64/gofer/plugins/pulpplugin.pyc",
            "/usr/lib64/gofer/plugins/pulpplugin.pyo",
            "/etc/rc.d/init.d/pulp-agent"
        ]
    },
    "license": "GPLv2",
    "name": "pulp-agent",
    "provides": [
        [
            "pulp-agent",
            "EQ",
            [
                "0",
                "2.1.1",
                "1.el6"
            ]
        ],
        [
            "config(pulp-agent)",
            "EQ",
            [
                "0",
                "2.1.1",
                "1.el6"
            ]
        ]
    ],
    "relativepath": "pulp-agent-2.1.1-1.el6.noarch.rpm",
    "release": "1.el6",
    "repodata": {
        "filelists": "<package pkgid=\\"708261189d2dfdb40144f607f6a36430c6b246fb81994f5a1dfd4302a2b18c24\\" name=\\"pulp-agent\\" arch=\\"noarch\\">    <version epoch=\\"0\\" ver=\\"2.1.1\\" rel=\\"1.el6\\"/>    <file>/etc/gofer/plugins/pulpplugin.conf</file>    <file>/etc/pulp/agent/agent.conf</file>    <file>/etc/rc.d/init.d/pulp-agent</file>    <file>/usr/lib64/gofer/plugins/pulpplugin.py</file>    <file>/usr/lib64/gofer/plugins/pulpplugin.pyc</file>    <file>/usr/lib64/gofer/plugins/pulpplugin.pyo</file></package>",
        "other": "<package pkgid=\\"708261189d2dfdb40144f607f6a36430c6b246fb81994f5a1dfd4302a2b18c24\\" name=\\"pulp-agent\\" arch=\\"noarch\\">    <version epoch=\\"0\\" ver=\\"2.1.1\\" rel=\\"1.el6\\"/><changelog author=\\"Jeff Ortel &lt;jortel@redhat.com&gt; 2.1.1-0.2.beta\\" date=\\"1365768000\\">-</changelog><changelog author=\\"Jeff Ortel &lt;jortel@redhat.com&gt; 2.1.1-0.3.beta\\" date=\\"1365768001\\">-</changelog><changelog author=\\"Jeff Ortel &lt;jortel@redhat.com&gt; 2.1.1-0.4.beta\\" date=\\"1365768002\\">-</changelog><changelog author=\\"Jeff Ortel &lt;jortel@redhat.com&gt; 2.1.1-0.5.beta\\" date=\\"1366372800\\">- 953665 - added ability for copy commands to specify the fields of their units  that should be fetched, so as to avoid loading the entirety of every unit in  the source repository into RAM. Also added the ability to provide a custom  \\"override_config\\" based on CLI options. (mhrivnak@redhat.com)</changelog><changelog author=\\"Jeff Ortel &lt;jortel@redhat.com&gt; 2.1.1-0.6.beta\\" date=\\"1366804800\\">-</changelog><changelog author=\\"Jeff Ortel &lt;jortel@redhat.com&gt; 2.1.1-0.7.beta\\" date=\\"1366804801\\">-</changelog><changelog author=\\"Jeff Ortel &lt;jortel@redhat.com&gt; 2.1.1-0.8.beta\\" date=\\"1366977600\\">- 954038 - updating applicability api to send unit ids instead of translated  plugin unit objects to profilers and fixing a couple of performance issues  (skarmark@redhat.com)</changelog><changelog author=\\"Jeff Ortel &lt;jortel@redhat.com&gt; 2.1.1-0.9.beta\\" date=\\"1367323200\\">- 957890 - removing duplicate units in case when consumer is bound to copies of  same repo (skarmark@redhat.com)- 957890 - fixed duplicate unit listing in the applicability report and  performance improvement fix to avoid loading unnecessary units  (skarmark@redhat.com)</changelog><changelog author=\\"Jeff Ortel &lt;jortel@redhat.com&gt; 2.1.1-0.10.beta\\" date=\\"1367928000\\">-</changelog><changelog author=\\"Jeff Ortel &lt;jortel@redhat.com&gt; 2.1.1-1\\" date=\\"1367928001\\">-</changelog></package>",
        "primary": "<package type=\\"rpm\\">  <name>pulp-agent</name>  <arch>noarch</arch>  <version epoch=\\"0\\" ver=\\"2.1.1\\" rel=\\"1.el6\\"/>  <checksum type=\\"sha256\\" pkgid=\\"YES\\">708261189d2dfdb40144f607f6a36430c6b246fb81994f5a1dfd4302a2b18c24</checksum>  <summary>The Pulp agent</summary>  <description>The pulp agent, used to provide remote command &amp; control andscheduled actions such as reporting installed content profileson a defined interval.</description>  <packager></packager>  <url>https://fedorahosted.org/pulp/</url>  <time file=\\"1367962980\\" build=\\"1367962910\\"/>  <size package=\\"88136\\" installed=\\"25944\\" archive=\\"26984\\"/><location href=\\"pulp-agent-2.1.1-1.el6.noarch.rpm\\"/>  <format>    <rpm:license>GPLv2</rpm:license>    <rpm:vendor/>    <rpm:group>Development/Languages</rpm:group>    <rpm:buildhost>rhel6-builder</rpm:buildhost>    <rpm:sourcerpm>pulp-2.1.1-1.el6.src.rpm</rpm:sourcerpm>    <rpm:header-range start=\\"280\\" end=\\"81648\\"/>    <rpm:provides>      <rpm:entry name=\\"config(pulp-agent)\\" flags=\\"EQ\\" epoch=\\"0\\" ver=\\"2.1.1\\" rel=\\"1.el6\\"/>      <rpm:entry name=\\"pulp-agent\\" flags=\\"EQ\\" epoch=\\"0\\" ver=\\"2.1.1\\" rel=\\"1.el6\\"/>    </rpm:provides>    <rpm:requires>      <rpm:entry name=\\"gofer\\" flags=\\"GE\\" epoch=\\"0\\" ver=\\"0.74\\"/>      <rpm:entry name=\\"pulp-consumer-client\\" flags=\\"EQ\\" epoch=\\"0\\" ver=\\"2.1.1\\"/>      <rpm:entry name=\\"python-pulp-agent-lib\\" flags=\\"EQ\\" epoch=\\"0\\" ver=\\"2.1.1\\"/>      <rpm:entry name=\\"python-pulp-bindings\\" flags=\\"EQ\\" epoch=\\"0\\" ver=\\"2.1.1\\"/>    </rpm:requires>    <file>/etc/gofer/plugins/pulpplugin.conf</file>    <file>/etc/pulp/agent/agent.conf</file>    <file>/etc/rc.d/init.d/pulp-agent</file>  </format></package>"
    },
    "requires": [
        [
            "python-pulp-bindings",
            "EQ",
            [
                "0",
                "2.1.1",
                null
            ]
        ],
        [
            "python-pulp-agent-lib",
            "EQ",
            [
                "0",
                "2.1.1",
                null
            ]
        ],
        [
            "pulp-consumer-client",
            "EQ",
            [
                "0",
                "2.1.1",
                null
            ]
        ],
        [
            "gofer",
            "GE",
            [
                "0",
                "0.74",
                null
            ]
        ]
    ],
    "vendor": "",
    "version": "2.1.1"
}
""")


SRPM_UNIT = json.loads("""
{
    "_content_type_id": "srpm",
    "_id": "b0160031-f57b-433a-9c66-b0a9df323c00",
    "_ns": "units_srpm",
    "_storage_path": "/var/lib/pulp/content/srpm/.//python-billiard/0.3.1/3.el6/src/5ac000c26637345e2ab013a978ff43cdcf10b76e64b2f221e9e6c195881b1301/python-billiard-0.3.1-3.el6.src.rpm",
    "arch": "src",
    "buildhost": "ppc05.phx2.fedoraproject.org",
    "changelog": [
        [
            1297166400,
            "Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.3.1-3",
            "- Rebuilt for https://fedoraproject.org/wiki/Fedora_15_Mass_Rebuild"
        ],
        [
            1281787200,
            "Fabian Affolter <fabian@bernewireless.net> - 0.3.1-2",
            "- TODO removed"
        ],
        [
            1278158400,
            "Fabian Affolter <fabian@bernewireless.net> - 0.3.1-1",
            "- Initial package"
        ]
    ],
    "checksum": "5ac000c26637345e2ab013a978ff43cdcf10b76e64b2f221e9e6c195881b1301",
    "checksumtype": "sha256",
    "description": "This package contains extensions to the multiprocessing Pool.",
    "epoch": "0",
    "filelist": [
        "./billiard-0.3.1.tar.gz",
        "./python-billiard.spec"
    ],
    "filename": "python-billiard-0.3.1-3.el6.src.rpm",
    "files": {
        "file": [
            "./billiard-0.3.1.tar.gz",
            "./python-billiard.spec"
        ]
    },
    "license": "BSD",
    "name": "python-billiard",
    "provides": [],
    "relativepath": "python-billiard-0.3.1-3.el6.src.rpm",
    "release": "3.el6",
    "repodata": {
        "filelists": "<package pkgid=\\"5ac000c26637345e2ab013a978ff43cdcf10b76e64b2f221e9e6c195881b1301\\" name=\\"python-billiard\\" arch=\\"src\\">    <version epoch=\\"0\\" ver=\\"0.3.1\\" rel=\\"3.el6\\"/>    <file>./billiard-0.3.1.tar.gz</file>    <file>./python-billiard.spec</file></package>",
        "other": "<package pkgid=\\"5ac000c26637345e2ab013a978ff43cdcf10b76e64b2f221e9e6c195881b1301\\" name=\\"python-billiard\\" arch=\\"src\\">    <version epoch=\\"0\\" ver=\\"0.3.1\\" rel=\\"3.el6\\"/><changelog author=\\"Fabian Affolter &lt;fabian@bernewireless.net&gt; - 0.3.1-1\\" date=\\"1278158400\\">- Initial package</changelog><changelog author=\\"Fabian Affolter &lt;fabian@bernewireless.net&gt; - 0.3.1-2\\" date=\\"1281787200\\">- TODO removed</changelog><changelog author=\\"Fedora Release Engineering &lt;rel-eng@lists.fedoraproject.org&gt; - 0.3.1-3\\" date=\\"1297166400\\">- Rebuilt for https://fedoraproject.org/wiki/Fedora_15_Mass_Rebuild</changelog></package>",
        "primary": "<package type=\\"rpm\\">  <name>python-billiard</name>  <arch>src</arch>  <version epoch=\\"0\\" ver=\\"0.3.1\\" rel=\\"3.el6\\"/>  <checksum type=\\"sha256\\" pkgid=\\"YES\\">5ac000c26637345e2ab013a978ff43cdcf10b76e64b2f221e9e6c195881b1301</checksum>  <summary>Multiprocessing Pool Extensions</summary>  <description>This package contains extensions to the multiprocessing Pool.</description>  <packager>Fedora Project</packager>  <url>http://pypi.python.org/pypi/billiard</url>  <time file=\\"1310585570\\" build=\\"1310515073\\"/>  <size package=\\"39544\\" installed=\\"36696\\" archive=\\"37088\\"/><location href=\\"python-billiard-0.3.1-3.el6.src.rpm\\"/>  <format>    <rpm:license>BSD</rpm:license>    <rpm:vendor>Fedora Project</rpm:vendor>    <rpm:group>Development/Languages</rpm:group>    <rpm:buildhost>ppc05.phx2.fedoraproject.org</rpm:buildhost>    <rpm:sourcerpm/>    <rpm:header-range start=\\"1384\\" end=\\"3252\\"/>    <rpm:requires>      <rpm:entry name=\\"python-devel\\"/>      <rpm:entry name=\\"python-setuptools\\"/>    </rpm:requires>  </format></package>"
    },
    "requires": [
        [
            "python-setuptools",
            null,
            [
                null,
                null,
                null
            ]
        ],
        [
            "python-devel",
            null,
            [
                null,
                null,
                null
            ]
        ]
    ],
    "vendor": "Fedora Project",
    "version": "0.3.1"
}
""")
