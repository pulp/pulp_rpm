from django.db.models import Q

from pulpcore.plugin.models import Repository, RepositoryVersion

from pulp_rpm.app.depsolving import Solver
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

    dest_repo = RpmRepository.objects.get(pk=dest_repo_pk)
    dest_repo_version = dest_repo.latest_version()

    content_types = source_repo.CONTENT_TYPES
    list(content_types)

    content_to_copy = source_repo_version.content

    if dependency_solving:
        # TODO: add lookaside repos here
        source_repos = set([source_repo_version])
        target_repos = set([dest_repo_version])

        solver = Solver()

        for src in source_repos:
            solver.load_source_repo(src)

        for tgt in target_repos:
            solver.load_target_repo(tgt)

        solver.finalize()
        # solver.find_dependent_units(content_to_copy)
        # TODO: combine the original filtered units w/ the dependencies into one queryset
        # (add_content() requires a queryset)

    with dest_repo.new_version() as new_version:
        new_version.add_content(content_to_copy)
