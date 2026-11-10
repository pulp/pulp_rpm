import pytest
from django.test import SimpleTestCase

from pulp_rpm.app.tasks.publishing import (
    PkgBuild,
    PublicationData,
    PublicationPlanner,
    _CannotDerive,
    _CollisionManager,
    _sign_repomd,
    _splice_stream,
    _validate_package_delta,
)


def test_publication_path_rejects_directory_traversal(tmp_path, monkeypatch):
    """Reject paths that escape the publication directory directly or via a symlink."""
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="outside publication"):
        PublicationData._publication_path("../outside")

    (tmp_path / "subrepo").symlink_to(tmp_path.parent, target_is_directory=True)
    with pytest.raises(ValueError, match="outside publication"):
        PublicationData._publication_path("subrepo/metadata")


class TestPublishing(SimpleTestCase):
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


PRIMARY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<metadata xmlns="http://linux.duke.edu/metadata/common" packages="3">
<package type="rpm">
  <name>alpha</name>
  <checksum type="sha256" pkgid="YES">aaa</checksum>
</package>
<package type="rpm">
  <name>beta</name>
  <checksum type="sha256" pkgid="YES">bbb</checksum>
</package>
<package type="rpm">
  <name>gamma</name>
  <checksum type="sha256" pkgid="YES">ccc</checksum>
