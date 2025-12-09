from django.test import TestCase

from pulp_rpm.app.tasks.publishing import PkgBuild, _CollisionManager


class TestPublishing(TestCase):
    """Test the publishing task."""

    def test_collision_manager(self):
        """Test that the collision manager is correctly choosing which packages to keep."""
        low_epoch = PkgBuild(cid=1, epoch=0, build_time=100)
        mid_epoch = PkgBuild(cid=2, epoch=1, build_time=150)
        high_epoch = PkgBuild(cid=3, epoch=2, build_time=50)
        low_build_time = PkgBuild(cid=4, epoch=0, build_time=200)
        mid_build_time = PkgBuild(cid=5, epoch=0, build_time=250)
        high_build_time = PkgBuild(cid=6, epoch=0, build_time=300)

        # Test that collisions on nevra or path are checking epoch correctly.
        cm = _CollisionManager()
        cm.add(mid_epoch, "nevra", "path", None)
        cm.add(low_epoch, "nevra", "path2", None)
        self.assertEqual([mid_epoch.cid], cm.retained_cids())
        cm.add(high_epoch, "nevra2", "path", None)
        self.assertEqual([high_epoch.cid], cm.retained_cids())

        # Test that collisions on nevra or path are checking build_time correctly.
        cm = _CollisionManager()
        cm.add(mid_build_time, "nevra", "path", None)
        cm.add(low_build_time, "nevra", "path2", None)
        self.assertEqual([mid_build_time.cid], cm.retained_cids())
        cm.add(high_build_time, "nevra2", "path", None)
        self.assertEqual([high_build_time.cid], cm.retained_cids())

        # Test that collisions on 2nd_path are being handled correctly.
        cm = _CollisionManager()
        cm.add(mid_build_time, "nevra", "path", "second_path")
        cm.add(low_build_time, "nevra2", "path2", "second_path")
        self.assertEqual({mid_build_time.cid, low_build_time.cid}, set(cm.retained_cids()))
        self.assertIn(mid_build_time.cid, cm.cid_to_second_path)
        self.assertEqual(cm.cid_to_second_path[mid_build_time.cid], "second_path")
        self.assertNotIn(low_build_time.cid, cm.cid_to_second_path)

        cm.add(high_build_time, "nevra3", "path3", "second_path")
        self.assertEqual(
            {mid_build_time.cid, low_build_time.cid, high_build_time.cid}, set(cm.retained_cids())
        )
        self.assertIn(high_build_time.cid, cm.cid_to_second_path)
        self.assertEqual(cm.cid_to_second_path[high_build_time.cid], "second_path")
        self.assertNotIn(mid_build_time.cid, cm.cid_to_second_path)
