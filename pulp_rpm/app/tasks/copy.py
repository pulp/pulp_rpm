from django.db import transaction
from django.db.models import Q

from pulpcore.plugin.models import Content, RepositoryVersion

from pulp_rpm.app.depsolving import Solver
from pulp_rpm.app.models import (
    UpdateRecord,
    Package,
    PackageCategory,
    PackageEnvironment,
    PackageGroup,
    RpmRepository,
    Modulemd,
)


def find_children_of_content(content, src_repo_version):
    """Finds the content referenced directly by other content and returns it all together.

    Finds RPMs referenced by Advisory/Errata content.

    Args:
        content (Queryset): Content for which to resolve children
        src_repo_version (pulpcore.models.RepositoryVersion): Source repo version

    Returns: Queryset of Content objects that are children of the intial set of content
    """
    # Content that were selected to be copied
    advisory_ids = content.filter(pulp_type=UpdateRecord.get_pulp_type()).only("pk")
    packagecategory_ids = content.filter(pulp_type=PackageCategory.get_pulp_type()).only("pk")
    packageenvironment_ids = content.filter(pulp_type=PackageEnvironment.get_pulp_type()).only("pk")
    packagegroup_ids = content.filter(pulp_type=PackageGroup.get_pulp_type()).only("pk")

    # Content in the source repository version
    package_ids = src_repo_version.content.filter(pulp_type=Package.get_pulp_type()).only("pk")
    module_ids = src_repo_version.content.filter(pulp_type=Modulemd.get_pulp_type()).only("pk")

    advisories = UpdateRecord.objects.filter(pk__in=advisory_ids)
    packages = Package.objects.filter(pk__in=package_ids)
    packagecategories = PackageCategory.objects.filter(pk__in=packagecategory_ids)
    packageenvironments = PackageEnvironment.objects.filter(pk__in=packageenvironment_ids)
    packagegroups = PackageGroup.objects.filter(pk__in=packagegroup_ids)
    modules = Modulemd.objects.filter(pk__in=module_ids)

    children = set()

    for advisory in advisories.iterator():
        # Find rpms referenced by Advisories/Errata
        package_nevras = advisory.get_pkglist()
        advisory_package_q = Q(pk__in=[])
        for nevra in package_nevras:
            (name, epoch, version, release, arch) = nevra
            advisory_package_q |= Q(
                name=name, epoch=epoch, version=version, release=release, arch=arch
            )
        children.update(packages.filter(advisory_package_q).values_list("pk", flat=True))

        module_nsvcas = advisory.get_module_list()
        advisory_module_q = Q(pk__in=[])
        for nsvca in module_nsvcas:
            (name, stream, version, context, arch) = nsvca
            advisory_module_q |= Q(
                name=name, stream=stream, version=version, context=context, arch=arch
            )
        children.update(modules.filter(advisory_module_q).values_list("pk", flat=True))

    # PackageCategories & PackageEnvironments resolution must go before PackageGroups
    packagegroup_names = set()
    for packagecategory in packagecategories.iterator():
        for group_id in packagecategory.group_ids:
            packagegroup_names.add(group_id["name"])

    for packageenvironment in packageenvironments.iterator():
        for group_id in packageenvironment.group_ids:
            packagegroup_names.add(group_id["name"])
        for group_id in packageenvironment.option_ids:
            packagegroup_names.add(group_id["name"])

    child_package_groups = PackageGroup.objects.filter(
        name__in=packagegroup_names, pk__in=src_repo_version.content
    )
    children.update([pkggroup.pk for pkggroup in child_package_groups])
    packagegroups = packagegroups.union(child_package_groups)

    # Find rpms referenced by PackageGroups
    packagegroup_package_names = set()
    for packagegroup in packagegroups.iterator():
        packagegroup_package_names |= set(pkg["name"] for pkg in packagegroup.packages)

    # TODO: do modular/nonmodular need to be taken into account?
    existing_package_names = (
        Package.objects.filter(
            name__in=packagegroup_package_names,
            pk__in=content,
        )
        .values_list("name", flat=True)
        .distinct()
    )

    missing_package_names = packagegroup_package_names - set(existing_package_names)

    needed_packages = Package.objects.with_age().filter(
        name__in=missing_package_names, pk__in=src_repo_version.content
    )

    # Pick the latest version of each package available which isn't already present
    # in the content set.
    for pkg in needed_packages.iterator():
        if pkg.age == 1:
            children.add(pkg.pk)

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

        if entry.get("content") is not None:
            content_filter = Q(pk__in=entry.get("content"))
        else:
            content_filter = Q()

        return (
            source_repo_version,
            dest_repo_version,
            dest_repo,
            content_filter,
            dest_version_provided,
        )

    if not dependency_solving:
        # No Dependency Solving Branch
        # ============================
        for entry in config:
            (
                source_repo_version,
                dest_repo_version,
                dest_repo,
                content_filter,
                dest_version_provided,
            ) = process_entry(entry)

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
            (
                source_repo_version,
                dest_repo_version,
                dest_repo,
                content_filter,
                dest_version_provided,
            ) = process_entry(entry)

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
