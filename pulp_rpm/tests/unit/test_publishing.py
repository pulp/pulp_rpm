import pytest

from pulp_rpm.app.tasks.publishing import PublicationData


def test_publication_path_rejects_directory_traversal(tmp_path, monkeypatch):
    """Reject paths that escape the publication directory directly or via a symlink."""
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="outside publication"):
        PublicationData._publication_path("../outside")

    (tmp_path / "subrepo").symlink_to(tmp_path.parent, target_is_directory=True)
    with pytest.raises(ValueError, match="outside publication"):
        PublicationData._publication_path("subrepo/metadata")
