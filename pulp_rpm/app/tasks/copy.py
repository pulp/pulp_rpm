from django.db.models import Q

from pulpcore.plugin.models import Repository, RepositoryVersion


def copy_content(source_repo_version_pk, dest_repo_pk, types):
    """
    Copy content from one repo to another.

    Args:
        source_repo_version_pk: repository version primary key to copy units from
        dest_repo_pk: repository primary key to copy units into
        types: a tuple of strings representing the '_type' values of types to include in the copy
    """
    source_repo_version = RepositoryVersion.objects.get(pk=source_repo_version_pk)
    dest_repo = Repository.objects.get(pk=dest_repo_pk)

    query = None
    for ptype in types:
        if query:
            query = query | Q(_type=ptype)
        else:
            query = Q(_type=ptype)

    content_to_copy = source_repo_version.content.filter(query)
    with RepositoryVersion.create(dest_repo) as new_version:
        new_version.add_content(content_to_copy)
