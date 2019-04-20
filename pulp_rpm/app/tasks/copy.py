from django.db.models import Q

from pulpcore.app.models.repository import RepositoryVersion


def copy_content(source_repo_version, dest_repo, types):
    """
    Copy content from one repo to another.

    Args:
        source_repo_version: repository version to copy units from
        dest_repo: repository to copy units into
        types: a tuple of strings representing the '_type' values of types to include in the copy
    """
    query = None
    for ptype in types:
        if query:
            query = query | Q(_type=ptype)
        else:
            query = Q(_type=ptype)

    content_to_copy = source_repo_version.content.filter(query)
    with RepositoryVersion.create(dest_repo) as new_version:
        new_version.add_content(content_to_copy)
