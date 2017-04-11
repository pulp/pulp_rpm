import mock

from pulp.common.compat import unittest
from pulp.server.db.migrate.models import _import_all_the_way


PATH_TO_MODULE = 'pulp_rpm.plugins.migrations.0037_rpm_primary_repodata_new_location'
migration = _import_all_the_way(PATH_TO_MODULE)


@mock.patch('pulp.server.db.connection.get_database')
@mock.patch.object(migration, 'migrate_rpm_base')
class TestMigrate(unittest.TestCase):
    def test_calls_migrate(self, mock_migrate_rpm_base, mock_get_db):
        mock_db = mock_get_db.return_value
        mock_unit = mock.MagicMock()
        mock_rpm_collection = mock_db['units_rpm']
        mock_rpm_collection.find.return_value = [mock_unit]
        mock_srpm_collection = mock_db['units_srpm']
        mock_srpm_collection.find.return_value = [mock_unit]

        migration.migrate()

        self.assertEqual(mock_migrate_rpm_base.call_count, 2)
        mock_migrate_rpm_base.assert_called_with(mock_rpm_collection, mock_unit)
        mock_migrate_rpm_base.assert_called_with(mock_srpm_collection, mock_unit)


@mock.patch.object(migration, 'fix_location')
class TestMigrateRPMBase(unittest.TestCase):
    def test_migrate_rpm_base(self, fix_location_mock):
        unit = {
            "_id": "123",
            "filename": "foo-bar.rpm",
            "repodata": "some-repo-data"
        }
        expected_delta = {
            "repodata": fix_location_mock.return_value
        }
        mock_collection = mock.MagicMock()

        migration.migrate_rpm_base(mock_collection, unit)

        fix_location_mock.assert_called_once_with("some-repo-data", "foo-bar.rpm")
        mock_collection.update_one.assert_called_once_with({'_id': '123'}, {'$set': expected_delta})


class TestFixLocation(unittest.TestCase):
    def test_fix_location_lowercase(self):
        rpm = "mouse-0.1.12-1.noarch.rpm"
        repodata = {
            'primary': PRIMARY,
            'other': OTHER,
            'filelists': FILELISTS,
        }

        ret = migration.fix_location(repodata, rpm)

        self.assertIn('Packages/m/%s"' % rpm, ret["primary"])
        self.assertNotIn('<location href="foo-bar.rpm"/>', ret["primary"])
        self.assertEqual(ret["other"], OTHER)
        self.assertEqual(ret["filelists"], FILELISTS)

    def test_fix_location_uppercase(self):
        rpm = "Mouse-0.1.12-1.noarch.rpm"
        repodata = {
            'primary': PRIMARY,
            'other': OTHER,
            'filelists': FILELISTS,
        }

        ret = migration.fix_location(repodata, rpm)

        self.assertIn('Packages/m/%s"' % rpm, ret["primary"])
        self.assertNotIn('foo-bar.rpm"', ret["primary"])
        self.assertEqual(ret["other"], OTHER)
        self.assertEqual(ret["filelists"], FILELISTS)

    def test_fix_location_number(self):
        rpm = "1-mouse-0.1.12-1.noarch.rpm"
        repodata = {
            'primary': PRIMARY,
            'other': OTHER,
            'filelists': FILELISTS,
        }

        ret = migration.fix_location(repodata, rpm)

        self.assertIn('Packages/1/%s"' % rpm, ret["primary"])
        self.assertNotIn('foo-bar.rpm"', ret["primary"])
        self.assertEqual(ret["other"], OTHER)
        self.assertEqual(ret["filelists"], FILELISTS)

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

OTHER = '''
<package arch="noarch" name="mouse"
  pkgid="f4200643b0845fdc55ee002c92c0404a9f3a2a49f596c78b40ab56749de226ce">
  <version epoch="0" rel="1" ver="0.1.12" />
</package>'''

FILELISTS = '''
<package arch="noarch" name="mouse"
  pkgid="f4200643b0845fdc55ee002c92c0404a9f3a2a49f596c78b40ab56749de226ce">
  <version epoch="0" rel="1" ver="0.1.12" />
  <file>/tmp/mouse.txt</file>
</package>'''
