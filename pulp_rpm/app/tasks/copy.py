from django.core.exceptions import MultipleObjectsReturned
from django.db.models import Q

from pulpcore.plugin.models import Content, RepositoryVersion

from pulp_rpm.app.depsolving import Solver
from pulp_rpm.app.models import UpdateRecord, Package, RpmRepository, Modulemd


def _filter_content(content, criteria, content_pks):
    """
    Filter content in the source repository version by criteria.

    Args:
        content: a queryset of content to filter
        criteria: a validated dict that maps content type to a list of filter criteria
        content_pks: a whitelist of content_pks to filter content
    """
    if not criteria and not content_pks:
        # if we have neither criteria and content pks, we're copying everything
        return content

    if criteria:
        # find the content_pks based on criteria
        content_pks = []
        for content_type in RpmRepository.CONTENT_TYPES:
            if criteria.get(content_type.TYPE):
                filters = Q()
                for filter in criteria[content_type.TYPE]:
                    filters |= Q(**filter)
                content_pks += content_type.objects.filter(filters).values_list("pk", flat=True)

    return content.filter(pk__in=content_pks)


def find_children_of_content(content, repository_version):
    """Finds the content referenced directly by other content and returns it all together.

    Finds RPMs referenced by Advisory/Errata content.

    Args:
        content (iterable): Content for which to resolve children
        repository_version (pulpcore.models.RepositoryVersion): Source repo version

    Returns: Queryset of Content objects that are children of the intial set of content
    """
    # Advisories that were selected to be copied
    advisory_ids = content.filter(pulp_type=UpdateRecord.get_pulp_type()).only('pk')
    # All packages in the source repository version
    package_ids = repository_version.content.filter(
        pulp_type=Package.get_pulp_type()).only('pk')
    # All modules in the source repository version
    module_ids = repository_version.content.filter(
        pulp_type=Modulemd.get_pulp_type()).only('pk')

    advisories = UpdateRecord.objects.filter(pk__in=advisory_ids)
    packages = Package.objects.filter(pk__in=package_ids)
    modules = Modulemd.objects.filter(pk__in=module_ids)

    children = set()

    for advisory in advisories:
        # Find rpms referenced by Advisories/Errata
        package_nevras = advisory.get_pkglist()
        for nevra in package_nevras:
            (name, epoch, version, release, arch) = nevra
            try:
                package = packages.get(
                    name=name, epoch=epoch, version=version, release=release, arch=arch)
                children.add(package.pk)
            except Package.DoesNotExist:
                raise
            except MultipleObjectsReturned:
                raise

        module_nsvcas = advisory.get_module_list()
        for nsvca in module_nsvcas:
            (name, stream, version, context, arch) = nsvca
            try:
                module = modules.get(
                    name=name, stream=stream, version=version, context=context, arch=arch)
                children.add(module.pk)
            except Modulemd.DoesNotExist:
                raise
            except MultipleObjectsReturned:
                raise

    # TODO: Find rpms referenced by PackageGroups,
    # PackageGroups referenced by PackageCategories, etc.

    return Content.objects.filter(pk__in=children)


def copy_content(source_repo_version_pk, dest_repo_pk, criteria, content_pks, dependency_solving):
    """
    Copy content from one repo to another.

    Args:
        source_repo_version_pk: repository version primary key to copy units from
        dest_repo_pk: repository primary key to copy units into
        criteria: a dict that maps type to a list of criteria to filter content by. Note that this
            criteria MUST be validated before being passed to this task.
        content_pks: a list of content pks to copy from source to destination
    """
    source_repo_version = RepositoryVersion.objects.get(pk=source_repo_version_pk)
    # source_repo = RpmRepository.objects.get(pk=source_repo_version.repository)

    dest_repo = RpmRepository.objects.get(pk=dest_repo_pk)
    dest_repo_version = dest_repo.latest_version()

    if not dependency_solving:
        content_to_copy = _filter_content(source_repo_version.content, criteria, content_pks)
        content_to_copy |= find_children_of_content(content_to_copy, source_repo_version)

        with dest_repo.new_version() as new_version:
            new_version.add_content(content_to_copy)

        return

    # Dependency Solving Branch
    # =========================
    content_to_copy = {}

    # TODO: add lookaside repos here
    repo_mapping = {source_repo_version: dest_repo_version}
    libsolv_repo_names = {}

    solver = Solver()

    for src in repo_mapping.keys():
        repo_name = solver.load_source_repo(src)
        libsolv_repo_names[repo_name] = src

        content = _filter_content(src.content, criteria, content_pks)
        children = find_children_of_content(content, src)
        content_to_copy[repo_name] = content | children

    for tgt in repo_mapping.values():
        solver.load_target_repo(tgt)

    solver.finalize()

    content_to_copy = solver.resolve_dependencies(content_to_copy)

    for from_repo, units in content_to_copy.items():
        src_repo_version = libsolv_repo_names[from_repo]
        dest_repo_version = repo_mapping[src_repo_version]
        with dest_repo_version.repository.new_version() as new_version:
            new_version.add_content(Content.objects.filter(pk__in=units))
