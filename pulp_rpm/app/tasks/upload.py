from pulpcore.plugin.models import (
    Artifact,
    ContentArtifact,
    CreatedResource,
)

from pulp_rpm.app.shared_utils import _prepare_package
from pulp_rpm.app.models import (
    Package,
    RpmRepository,
)


def one_shot_upload(artifact_pk, filename, repository_pk=None):
    """
    One shot upload for RPM package.

    Args:
        artifact_pk: validated artifact for a file
        filename : name of file
        repository_pk: repository to extend with new pkg
    """
    artifact = Artifact.objects.get(pk=artifact_pk)

    # export META from rpm and prepare dict as saveable format
    try:
        new_pkg = _prepare_package(artifact, filename)
    except OSError:
        raise OSError('RPM file cannot be parsed for metadata.')

    pkg, created = Package.objects.get_or_create(**new_pkg)

    if not created:
        raise OSError('RPM package {} already exists.'.format(pkg.filename))

    ContentArtifact.objects.create(
        artifact=artifact,
        content=pkg,
        relative_path=filename
    )

    resource = CreatedResource(content_object=pkg)
    resource.save()

    if repository_pk:
        repository = RpmRepository.objects.get(pk=repository_pk)
        content_to_add = Package.objects.filter(pkgId=pkg.pkgId)

        # create new repo version with uploaded package
        with repository.new_version() as new_version:
            new_version.add_content(content_to_add)
