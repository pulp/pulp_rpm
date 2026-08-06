from django.db import transaction
from django.db.models import Q, QuerySet

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
from pulp_rpm.app.shared_utils import annotate_with_age, safe_in


class ChildContentResolver:
    """Resolves content referenced by other content within a repository version."""

    def __init__(self, repo_version: RepositoryVersion, only_content_ids=None):
        self.repo_version = repo_version
        content_qs = Content.objects.filter(pulp_domain=get_domain_pk())
        if only_content_ids is not None:
            content_qs = content_qs.filter(safe_in("pk", only_content_ids))
        self._content = self._restrict_to_repo_version(content_qs)

    def _restrict_to_repo_version(self, qs: QuerySet) -> QuerySet:
        """Restrict a queryset to the content present in this repository version.

        Built on Content (plain pulp_id pk), since safe_in's any_array lookup doesn't support
        the relation field backing pk on subclasses like PackageGroup/Package. Keeps the id list
        as a single array param, unlike get_content()'s literal pk__in=[...], which would
        multiply bound params when combined via .union()/|.
        """
        repo_content = Content.objects.filter(safe_in("pk", self.repo_version.content_ids))
        return qs.filter(pk__in=repo_content)

    def resolve(self) -> QuerySet[Content]:
        """Return the selected content combined with all resolved children."""
        advisory_children = self.get_advisory_children()
        group_children = self.get_comps_children()
        repository_content = self.get_repository_content()
        return repository_content | advisory_children | group_children

    def get_repository_content(self) -> QuerySet[Content]:
        """Return the filtered content within the repository version."""
        return self._content

    def get_comps_children(self) -> QuerySet[Content]:
        """Resolve comps children: groups from categories/environments, and their packages."""
        group_children, expanded_groups = self._resolve_child_groups()
        package_children = self._resolve_group_packages(expanded_groups)
        return group_children | package_children

    def get_advisory_children(self) -> QuerySet[Content]:
        """Resolve packages and modules referenced by advisories."""
        advisories = self._content_of_type(self._content, UpdateRecord)
        packages = self._content_of_type(self.repo_version.content, Package)
        modules = self._content_of_type(self.repo_version.content, Modulemd)

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
        return Content.objects.filter(safe_in("pk", child_pks))

    def _resolve_child_groups(
        self,
    ) -> tuple[QuerySet[Content], QuerySet[PackageGroup]]:
        """Collect group names from categories and environments, return matching groups."""
        packagecategories = self._content_of_type(self._content, PackageCategory)
        packageenvironments = self._content_of_type(self._content, PackageEnvironment)
        packagegroups = self._content_of_type(self._content, PackageGroup)

        packagegroup_names = set()
        for packagecategory in packagecategories.iterator():
            for group_id in packagecategory.group_ids:
                packagegroup_names.add(group_id["name"])

        for packageenvironment in packageenvironments.iterator():
            for group_id in packageenvironment.group_ids:
                packagegroup_names.add(group_id["name"])
            for group_id in packageenvironment.option_ids:
                packagegroup_names.add(group_id["name"])

        package_group_qs = PackageGroup.objects.filter(safe_in("name", packagegroup_names))
        child_package_groups = self._restrict_to_repo_version(package_group_qs)
        expanded_groups = packagegroups.union(child_package_groups)
        return Content.objects.filter(pk__in=child_package_groups), expanded_groups

    def _resolve_group_packages(self, packagegroups: QuerySet[PackageGroup]) -> QuerySet[Content]:
        """Resolve the latest version of missing packages referenced by groups."""
        packagegroup_package_names = set()
        for packagegroup in packagegroups.iterator():
            packagegroup_package_names |= set(pkg["name"] for pkg in packagegroup.packages)

        # TODO: do modular/nonmodular need to be taken into account?
        existing_package_names = (
            Package.objects.filter(safe_in("name", packagegroup_package_names))
            .filter(pk__in=self._content)
            .values_list("name", flat=True)
            .distinct()
        )

        missing_package_names = packagegroup_package_names - set(existing_package_names)
        needed_packages = annotate_with_age(
            self._restrict_to_repo_version(
                Package.objects.filter(safe_in("name", missing_package_names))
            )
        )

        child_pks = set()
        for pkg in needed_packages.iterator():
            if pkg.age == 1:
                child_pks.add(pkg.pk)
        return Content.objects.filter(safe_in("pk", child_pks))

    @staticmethod
    def _content_of_type(content_qs: QuerySet[Content], model) -> QuerySet:
        """Narrow a Content queryset to a specific subclass."""
        return model.objects.filter(
            pk__in=content_qs.filter(pulp_type=model.get_pulp_type()).only("pk")
        )


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

        content_ids = entry.get("content")

        return (
            source_repo_version,
            dest_repo_version,
            dest_repo,
            content_ids,
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
                content_ids,
                dest_version_provided,
            ) = process_entry(entry)

            resolver = ChildContentResolver(source_repo_version, content_ids)
            content_to_copy = resolver.resolve()
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
                content_ids,
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
            content_to_copy[source_repo_name] = ChildContentResolver(
                source_repo_version, content_ids
            ).resolve()

        solver.finalize()

        content_to_copy = solver.resolve_dependencies(
            content_to_copy, focus_installed=not dependency_upgrade
        )

        for from_repo, units in content_to_copy.items():
            src_repo_version = libsolv_repo_names[from_repo]
            dest_repo_version = repo_mapping[src_repo_version]
            base_version = dest_repo_version if base_versions[src_repo_version] else None
            with dest_repo_version.repository.new_version(base_version=base_version) as new_version:
                new_version.add_content(Content.objects.filter(safe_in("pk", units)))
