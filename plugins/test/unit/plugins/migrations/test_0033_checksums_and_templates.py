from pulp.common.compat import unittest

import mock

from pulp.server.db.migrate.models import _import_all_the_way


PATH_TO_MODULE = 'pulp_rpm.plugins.migrations.0033_checksums_and_templates'
migration = _import_all_the_way(PATH_TO_MODULE)


@mock.patch('pulp.server.db.connection.get_database')
@mock.patch.object(migration, 'migrate_rpm_base')
@mock.patch.object(migration, 'migrate_drpms')
class TestMigrate(unittest.TestCase):
    def test_calls_migrate_rpm_base(self, mock_migrate_drpms, mock_migrate_rpm_base, mock_get_db):
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

    def test_calls_migrate_drpms(self, mock_migrate_drpms, mock_migrate_rpm_base, mock_get_db):
        mock_db = mock_get_db.return_value
        mock_drpm_collection = mock_db['units_drpm']

        migration.migrate()

        mock_migrate_drpms.assert_called_once_with(mock_drpm_collection)


class TestMigrateDRPMs(unittest.TestCase):
    def test_calls_update(self):
        mock_collection = mock.MagicMock()

        migration.migrate_drpms(mock_collection)

        # re-typing the call args here would have little value, so we just make sure the call
        # happened
        self.assertEqual(mock_collection.update_many.call_count, 1)


class TestMigrateRPMBase(unittest.TestCase):
    def setUp(self):
        super(TestMigrateRPMBase, self).setUp()
        self.rpm = {
            '_id': '1234',
            'checksum': 'abc123',
            'checksumtype': 'sha1',
            'repodata': {'primary': 'stuff'},
        }

    @mock.patch.object(migration, '_modify_xml')
    def test_calls_modify_xml(self, mock_modify_xml):
        mock_collection = mock.MagicMock()

        migration.migrate_rpm_base(mock_collection, self.rpm)

        mock_modify_xml.assert_called_once_with(self.rpm['repodata'])

    @mock.patch.object(migration, '_modify_xml')
    def test_calls_update(self, mock_modify_xml):
        mock_collection = mock.MagicMock()

        migration.migrate_rpm_base(mock_collection, self.rpm)

        expected_delta = {
            'repodata': mock_modify_xml.return_value,
            'checksums': {'sha1': 'abc123'},
        }
        mock_collection.update_one.assert_called_once_with({'_id': '1234'},
                                                           {'$set': expected_delta})


class TestModifyXml(unittest.TestCase):
    def setUp(self):
        super(TestModifyXml, self).setUp()
        self.repodata = {
            'primary': PRIMARY,
            'other': OTHER,
            'filelists': FILELISTS,
        }

    def test_other_template(self):
        ret = migration._modify_xml(self.repodata)

        self.assertTrue('{{ pkgid }}' in ret['other'])
        self.assertTrue('f4200643b' not in ret['other'])

    def test_filelists_template(self):
        ret = migration._modify_xml(self.repodata)

        self.assertTrue('{{ pkgid }}' in ret['filelists'])
        self.assertTrue('f4200643b' not in ret['filelists'])

    def test_primary_template(self):
        ret = migration._modify_xml(self.repodata)

        self.assertTrue('{{ checksum }}' in ret['primary'])
        self.assertTrue('{{ checksumtype }}' in ret['primary'])
        self.assertTrue('f4200643b' not in ret['primary'])
        self.assertTrue('sha256' not in ret['primary'])


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
  <location href="mouse-0.1.12-1.noarch.rpm"/>
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
