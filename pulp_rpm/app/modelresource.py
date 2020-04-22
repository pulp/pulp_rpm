from pulpcore.plugin.importexport import QueryModelResource
from pulp_rpm.app.models import (
    DistributionTree,
    Modulemd,
    ModulemdDefaults,
    Package,
    PackageCategory,
    PackageGroup,
    PackageEnvironment,
    PackageLangpacks,
    RepoMetadataFile,
    UpdateRecord,
)


class DistributionTreeResource(QueryModelResource):
    """
    Resource for import/export of rpm_distributiontree entities.
    """

    def set_up_queryset(self):
        """
        :return: DistributionTrees specific to a specified repo-version.
        """
        return DistributionTree.objects.filter(pk__in=self.repo_version.content)

    class Meta:
        model = DistributionTree


class ModulemdResource(QueryModelResource):
    """
    Resource for import/export of rpm_modulemd entities.
    """

    def set_up_queryset(self):
        """
        :return: Modulemds specific to a specified repo-version.
        """
        return Modulemd.objects.filter(pk__in=self.repo_version.content)

    class Meta:
        model = Modulemd


class ModulemdDefaultsResource(QueryModelResource):
    """
    Resource for import/export of rpm_modulemddefaults entities.
    """

    def set_up_queryset(self):
        """
        :return: ModulemdDefaults specific to a specified repo-version.
        """
        return ModulemdDefaults.objects.filter(pk__in=self.repo_version.content)

    class Meta:
        model = ModulemdDefaults


class PackageResource(QueryModelResource):
    """
    Resource for import/export of rpm_package entities.
    """

    def set_up_queryset(self):
        """
        :return: Packages specific to a specified repo-version.
        """
        return Package.objects.filter(pk__in=self.repo_version.content)

    class Meta:
        model = Package


class PackageCategoryResource(QueryModelResource):
    """
    Resource for import/export of rpm_packagecategory entities.
    """

    def set_up_queryset(self):
        """
        :return: PackageCategories specific to a specified repo-version.
        """
        return PackageCategory.objects.filter(pk__in=self.repo_version.content)

    class Meta:
        model = PackageCategory


class PackageGroupResource(QueryModelResource):
    """
    Resource for import/export of rpm_packagegroup entities.
    """

    def set_up_queryset(self):
        """
        :return: PackageGroups specific to a specified repo-version.
        """
        return PackageGroup.objects.filter(pk__in=self.repo_version.content)

    class Meta:
        model = PackageGroup


class PackageEnvironmentResource(QueryModelResource):
    """
    Resource for import/export of rpm_packageenvironment entities.
    """

    def set_up_queryset(self):
        """
        :return: PackageEnvironments specific to a specified repo-version.
        """
        return PackageEnvironment.objects.filter(pk__in=self.repo_version.content)

    class Meta:
        model = PackageEnvironment


class PackageLangpacksResource(QueryModelResource):
    """
    Resource for import/export of rpm_packagelangpack entities.
    """

    def set_up_queryset(self):
        """
        :return: PackageLangpacks specific to a specified repo-version.
        """
        return PackageLangpacks.objects.filter(pk__in=self.repo_version.content)

    class Meta:
        model = PackageLangpacks


class RepoMetadataFileResource(QueryModelResource):
    """
    Resource for import/export of rpm_repometadatafile entities.
    """

    def set_up_queryset(self):
        """
        :return: RepoMetadataFiles specific to a specified repo-version.
        """
        return RepoMetadataFile.objects.filter(pk__in=self.repo_version.content)

    class Meta:
        model = RepoMetadataFile


class UpdateRecordResource(QueryModelResource):
    """
    Resource for import/export of rpm_updaterecord entities.
    """

    def set_up_queryset(self):
        """
        :return: UpdateRecords specific to a specified repo-version.
        """
        return UpdateRecord.objects.filter(pk__in=self.repo_version.content)

    class Meta:
        model = UpdateRecord


IMPORT_ORDER = [
    PackageResource,
    ModulemdResource,
    ModulemdDefaultsResource,
    PackageGroupResource,
    PackageCategoryResource,
    PackageEnvironmentResource,
    PackageLangpacksResource,
    UpdateRecordResource,
    DistributionTreeResource,
    RepoMetadataFileResource,
]
