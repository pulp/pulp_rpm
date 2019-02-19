import os

from pulp_rpm.app.shared_utils import _prepare_package
from pulp_rpm.app.models import Package
from pulpcore.app.models.content import ContentArtifact
from pulpcore.app.models.repository import RepositoryVersion


def one_shot_upload(artifact, repository=None):
    """
    One shot upload for RPM package.

    Args:
        artifact: validated artifact for a file
        repository: repository to extend with new pkg
        path: artifact href
    """
    filename = os.path.basename(artifact.file.path)

    # export META from rpm and prepare dict as saveable format
    try:
        new_pkg = _prepare_package(artifact, filename)
    except OSError:
        raise OSError('RPM file cannot be parsed for metadata.')

    pkg, created = Package.objects.get_or_create(**new_pkg)

    ContentArtifact.objects.create(
        artifact=artifact,
        content=pkg,
        relative_path=filename
    )

    if repository:
        content_to_add = Package.objects.filter(pkgId=pkg.pkgId)

        # create new repo version with uploaded package
        with RepositoryVersion.create(repository) as new_version:
            new_version.add_content(content_to_add)
