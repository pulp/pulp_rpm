import json
import unittest

from django.test import TestCase

# The code we're testing relies on createrepo_c, which is not available everywhere.
# If we can't import pulp_rpm.app.advisory, set a flag so we know to skip this test on the
# platform we're running on at the moment.
try:
    from pulp_rpm.app.advisory import resolve_advisory_conflict
    from pulp_rpm.app.exceptions import AdvisoryConflict
    from pulp_rpm.app.serializers.advisory import UpdateRecordSerializer

    no_createrepo = False
except ModuleNotFoundError:
    no_createrepo = True

BEAR_DOG_JSON = """{
    "issued_date":  "2022-01-01 12:34:55",
    "id":  "TEST-2022-0001",
    "type":  "Bug Fix Advisory",
    "release":  "1",
    "version": "1",
    "pkglist": [
        {
            "packages": [
                {
                    "arch": "noarch",
                    "epoch": "0",
                    "filename": "bear-4.1-1.noarch.rpm",
                    "name": "bear",
                    "reboot_suggested": false,
                    "relogin_suggested": false,
                    "restart_suggested": false,
                    "release": "1",
                    "src": "http://www.fedoraproject.org",
                    "sum": "",
                    "sum_type": "",
                    "version": "4.1"
                },
                {
                    "arch": "noarch",
                    "epoch": "0",
                    "filename": "dog-6.1-6.noarch.rpm",
                    "name": "dog",
                    "reboot_suggested": false,
                    "relogin_suggested": false,
                    "restart_suggested": false,
                    "release": "6",
                    "src": "http://www.fedoraproject.org",
                    "sum": "",
                    "sum_type": "",
                    "version": "6.1"
                }
            ]
        }
    ],
    "severity":  "",
    "description":  "Not available",
    "reboot_suggested":  false,
    "updated_date":  "2022-01-02 12:34:55",
    "solution":  "Not available",
    "fromstr":  "centos-announce@centos.org"
}"""

BIRD_JSON = """{
    "issued_date":  "2022-01-01 12:34:55",
    "id":  "TEST-2022-0001",
    "type":  "Bug Fix Advisory",
    "release":  "1",
    "version": "1",
    "pkglist": [
        {
            "packages": [
                {
                    "arch": "noarch",
                    "epoch": "0",
                    "filename": "bird-1.2-3.noarch.rpm",
                    "name": "bird",
                    "reboot_suggested": false,
                    "relogin_suggested": false,
                    "restart_suggested": false,
                    "release": "3",
                    "src": "http://www.fedoraproject.org",
                    "sum": "",
                    "sum_type": "",
                    "version": "1.2"
                }
            ]
        }
    ],
    "severity":  "",
    "description":  "Not available",
    "reboot_suggested":  false,
    "updated_date":  "2022-01-02 12:34:55",
    "solution":  "Not available",
    "fromstr":  "centos-announce@centos.org"
}"""

NEW_BIRD_JSON = """{
    "issued_date":  "2022-01-01 12:34:55",
    "id":  "TEST-2022-0001",
    "type":  "Bug Fix Advisory",
    "release":  "1",
    "version": "1",
    "pkglist": [
        {
            "packages": [
                {
                    "arch": "noarch",
                    "epoch": "0",
                    "filename": "bird-2.2-1.noarch.rpm",
                    "name": "bird",
                    "reboot_suggested": false,
                    "relogin_suggested": false,
                    "restart_suggested": false,
                    "release": "1",
                    "src": "http://www.fedoraproject.org",
                    "sum": "",
                    "sum_type": "",
                    "version": "2.2"
                }
            ]
        }
    ],
    "severity":  "",
    "description":  "Not available",
    "reboot_suggested":  false,
    "updated_date":  "2022-01-02 12:34:55",
    "solution":  "Not available",
    "fromstr":  "centos-announce@centos.org"
}"""

CAMEL_BEAR_JSON = """{
    "issued_date":  "2022-01-01 12:34:55",
    "id":  "TEST-2022-0001",
    "type":  "Bug Fix Advisory",
    "release":  "1",
    "version": "1",
    "pkglist": [
        {
            "packages": [
                {
                    "arch": "noarch",
                    "epoch": "0",
                    "filename": "camel-0.1-1.noarch.rpm",
                    "name": "camel",
                    "reboot_suggested": false,
                    "relogin_suggested": false,
                    "restart_suggested": false,
                    "release": "1",
                    "src": "http://www.fedoraproject.org",
                    "sum": "",
                    "sum_type": "",
                    "version": "0.1"
                },
                {
                    "arch": "noarch",
                    "epoch": "0",
                    "filename": "bear-4.1-1.noarch.rpm",
                    "name": "bear",
                    "reboot_suggested": false,
                    "relogin_suggested": false,
                    "restart_suggested": false,
                    "release": "1",
                    "src": "http://www.fedoraproject.org",
                    "sum": "",
                    "sum_type": "",
                    "version": "4.1"
                }
            ]
        }
    ],
    "severity":  "",
    "description":  "Not available",
    "reboot_suggested":  false,
    "updated_date":  "2022-01-02 12:34:55",
    "solution":  "Not available",
    "fromstr":  "centos-announce@centos.org"
}"""