</package>
</metadata>
"""


class TestSpliceStream(SimpleTestCase):
    """The package splice must keep retained entries verbatim and append the delta."""

    def test_keeps_retained_and_appends_added(self):
        import io

        output = io.StringIO()
        _splice_stream(
            io.StringIO(PRIMARY_XML),
            output,
            {"aaa", "ccc"},
            ['<package type="rpm"><name>delta</name></package>\n'],
            3,
            "sha256",
        )
        text = output.getvalue()
        assert 'packages="3"' in text
        assert "alpha" in text
        assert "gamma" in text
        assert "delta" in text
        assert "beta" not in text
        assert text.rstrip().endswith("</metadata>")

    def test_reads_pkgid_attribute_blocks(self):
        import io

        base = (
            '<metadata packages="1">\n'
            '<package pkgid="abc" name="x" arch="noarch">\n</package>\n'
            "</metadata>\n"
        )
        output = io.StringIO()
        _splice_stream(io.StringIO(base), output, {"abc"}, [], 1, "sha256")
        assert 'pkgid="abc"' in output.getvalue()

    def test_count_mismatch_is_refused(self):
        import io

        with pytest.raises(_CannotDerive, match="wrote 1 of 2"):
            _splice_stream(io.StringIO(PRIMARY_XML), io.StringIO(), {"aaa"}, [], 2, "sha256")

    def test_missing_header_is_refused(self):
        import io

        with pytest.raises(_CannotDerive, match="header"):
            _splice_stream(
                io.StringIO('<package type="rpm">\n'), io.StringIO(), set(), [], 0, "sha256"
            )

    def test_open_checksum_uses_requested_algorithm(self):
        import io

        output = io.StringIO()
        checksum, size = _splice_stream(io.StringIO(PRIMARY_XML), output, {"aaa"}, [], 1, "sha512")
        assert len(checksum) == 128
        assert size == len(output.getvalue().encode())
        checksum, size = _splice_stream(
            io.StringIO(PRIMARY_XML), io.StringIO(), {"aaa"}, [], 1, None
        )
        assert checksum is None
        assert size > 0

    def test_preserves_filelists_root(self):
        import io

        base = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<filelists xmlns="http://linux.duke.edu/metadata/filelists" packages="1">\n'
            '<package pkgid="abc" name="x" arch="noarch">\n</package>\n'
            "</filelists>\n"
        )
        output = io.StringIO()
        _splice_stream(io.StringIO(base), output, {"abc"}, [], 1, "sha256")
        text = output.getvalue()
        assert 'packages="1"' in text
        assert text.rstrip().endswith("</filelists>")


class TestPackageDelta(SimpleTestCase):
    """A derivation must not change which package wins a NEVRA or a filename."""

    @staticmethod
    def _plan(added=(), removed=()):
        from types import SimpleNamespace

        return SimpleNamespace(
            delta=SimpleNamespace(added_pks=frozenset(added), removed_pks=frozenset(removed)),
            request=SimpleNamespace(repository_version=object()),
        )

    @staticmethod
    def _patch(delta_nevra, delta_path, retained_nevras, retained_filenames):
        from types import SimpleNamespace
        from unittest.mock import patch

        return (
            patch(
                "pulp_rpm.app.tasks.publishing._target_package_keys",
                return_value=(retained_nevras, retained_filenames),
            ),
            patch(
                "pulp_rpm.app.tasks.publishing._package_details",
                return_value={
                    "delta": (SimpleNamespace(path=delta_path), delta_nevra),
                },
            ),
        )

    def test_removed_package_colliding_with_a_survivor_is_refused(self):
        nevra = ("pkg", "0", "1", "1", "noarch")
        retained_keys, details = self._patch(
            nevra, "Packages/p/pkg-1-1.noarch.rpm", {nevra}, {"pkg-1-1.noarch.rpm"}
        )
        with retained_keys, details:
            with pytest.raises(_CannotDerive, match="collision key"):
                _validate_package_delta(self._plan(removed=["delta"]))

    def test_added_package_colliding_with_a_survivor_is_refused(self):
        retained_keys, details = self._patch(
            ("pkg", "0", "1", "1", "noarch"),
            "Packages/p/other.rpm",
            {("pkg", "0", "1", "1", "noarch")},
            {"unrelated.rpm"},
        )
        with retained_keys, details:
            with pytest.raises(_CannotDerive, match="collision key"):
                _validate_package_delta(self._plan(added=["delta"]))

    def test_non_colliding_delta_is_accepted(self):
        retained_keys, details = self._patch(
            ("pkg", "0", "1", "1", "noarch"),
            "Packages/p/pkg-1-1.noarch.rpm",
            {("other", "0", "2", "1", "noarch")},
            {"other-2-1.noarch.rpm"},
        )
        with retained_keys, details:
            _validate_package_delta(self._plan(removed=["delta"]))


class TestWorthDeriving(SimpleTestCase):
    """Deriving pays off only while most of both sides are retained."""

    def test_derives_when_most_of_both_sides_are_retained(self):
        assert PublicationPlanner._worth_deriving(4, 1, 1)
        assert PublicationPlanner._worth_deriving(4, 2, 0)

    def test_publishes_fully_when_most_of_the_target_is_new(self):
        assert not PublicationPlanner._worth_deriving(4, 3, 0)
        assert not PublicationPlanner._worth_deriving(4, 4, 0)

    def test_publishes_fully_when_most_of_the_base_was_removed(self):
        assert not PublicationPlanner._worth_deriving(2, 0, 3)


def test_sign_repomd_publishes_under_the_given_repodata_path(tmp_path, monkeypatch):
    """Sub-repo metadata must not be signed into the top-level repodata path."""
    from types import SimpleNamespace
    from unittest.mock import patch

    monkeypatch.chdir(tmp_path)
    repomd = tmp_path / "repomd.xml"
    repomd.write_text("<repomd/>")
    signature = tmp_path / "repomd.xml.asc"
    signature.write_text("signature")

    def sign(path):
        return {"file": str(repomd), "signature": str(signature)}

    service = SimpleNamespace(public_key="KEY", sign=sign)
    with patch("pulp_rpm.app.tasks.publishing.PublishedMetadata") as published:
        _sign_repomd(object(), str(repomd), "addon/repodata", service)

    paths = [call.kwargs["relative_path"] for call in published.create_from_file.call_args_list]
    assert paths
    assert all(path.startswith("addon/repodata/") for path in paths)
