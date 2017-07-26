import mock

from pulp.common.compat import unittest
from pulp.server.db.migrate.models import _import_all_the_way

PATH_TO_MODULE = 'pulp_rpm.plugins.migrations.0041_metadata_rpm_srpm_upload_fix'

migration = _import_all_the_way(PATH_TO_MODULE)

PRIMARY = '''
<package type="rpm">
  <name>mouse</name>
  <arch>noarch</arch>
  <version epoch="0" rel="1" ver="0.1.12" />
  <checksum pkgid="YES"
    type="sha256">f4200643b0845fdc55ee002c92c0404a9f3a2a49f596c78b40ab56749de226ce</checksum>
  <summary>A dummy package of mouse</summary>
  <description>A dummy package of mouse</description>
  <packager />
  <url>http://tstrachota.fedorapeople.org</url>
  <time build="1331831376" file="1463813415" />
  <size archive="296" installed="42" package="2476" />
  <location href="foo-bar.rpm"/>
  <format>
    <rpm:license>GPLv2</rpm:license>
    <rpm:vendor />
    <rpm:group>Internet/Applications</rpm:group>
    <rpm:buildhost>smqe-ws15</rpm:buildhost>
    <rpm:sourcerpm>mouse-0.1.12-1.src.rpm</rpm:sourcerpm>
    <rpm:header-range end="2325" start="872" />
    <rpm:provides>
      <rpm:entry epoch="0" flags="EQ" name="mouse" rel="1" ver="0.1.12" />
    </rpm:provides>
    <rpm:requires>
      <rpm:entry name="dolphin" />
      <rpm:entry name="zebra" />
    </rpm:requires>
  </format>
</package>'''


@mock.patch('pulp.server.db.connection.get_database')
@mock.patch.object(migration, 'fix_metadata')
class TestMigrate(unittest.TestCase):
    def test_calls_fix(self, mock_fix, mock_get_db):
        mock_db = mock_get_db.return_value
        mock_unit = mock.MagicMock()
        mock_rpm_collection = mock_db['units_rpm']
        mock_rpm_collection.find.return_value = [mock_unit]
        mock_srpm_collection = mock_db['units_srpm']
        mock_srpm_collection.find.return_value = [mock_unit]

        migration.migrate()

        self.assertEqual(mock_fix.call_count, 2)
        mock_fix.assert_called_with(mock_rpm_collection, mock_unit)
        mock_fix.assert_called_with(mock_srpm_collection, mock_unit)


@mock.patch.object(migration, 'decompress_repodata')
@mock.patch.object(migration, 'fake_xml_element')
@mock.patch.object(migration, 'process_package_element')
class TestFixMetadata(unittest.TestCase):
    def test_fix_metadata(self, process_package_element_mock, fake_xml_element_mock,
                          decompress_repodata_mock):

        mock_primary_repodata = mock.MagicMock()

        unit = {
            '_id': '123',
            'repodata': {
                'primary': mock_primary_repodata
            }
        }
        mock_collection = mock.MagicMock()

        migration.fix_metadata(mock_collection, unit)

        decompress_repodata_mock.assert_called_once_with(mock_primary_repodata)
        fake_xml_element_mock.assert_called_once_with(decompress_repodata_mock.return_value)
        fake_xml_element_mock.return_value.find.assert_called_once_with(migration.PACKAGE_TAG)
        process_package_element_mock.assert_called_once_with(
            unit, fake_xml_element_mock.return_value.find.return_value)
        mock_collection.update_one.assert_called_once_with(
            {'_id': '123'}, {'$set': process_package_element_mock.return_value})


class TestFakeElemt(unittest.TestCase):
    def test_fake_element(self):
        input_ = """<test><rpm:test>a test</rpm:test></test>"""
        expected_output = ('<faketag xmlns="http://linux.duke.edu/metadata/common" '
                           'xmlns:rpm="http://linux.duke.edu/metadata/rpm"><test>'
                           '<rpm:test>a test</rpm:test></test></faketag>')
        self.assertEqual(migration.ET.tostring(migration.fake_xml_element(input_)), expected_output)


@mock.patch.object(migration, '_process_format_element')
class ProcessPackageElement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.element = migration.fake_xml_element(PRIMARY).find(migration.PACKAGE_TAG)

    def test_process_package_element_no_changes(self, process_format_mock):
        unit = {
            "time": None,
            "build_time": None,
            "size": None,
            "description": None,
        }

        delta = migration.process_package_element(unit, self.element)
        process_format_mock.assert_called_once_with(unit, self.element.find(migration.FORMAT_TAG))
        self.assertEqual(delta, {"summary": "A dummy package of mouse"})

    def test_process_package_element_empty_unit(self, process_format_mock):
        expected_delta = {
            "time": 1463813415,
            "build_time": 1331831376,
            "size": 2476,
            "description": "A dummy package of mouse",
            "summary": "A dummy package of mouse"
        }

        delta = migration.process_package_element({}, self.element)
        process_format_mock.assert_called_once_with({}, self.element.find(migration.FORMAT_TAG))
        self.assertEqual(delta, expected_delta)


class ProcessFormatElement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.element = migration.fake_xml_element(PRIMARY).find(
            migration.PACKAGE_TAG).find(migration.FORMAT_TAG)

    def test_process_format_element_no_changes(self):
        unit = {
            "license": None,
            "header_range": {
                "start": None,
                "end": None
            },
            "buildhost": None,
            "sourcerpm": None
        }
        delta = migration._process_format_element(unit, self.element)
        self.assertEqual(delta, {"group": "Internet/Applications"})

    def test_process_format_element_empty_unit(self):
        expected_delta = {
            "license": "GPLv2",
            "header_range": {
                "start": 872,
                "end": 2325,
            },
            "buildhost": "smqe-ws15",
            "sourcerpm": "mouse-0.1.12-1.src.rpm",
            "group": "Internet/Applications"
        }
        delta = migration._process_format_element({}, self.element)
        self.assertEqual(delta, expected_delta)