CAMEL_BEAR_BIRD_JSON = """{
    "issued_date":  "2022-01-01 12:34:55",
    "id":  "TEST-2022-0001",
    "type":  "Bug Fix Advisory",
    "release":  "1",
    "version": "1",
    "pkglist": [
        {
            "packages": [
                {
                    "arch": "noarch",
                    "epoch": "0",
                    "filename": "camel-0.1-1.noarch.rpm",
                    "name": "camel",
                    "reboot_suggested": false,
                    "relogin_suggested": false,
                    "restart_suggested": false,
                    "release": "1",
                    "src": "http://www.fedoraproject.org",
                    "sum": "",
                    "sum_type": "",
                    "version": "0.1"
                },
                {
                    "arch": "noarch",
                    "epoch": "0",
                    "filename": "bear-4.1-1.noarch.rpm",
                    "name": "bear",
                    "reboot_suggested": false,
                    "relogin_suggested": false,
                    "restart_suggested": false,
                    "release": "1",
                    "src": "http://www.fedoraproject.org",
                    "sum": "",
                    "sum_type": "",
                    "version": "4.1"
                },
                {
                    "arch": "noarch",
                    "epoch": "0",
                    "filename": "bird-1.2-3.noarch.rpm",
                    "name": "bird",
                    "reboot_suggested": false,
                    "relogin_suggested": false,
                    "restart_suggested": false,
                    "release": "3",
                    "src": "http://www.fedoraproject.org",
                    "sum": "",
                    "sum_type": "",
                    "version": "1.2"
                }
            ]
        }
    ],
    "severity":  "",
    "description":  "Not available",
    "reboot_suggested":  false,
    "updated_date":  "2022-01-02 12:34:55",
    "solution":  "Not available",
    "fromstr":  "centos-announce@centos.org"
}"""

CAMEL_BEAR_DOG_JSON = """{
    "issued_date":  "2022-01-01 12:34:55",
    "id":  "TEST-2022-0001",
    "type":  "Bug Fix Advisory",
    "release":  "1",
    "version": "1",
    "pkglist": [
        {
            "packages": [
                {
                    "arch": "noarch",
                    "epoch": "0",
                    "filename": "camel-0.1-1.noarch.rpm",
                    "name": "camel",
                    "reboot_suggested": false,
                    "relogin_suggested": false,
                    "restart_suggested": false,
                    "release": "1",
                    "src": "http://www.fedoraproject.org",
                    "sum": "",
                    "sum_type": "",
                    "version": "0.1"
                },
                {
                    "arch": "noarch",
                    "epoch": "0",
                    "filename": "bear-4.1-1.noarch.rpm",
                    "name": "bear",
                    "reboot_suggested": false,
                    "relogin_suggested": false,
                    "restart_suggested": false,
                    "release": "1",
                    "src": "http://www.fedoraproject.org",
                    "sum": "",
                    "sum_type": "",
                    "version": "4.1"
                },
                {
                    "arch": "noarch",
                    "epoch": "0",
                    "filename": "dog-6.1-6.noarch.rpm",
                    "name": "dog",
                    "reboot_suggested": false,
                    "relogin_suggested": false,
                    "restart_suggested": false,
                    "release": "6",
                    "src": "http://www.fedoraproject.org",
                    "sum": "",
                    "sum_type": "",
                    "version": "6.1"
                }
            ]
        }
    ],
    "severity":  "",
    "description":  "Not available",
    "reboot_suggested":  false,
    "updated_date":  "2022-01-02 12:34:55",
    "solution":  "Not available",
    "fromstr":  "centos-announce@centos.org"
}"""


