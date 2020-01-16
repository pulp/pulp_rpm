from django.db.models import Q

from pulpcore.plugin.models import Repository, RepositoryVersion

from pulp_rpm.app.models import RpmRepository


def copy_content(source_repo_version_pk, dest_repo_pk, criteria, dependency_solving):
    """
    Copy content from one repo to another.

    Args:
        source_repo_version_pk: repository version primary key to copy units from
        dest_repo_pk: repository primary key to copy units into
        types: a tuple of strings representing the '_type' values of types to include in the copy
    """
    source_repo_version = RepositoryVersion.objects.get(pk=source_repo_version_pk)
    source_repo = RpmRepository.objects.get(pk=source_repo_version.repository)
    content_types = source_repo.CONTENT_TYPES
    list(content_types)

    dest_repo = RpmRepository.objects.get(pk=dest_repo_pk)

    content_to_copy = source_repo_version.content

    with dest_repo.new_version() as new_version:
        new_version.add_content(content_to_copy)
