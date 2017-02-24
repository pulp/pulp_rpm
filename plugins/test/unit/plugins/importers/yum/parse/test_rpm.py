from __future__ import absolute_import

import os
from gettext import gettext as _

import rpm as rpm_module

from mock import Mock, patch
from pulp.common.compat import unittest
from pulp.devel.unit import util
from pulp.server.exceptions import PulpCodedException
from pulp_rpm.plugins.importers.yum.parse import rpm

DATA_DIR = os.path.join(os.path.dirname(__file__), '../../../../../data')

MODULE = 'pulp_rpm.plugins.importers.yum.parse.rpm'


class TesGetPackageXml(unittest.TestCase):
    """
    tests for the get_package_xml method,  most
    of this methods functionality is tested indirectly
    by the upload tests.
    """

    PRIMARY = u"""
    <package type="rpm">
      <name>rabbit</name>
      <arch>noarch</arch>
      <version epoch="0" ver="5.0.3" rel="1.fc22"/>
      <checksum type="sha256" pkgid="YES">b88a43acd5c9239</checksum>
      <summary>rabbit IDE</summary>
      <description>The rabbit (professional) IDE.</description>
      <packager>Frosty \u2603\x9a</packager>
      <url>http://redhat.com</url>
      <time file="1452798172" build="1452797732"/>
      <size package="187399436" installed="187899535" archive="187899924"/>
      <location href="rabbit-5.0.3-1.fc22.noarch.rpm"/>
      <format>
        <rpm:license>GPLv2</rpm:license>
        <rpm:vendor/>
        <rpm:group>Development/Tools</rpm:group>
        <rpm:buildhost>localhost</rpm:buildhost>
        <rpm:sourcerpm>rabbit-5.0.3-1.fc22.src.rpm</rpm:sourcerpm>
        <rpm:header-range start="4392" end="6476"/>
        <rpm:provides>
          <rpm:entry name="rabbit" flags="EQ" epoch="0" ver="5.0.3" rel="1.fc22"/>
        </rpm:provides>
        <rpm:requires>
        </rpm:requires>
      </format>
    </package>
    """.encode('utf-8')

    @patch(MODULE + '.yumbased')
    @patch(MODULE + '.change_location_tag')
    def test_get_package_xml(self, change_location_tag, yumbased):
        package = Mock()
        package.xml_dump_primary_metadata.return_value = self.PRIMARY
        yumbased.CreateRepoPackage.return_value = package
        rel_path = 'a/b/c/d/rabbit.rpm'

        # test
        md = rpm.get_package_xml(rel_path)

        # validation
        change_location_tag.assert_called_once_with(
            self.PRIMARY.decode('utf-8', 'replace'),
            rel_path)
        self.assertEqual(md['primary'], change_location_tag.return_value)
        self.assertEqual(md['filelists'], package.xml_dump_filelists_metadata.return_value)
        self.assertEqual(md['other'], package.xml_dump_other_metadata.return_value)

    @patch(MODULE + '.yumbased')
    def test_get_package_xml_yum_exception(self, mock_yumbased):
        mock_yumbased.CreateRepoPackage.side_effect = Exception()
        result = rpm.get_package_xml("/bad/package/path")
        util.compare_dict(result, {})


class TestChangeLocationTag(unittest.TestCase):

    PRIMARY = u"""
    <package type="rpm">
      <name>rabbit</name>
      <arch>noarch</arch>
      <version epoch="0" ver="5.0.3" rel="1.fc22"/>
      <checksum type="sha256" pkgid="YES">b88a43acd5c9239</checksum>
      <summary>rabbit IDE</summary>
      <description>The rabbit (professional) IDE.</description>
      <packager>Roger Rabbit</packager>
      <url>http://redhat.com</url>
      <time file="1452798172" build="1452797732"/>
      <size package="187399436" installed="187899535" archive="187899924"/>
      <location href="rabbit-5.0.3-1.fc22.noarch.rpm"/>
      <format>
        <rpm:license>GPLv2</rpm:license>
        <rpm:vendor/>
        <rpm:group>Development/Tools</rpm:group>
        <rpm:buildhost>localhost</rpm:buildhost>
        <rpm:sourcerpm>rabbit-5.0.3-1.fc22.src.rpm</rpm:sourcerpm>
        <rpm:header-range start="4392" end="6476"/>
        <rpm:provides>
          <rpm:entry name="rabbit" flags="EQ" epoch="0" ver="5.0.3" rel="1.fc22"/>
        </rpm:provides>
        <rpm:requires>
        </rpm:requires>
      </format>
    </package>
    """.encode('utf-8')

    def test_relocation(self):
        rel_path = 'a/b/c/d/rabbit-5.0.3-1.fc22.noarch.rpm'
        relocated = rpm.change_location_tag(self.PRIMARY, rel_path)
        self.assertEqual(
            relocated,
            self.PRIMARY.replace(
                '<location href="rabbit-5.0.3-1.fc22.noarch.rpm"/>',
                '<location href="Packages/r/rabbit-5.0.3-1.fc22.noarch.rpm"/>'))


class PackageHeaders(unittest.TestCase):
    """
    tests for package headers and signature extraction
    """

    def test_package_signature_from_header(self):
        sample_rpm_filename = os.path.join(DATA_DIR, 'walrus-5.21-1.noarch.rpm')
        headers = rpm.package_headers(sample_rpm_filename)
        self.assertTrue(isinstance(headers, rpm_module.hdr))
        signing_key = rpm.package_signature(headers)
        self.assertEquals(signing_key, 'f78fb195')
        self.assertEquals(len(signing_key), 8)

    def test_invalid_package_headers(self):
        fake_rpm_file = os.path.join(DATA_DIR, 'fake.rpm')
        with self.assertRaises(rpm_module.error) as e:
            rpm.package_headers(fake_rpm_file)
        self.assertEquals(e.exception.message, 'error reading package header')


