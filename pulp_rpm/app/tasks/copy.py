from django.core.exceptions import MultipleObjectsReturned
from django.db import transaction
from django.db.models import Q

from pulpcore.plugin.models import Content, RepositoryVersion

from pulp_rpm.app.depsolving import Solver
from pulp_rpm.app.models import UpdateRecord, Package, RpmRepository, Modulemd


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


@transaction.atomic
def copy_content(config, dependency_solving):
    """
    Copy content from one repo to another.

    Args:
        source_repo_version_pk: repository version primary key to copy units from
        dest_repo_pk: repository primary key to copy units into
        criteria: a dict that maps type to a list of criteria to filter content by. Note that this
            criteria MUST be validated before being passed to this task.
        content_pks: a list of content pks to copy from source to destination
    """
    def process_entry(entry):
        source_repo_version = RepositoryVersion.objects.get(pk=entry["source_repo_version"])
        dest_repo = RpmRepository.objects.get(pk=entry["dest_repo"])

        dest_version_provided = bool(entry.get("dest_base_version"))
        if dest_version_provided:
            dest_repo_version = RepositoryVersion.objects.get(pk=entry["dest_base_version"])
        else:
            dest_repo_version = dest_repo.latest_version()

        if entry.get("content"):
            content_filter = Q(pk__in=entry.get("content"))
        else:
            content_filter = Q()

        return (
            source_repo_version, dest_repo_version,
            dest_repo, content_filter, dest_version_provided
        )

    if not dependency_solving:
        # No Dependency Solving Branch
        # ============================
        for entry in config:
            (source_repo_version, dest_repo_version,
                dest_repo, content_filter, dest_version_provided) = process_entry(entry)

            content_to_copy = source_repo_version.content.filter(content_filter)
            content_to_copy |= find_children_of_content(content_to_copy, source_repo_version)

            base_version = dest_repo_version if dest_version_provided else None
            with dest_repo.new_version(base_version=base_version) as new_version:
                new_version.add_content(content_to_copy)
    else:
        # Dependency Solving Branch
        # =========================

        # TODO: a more structured way to store this state would be nice.
        content_to_copy = {}
        repo_mapping = {}
        libsolv_repo_names = {}
        base_versions = {}

        solver = Solver()

        for entry in config:
            (source_repo_version, dest_repo_version,
                dest_repo, content_filter, dest_version_provided) = process_entry(entry)

            repo_mapping[source_repo_version] = dest_repo_version
            base_versions[source_repo_version] = dest_version_provided

            # Load the content from the source and destination repository versions into the solver
            source_repo_name = solver.load_source_repo(source_repo_version)
            solver.load_target_repo(dest_repo_version)

            # Store the correspondance between the libsolv name of a repo version and the
            # actual Pulp repo version, so that we can work backwards to get the latter
            # from the former.
            libsolv_repo_names[source_repo_name] = source_repo_version

            # Find all of the matching content in the repository version, then determine
            # child relationships (e.g. RPM children of Errata/Advisories), then combine
            # those two sets to copy the specified content + children.
            content = source_repo_version.content.filter(content_filter)
            children = find_children_of_content(content, source_repo_version)
            content_to_copy[source_repo_name] = content | children

        solver.finalize()

        content_to_copy = solver.resolve_dependencies(content_to_copy)

        for from_repo, units in content_to_copy.items():
            src_repo_version = libsolv_repo_names[from_repo]
            dest_repo_version = repo_mapping[src_repo_version]
            base_version = dest_repo_version if base_versions[src_repo_version] else None
            with dest_repo_version.repository.new_version(base_version=base_version) as new_version:
                new_version.add_content(Content.objects.filter(pk__in=units))
