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
        cm.add(mid_epoch, "nevra", "path")
        cm.add(low_epoch, "nevra", "path2")
        self.assertEqual([mid_epoch.cid], cm.retained_cids())
        cm.add(high_epoch, "nevra2", "path")
        self.assertEqual([high_epoch.cid], cm.retained_cids())

        # Test that collisions on nevra or path are checking build_time correctly.
        cm = _CollisionManager()
        cm.add(mid_build_time, "nevra", "path")
        cm.add(low_build_time, "nevra", "path2")
        self.assertEqual([mid_build_time.cid], cm.retained_cids())
        cm.add(high_build_time, "nevra2", "path")
        self.assertEqual([high_build_time.cid], cm.retained_cids())