class SignatureEnabled(unittest.TestCase):
    """
    tests for signature policy state
    """

    def test_signature_check_enabled(self):
        config = {"require_signature": True, "allowed_keys": []}
        response = rpm.signature_enabled(config)
        self.assertTrue(response)

    def test_signature_check_disabled(self):
        config = {"require_signature": False, "allowed_keys": []}
        response = rpm.signature_enabled(config)
        self.assertFalse(response)


class FilterSignature(unittest.TestCase):
    """
    test for package signature filtering
    """

    def test_reject_unsigned_packages(self):
        unit = Mock()
        unit.signing_key = None
        config = {"require_signature": True}

        with self.assertRaises(PulpCodedException) as cm:
                rpm.filter_signature(unit, config)
                self.assertEqual(cm.exception.error_code.code, 'RPM1013')

    def test_invalid_package_signature(self):
        unit = Mock()
        unit.signing_key = '12345678'
        config = {"allowed_keys": ['87654321']}

        with self.assertRaises(PulpCodedException) as cm:
            rpm.filter_signature(unit, config)
            self.assertEqual(cm.exception.error_code.code, 'RPM1014')


class TestDeltaRPMpackageInfo(unittest.TestCase):
    """
    tests for DRPM package header extraction
    """

    def test_package_header_from_file(self):
        """Test if exporting is correct."""
        sample_drpm_filename = os.path.join(DATA_DIR,
                                            'yum-3.2.29-20.fc16_from_el6_3.4.3-8.fc16.noarch.drpm')
        headers = rpm.drpm_package_info(sample_drpm_filename)
        self.assertEquals(headers['old_nevr'], 'yum-3.2.29-20.fc16_from_el6')
        self.assertEquals(headers['nevr'], 'yum-3.4.3-8.fc16')
        self.assertEquals(headers['seq'], (
            '4d1beb61671e5cd33b731e1807e6bc78211141321242121222421'
            '2121242421212724212121212124242121212b427212121230cd2'
            '109d210ec210bc210ab210de110ae110fd110cd110ec1108c110d'
            'b110ab110fa110ca1109a110b9110a8110f710c710e6108610d51'
            '0a510f4109410d310a310f2109210e11'))


class TestNEVRA(unittest.TestCase):
    """Test  NEVRA parsing."""

    def test_correct_nevra_parsing(self):
        """Test parsing NEVRA."""
        excepted_nevra = rpm.nevr("yum-3.4.3-8.fc16") + ("x86_64",)
        self.assertEquals(rpm.nevra("yum-3.4.3-8.fc16.x86_64"), excepted_nevra)

    def test_nevra_to_nevr(self):
        """Test parsing NEVRA tuple to NEVR tuple."""
        nevra = rpm.nevra("yum-3.4.3-8.fc16.x86_64")
        nevr = rpm.nevr("yum-3.4.3-8.fc16")
        self.assertEquals(rpm.nevra_to_nevr(*nevra), nevr)

    def test_invalid_nevra(self):
        nevra = "jay-3-fc24"
        with self.assertRaises(ValueError) as e:
            rpm.nevra(nevra)
        self.assertEquals(e.exception.message,
                          _("failed to parse nevra '%s' not a valid nevra") % nevra)


class TestNEVR(unittest.TestCase):
    """Test NEVR"""

    def test_nevr_parsing_without_epoch(self):
        """Test NEVR parsing without epoch."""
        nevr = "jay-4.10-4.fc3"
        excepted_nevr = ("jay", 0, "4.10", "4.fc3")
        self.assertEquals(rpm.nevr(nevr), excepted_nevr)

    def test_nevr_parsing_with_epoch(self):
        """Test NEVR parsing with epoch."""
        nevr = "jay-3:3.10-4.fc3"
        excepted_nevr = ("jay", 3, "3.10", "4.fc3")
        self.assertEquals(rpm.nevr(nevr), excepted_nevr)

    def test_invalid_nevr_one_dash(self):
        """Test NEVR with just one '-'."""
        nevr = "jay3.10-4.fc3"
        with self.assertRaises(ValueError) as e:
            rpm.nevr(nevr)
        self.assertEquals(e.exception.message,
                          _("failed to parse nevr '%s' not a valid nevr") % nevr)

    def test_invalid_nevr_multiple_duble_dot(self):
        """Test NEVR with multiple duble dot."""
        nevr = "jay-6:6:6.10-4.fc3"
        with self.assertRaises(ValueError) as e:
            rpm.nevr(nevr)
        self.assertEquals(e.exception.message,
                          _("failed to parse nevr '%s' not a valid nevr") % nevr)

    def test_nerv_to_evr(self):
        """Test parsing NEVR tuple to EVR tuple."""
        nevr = rpm.nevr("yum-3.4.3-8.fc16")
        evr = nevr[1:]
        self.assertEquals(rpm.nevr_to_evr(*nevr), evr)


class TestEVR(unittest.TestCase):
    """Test EVR."""

    def test_evr_to_str_without_epoch(self):
        """Test converting EVR tuple to string without epoch."""
        evr = (0, "3.10", "4.fc3")
        self.assertEquals(rpm.evr_to_str(*evr), "3.10-4.fc3")

    def test_evr_with_epoch(self):
        """Test converting EVR tuple to string with epoch."""
        evr = (3, "3.10", "4.fc3")
        self.assertEquals(rpm.evr_to_str(*evr), "3:3.10-4.fc3")
