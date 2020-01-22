from django.db.models import Q

from pulpcore.plugin.models import RepositoryVersion

from pulp_rpm.app.depsolving import Solver
from pulp_rpm.app.models import RpmRepository


def _filter_content(content, criteria):
    """
    Filter content in the source repository version by criteria

    Args:
        content: a queryset of content to filter
        criteria: a validated dict that maps content type to a list of filter criteria
    """
    if not criteria:
        return content

    content_pks = []
    for content_type in RpmRepository.CONTENT_TYPES:
        if criteria.get(content_type.TYPE):
            filters = Q()
            for filter in criteria[content_type.TYPE]:
                filters |= Q(**filter)
            content_pks += content_type.objects.filter(filters).values_list("pk", flat=True)

    return content.filter(pk__in=content_pks)


def copy_content(source_repo_version_pk, dest_repo_pk, criteria, dependency_solving):
    """
    Copy content from one repo to another.

    Args:
        source_repo_version_pk: repository version primary key to copy units from
        dest_repo_pk: repository primary key to copy units into
        criteria: a dict that maps type to a list of criteria to filter content by. Note that this
            criteria MUST be validated before being passed to this task.
    """
    source_repo_version = RepositoryVersion.objects.get(pk=source_repo_version_pk)
    source_repo = RpmRepository.objects.get(pk=source_repo_version.repository)

    dest_repo = RpmRepository.objects.get(pk=dest_repo_pk)
    dest_repo_version = dest_repo.latest_version()

    content_types = source_repo.CONTENT_TYPES
    list(content_types)

    content_to_copy = _filter_content(source_repo_version.content, criteria)

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