@unittest.skipIf(
    no_createrepo,
    "This test can only be run on a system that supports createrepo_c",
)
class TestAdvisoryConflicts(TestCase):
    """
    Test rules on advisory-conflicts.

    The "cases" being tested are described at pulp_rpm.app.advisory.resolve_advisory_conflict() -
    see description for further commentary.

    NOTE: We create advisories from JSON loaded from the strings above. Any time we call
    UpdateRecordSerializer.create(), we have to recreate the data-structure, because create()
    "pops" data out of the structure.
    """

    def test_same_dates_empty_intersection(self):
        """
        Case 1: Same date, pkglist intersection empty.

        Merge into existing, added[] = existing, excluded[] = incoming.
        """
        urs = UpdateRecordSerializer()
        cbd_data = json.loads(CAMEL_BEAR_DOG_JSON)
        existing = urs.create(cbd_data)

        b_data = json.loads(BIRD_JSON)
        incoming = urs.create(b_data)
        try:
            added, removed, excluded = resolve_advisory_conflict(existing, incoming)
            self.assertIsNotNone(added)
            self.assertIsNotNone(excluded)
            self.assertEqual(1, len(added))
            self.assertEqual(1, len(excluded))
            self.assertEqual(1, len(removed))
            self.assertEqual(existing.pulp_id, added[0])
            self.assertEqual(incoming.pulp_id, excluded[0])
            self.assertIsNotNone(existing.get_pkglist())
            names = set([pkg[0] for pkg in existing.get_pkglist()])
            for name in ("camel", "bear", "dog", "bird"):
                self.assertIn(name, names)
        finally:
            existing.delete()
            incoming.delete()

    def test_diff_dates_nonempty_intersection(self):
        """
        Case 2: Dates different, pkglist intersection non-empty.

        Accept "newer", remove/exclude "older"
        """
        urs = UpdateRecordSerializer()
        cb_data = json.loads(CAMEL_BEAR_JSON)
        existing1 = urs.create(cb_data)

        cbd_data = json.loads(CAMEL_BEAR_DOG_JSON)
        cbd_data["version"] = "2"
        incoming2 = urs.create(cbd_data)

        cb_data = json.loads(CAMEL_BEAR_JSON)
        cb_data["version"] = "3"
        existing3 = urs.create(cb_data)
        try:
            # Incoming is newer
            added, removed, excluded = resolve_advisory_conflict(existing1, incoming2)
            self.assertEqual(0, len(added))
            self.assertEqual(0, len(excluded))
            self.assertEqual(1, len(removed))
            self.assertEqual(existing1.pulp_id, removed[0])

            # Existing is newer
            added, removed, excluded = resolve_advisory_conflict(existing3, incoming2)
            self.assertEqual(0, len(added))
            self.assertEqual(1, len(excluded))
            self.assertEqual(0, len(removed))
            self.assertEqual(incoming2.pulp_id, excluded[0])
        finally:
            existing1.delete()
            existing3.delete()
            incoming2.delete()

    def test_diff_dates_name_intersection(self):
        """
        Case 3a: Dates differ, pkglist intersection empty, pkglists differ ONLY by EVR (same names).

        Accept "newer", remove/exclude "older"
        """
        urs = UpdateRecordSerializer()
        b_data = json.loads(BIRD_JSON)
        existing1 = urs.create(b_data)

        nb_data = json.loads(NEW_BIRD_JSON)
        nb_data["version"] = "3"
        incoming3 = urs.create(nb_data)

        b_data = json.loads(BIRD_JSON)
        b_data["version"] = "4"
        existing4 = urs.create(b_data)

        try:
            # incoming newer
            added, removed, excluded = resolve_advisory_conflict(existing1, incoming3)
            self.assertEqual(0, len(added))
            self.assertEqual(0, len(excluded))
            self.assertEqual(1, len(removed))
            self.assertEqual(existing1.pulp_id, removed[0])

            # existing newer
            added, removed, excluded = resolve_advisory_conflict(existing4, incoming3)
            self.assertEqual(0, len(added))
            self.assertEqual(1, len(excluded))
            self.assertEqual(0, len(removed))
            self.assertEqual(incoming3.pulp_id, excluded[0])
        finally:
            existing1.delete()
            existing4.delete()
            incoming3.delete()

    def test_diff_dates_empty_intersection(self):
        """
        Case 3b: Dates differ, pkglist intersection empty, NOT same pkg-names.

        raise ERROR
        """
        urs = UpdateRecordSerializer()
        cb_data = json.loads(CAMEL_BEAR_JSON)
        cb_data["version"] = "3"
        incoming3 = urs.create(cb_data)

        b_data = json.loads(BIRD_JSON)
        existing = urs.create(b_data)
        try:
            with self.assertRaises(AdvisoryConflict):
                added, removed, excluded = resolve_advisory_conflict(existing, incoming3)
        finally:
            existing.delete()
            incoming3.delete()

    def test_same_dates_nonempty_intersection(self):
        """
        Case 4: Same dates, pkglist intersection not empty, intersection NOT subset of either.

        Raise ERROR
        """
        urs = UpdateRecordSerializer()
        cb_data = json.loads(CAMEL_BEAR_BIRD_JSON)
        existing = urs.create(cb_data)

        cbd_data = json.loads(CAMEL_BEAR_DOG_JSON)
        incoming = urs.create(cbd_data)
        try:
            with self.assertRaises(AdvisoryConflict):
                added, removed, excluded = resolve_advisory_conflict(existing, incoming)
        finally:
            existing.delete()
            incoming.delete()
