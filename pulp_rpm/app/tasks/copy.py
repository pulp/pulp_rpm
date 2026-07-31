from django.contrib.postgres.fields import ArrayField
from django.db import transaction
from django.db.models import Func, Q, QuerySet, TextField, Value

from pulpcore.plugin.models import Content, RepositoryVersion
from pulpcore.plugin.util import get_domain_pk

from pulp_rpm.app.depsolving import Solver
from pulp_rpm.app.models import (
    Modulemd,
    Package,
    PackageCategory,
    PackageEnvironment,
    PackageGroup,
    RpmRepository,
    UpdateRecord,
)
from pulp_rpm.app.shared_utils import annotate_with_age


def _unnest_names(names):
    """Wrap a set of names in a subquery using unnest(ARRAY[...]).

    Avoids the PostgreSQL 65535 parameter limit by passing all names as a single
    array parameter instead of N scalar parameters.
    """
    return Package.objects.annotate(
        _unnested=Func(
            Value(sorted(names), output_field=ArrayField(TextField())),
            function="unnest",
        )
    ).values("_unnested")


def _content_of_type(content_qs: QuerySet[Content], model) -> QuerySet:
    """Filter a Content queryset to a specific subclass and return a typed queryset."""
    return model.objects.filter(
        pk__in=content_qs.filter(pulp_type=model.get_pulp_type()).only("pk")
    )


def _resolve_advisory_children(
    content: QuerySet[Content], src_repo_version: RepositoryVersion
) -> QuerySet[Content]:
    """Find packages and modules referenced by advisories via NEVRA/NSVCA matching."""
    advisories = _content_of_type(content, UpdateRecord)
    packages = _content_of_type(src_repo_version.content, Package)
    modules = _content_of_type(src_repo_version.content, Modulemd)

    child_pks = set()
    for advisory in advisories.iterator():
        package_nevras = advisory.get_pkglist()
        advisory_package_q = Q(pk__in=[])
        for nevra in package_nevras:
            name, epoch, version, release, arch = nevra
            advisory_package_q |= Q(
                name=name,
                epoch=epoch,
                version=version,
                release=release,
                arch=arch,
                pulp_domain=get_domain_pk(),
            )
        child_pks.update(packages.filter(advisory_package_q).values_list("pk", flat=True))

        module_nsvcas = advisory.get_module_list()
        advisory_module_q = Q(pk__in=[])
        for nsvca in module_nsvcas:
            name, stream, version, context, arch = nsvca
            advisory_module_q |= Q(
                name=name,
                stream=stream,
                version=version,
                context=context,
                arch=arch,
                pulp_domain=get_domain_pk(),
            )
        child_pks.update(modules.filter(advisory_module_q).values_list("pk", flat=True))
    return Content.objects.filter(pk__in=child_pks)


def _resolve_child_groups(
    content: QuerySet[Content], src_repo_version: RepositoryVersion
) -> tuple[QuerySet[Content], QuerySet[PackageGroup]]:
    """Resolve groups referenced by categories/environments.

    Returns (child_pks, expanded_groups queryset).
    """
    packagecategories = _content_of_type(content, PackageCategory)
    packageenvironments = _content_of_type(content, PackageEnvironment)
    packagegroups = _content_of_type(content, PackageGroup)

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
    expanded_groups = packagegroups.union(child_package_groups)
    return Content.objects.filter(pk__in=child_package_groups), expanded_groups


def _resolve_group_packages(
    packagegroups: QuerySet[PackageGroup],
    content: QuerySet[Content],
    src_repo_version: RepositoryVersion,
) -> QuerySet[Content]:
    """Find the latest version of each package referenced by groups but not already in content."""
    packagegroup_package_names = set()
    for packagegroup in packagegroups.iterator():
        packagegroup_package_names |= set(pkg["name"] for pkg in packagegroup.packages)

    # TODO: do modular/nonmodular need to be taken into account?
    existing_package_names = (
        Package.objects.filter(
            name__in=_unnest_names(packagegroup_package_names),
            pk__in=content,
        )
        .values_list("name", flat=True)
        .distinct()
    )

    missing_package_names = packagegroup_package_names - set(existing_package_names)
    missing_package_names_qs = Package.objects.filter(name__in=_unnest_names(missing_package_names))

    needed_packages = annotate_with_age(src_repo_version.get_content(missing_package_names_qs))

    child_pks = set()
    for pkg in needed_packages.iterator():
        if pkg.age == 1:
            child_pks.add(pkg.pk)
    return Content.objects.filter(pk__in=child_pks)


def find_children_of_content(
    content_filter: Q, src_repo_version: RepositoryVersion
) -> QuerySet[Content]:
    """Finds the content referenced directly by other content and returns it all together.

    Args:
        content_filter (Q): Filter to select content from src_repo_version
        src_repo_version (pulpcore.models.RepositoryVersion): Source repo version

    Returns: Queryset of Content objects that are children of the initial set of content
    """
    filter_qs = Content.objects.filter(content_filter)
    content = src_repo_version.get_content(filter_qs)

    advisory_children = _resolve_advisory_children(content, src_repo_version)
    group_children, expanded_groups = _resolve_child_groups(content, src_repo_version)
    package_children = _resolve_group_packages(expanded_groups, content, src_repo_version)

    return content | advisory_children | group_children | package_children


@transaction.atomic
def copy_content(config, dependency_solving, dependency_upgrade=False):
    """
    Copy content from one repo to another.

    Args:
        config: Details of how the copy should be performed.
        dependency_solving: Use dependency solving to find additional content units to copy.
        dependency_upgrade: Resolve dependencies to latest compatible versions instead of
            preferring versions already in the destination.

    Config format details:
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

        content_filter &= Q(pulp_domain=get_domain_pk())

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

            content_to_copy = find_children_of_content(content_filter, source_repo_version)

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
            content_to_copy[source_repo_name] = find_children_of_content(
                content_filter, source_repo_version
            )

        solver.finalize()

        content_to_copy = solver.resolve_dependencies(
            content_to_copy, focus_installed=not dependency_upgrade
        )

        for from_repo, units in content_to_copy.items():
            src_repo_version = libsolv_repo_names[from_repo]
            dest_repo_version = repo_mapping[src_repo_version]
            base_version = dest_repo_version if base_versions[src_repo_version] else None
            with dest_repo_version.repository.new_version(base_version=base_version) as new_version:
                new_version.add_content(Content.objects.filter(pk__in=units))
