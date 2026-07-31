from django.db import transaction
from django.db.models import BooleanField
from django.db.models.expressions import RawSQL

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
from pulp_rpm.app.sql_utils import annotate_with_age, get_content_in_repoversion, safe_in


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
    package_ids = get_content_in_repoversion(
        src_repo_version, pulp_type=Package.get_pulp_type()
    ).only("pk")
    module_ids = get_content_in_repoversion(
        src_repo_version, pulp_type=Modulemd.get_pulp_type()
    ).only("pk")

    # pulp_type is required alongside pk: django-lifecycle (BaseModel) needs it per instance to
    # evaluate its hooks, and omitting it here would trigger a refresh_from_db() per row instead.
    advisories = UpdateRecord.objects.filter(pk__in=advisory_ids).only("pk", "pulp_type")
    packages = Package.objects.filter(pk__in=package_ids)
    packagecategories = PackageCategory.objects.filter(pk__in=packagecategory_ids)
    packageenvironments = PackageEnvironment.objects.filter(pk__in=packageenvironment_ids)
    packagegroups = PackageGroup.objects.filter(pk__in=packagegroup_ids).only(
        "pk", "packages", "pulp_type"
    )
    modules = Modulemd.objects.filter(pk__in=module_ids)

    children = set()

    # --- Advisories: resolve the packages and modules they reference ---
    domain_pk = get_domain_pk()
    for advisory in advisories.iterator():
        package_nevras = advisory.get_pkglist()
        if package_nevras:
            # Uses a single unnest()-zipped array comparison (avoid param blow)
            names, epochs, versions, releases, arches = zip(*package_nevras)
            matching_packages = (
                packages.filter(pulp_domain=domain_pk)
                .annotate(
                    _nevra_match=RawSQL(
                        '("rpm_package"."name", "rpm_package"."epoch", "rpm_package"."version", '
                        '"rpm_package"."release", "rpm_package"."arch") IN '
                        "(SELECT * FROM unnest(%s::text[], %s::text[], %s::text[], "
                        "%s::text[], %s::text[]))",
                        (list(names), list(epochs), list(versions), list(releases), list(arches)),
                        output_field=BooleanField(),
                    )
                )
                .filter(_nevra_match=True)
            )
            children.update(matching_packages.values_list("pk", flat=True))

        module_nsvcas = advisory.get_module_list()
        if module_nsvcas:
            # Uses a single unnest()-zipped array comparison (avoid param blow)
            names, streams, versions, contexts, arches = zip(*module_nsvcas)
            matching_modules = (
                modules.filter(pulp_domain=domain_pk)
                .annotate(
                    _nsvca_match=RawSQL(
                        '("rpm_modulemd"."name", "rpm_modulemd"."stream", '
                        '"rpm_modulemd"."version", "rpm_modulemd"."context", '
                        '"rpm_modulemd"."arch") IN '
                        "(SELECT * FROM unnest(%s::text[], %s::text[], %s::text[], "
                        "%s::text[], %s::text[]))",
                        (list(names), list(streams), list(versions), list(contexts), list(arches)),
                        output_field=BooleanField(),
                    )
                )
                .filter(_nsvca_match=True)
            )
            children.update(matching_modules.values_list("pk", flat=True))

    # --- PackageCategories & PackageEnvironments: resolve the PackageGroups they reference ---
    # (must go before the PackageGroups section below, which needs the full group set)
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
        safe_in("name", packagegroup_names), pk__in=get_content_in_repoversion(src_repo_version)
    ).only("pk", "packages", "pulp_type")
    children.update(child_package_groups.values_list("pk", flat=True))
    packagegroups = packagegroups.union(child_package_groups)

    # --- PackageGroups: resolve the packages they reference ---
    packagegroup_package_names = set()
    for packagegroup in packagegroups.iterator():
        packagegroup_package_names |= set(pkg["name"] for pkg in packagegroup.packages)

    # TODO: do modular/nonmodular need to be taken into account?
    existing_package_names = (
        Package.objects.filter(
            safe_in("name", packagegroup_package_names),
            pk__in=content,
        )
        .values_list("name", flat=True)
        .distinct()
    )

    missing_package_names = packagegroup_package_names - set(existing_package_names)

    needed_packages = annotate_with_age(
        Package.objects.filter(
            safe_in("name", missing_package_names),
            pk__in=get_content_in_repoversion(src_repo_version),
        )
    )

    # Pick the latest version of each package available which isn't already present
    # in the content set.
    for pk, age in needed_packages.values_list("pk", "age").iterator():
        if age == 1:
            children.add(pk)

    return Content.objects.filter(safe_in("pk", children))


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
        content_pks = entry.get("content")
        return (
            source_repo_version,
            dest_repo_version,
            dest_repo,
            content_pks,
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
                content_pks,
                dest_version_provided,
            ) = process_entry(entry)

            content_in_repo = get_content_in_repoversion(source_repo_version)
            if content_pks is None:
                content_to_copy = content_in_repo
            else:
                user_selected = content_in_repo.filter(safe_in("pk", content_pks))
                content_children = find_children_of_content(user_selected, source_repo_version)
                content_to_copy = user_selected | content_children

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
                content_pks,
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
            content_in_repo = get_content_in_repoversion(source_repo_version)
            if content_pks is None:
                content = content_in_repo
            else:
                content = content_in_repo.filter(safe_in("pk", content_pks))
            children = find_children_of_content(content, source_repo_version)
            content_to_copy[source_repo_name] = content | children

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
