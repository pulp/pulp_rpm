from pulpcore.plugin.importexport import BaseContentResource
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


class DistributionTreeResource(BaseContentResource):
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
        import_id_fields = model.natural_key_fields()


class ModulemdResource(BaseContentResource):
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
        import_id_fields = model.natural_key_fields()


class ModulemdDefaultsResource(BaseContentResource):
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
        import_id_fields = model.natural_key_fields()


class PackageResource(BaseContentResource):
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
        import_id_fields = model.natural_key_fields()


class PackageCategoryResource(BaseContentResource):
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
        import_id_fields = model.natural_key_fields()


class PackageGroupResource(BaseContentResource):
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
        import_id_fields = model.natural_key_fields()


class PackageEnvironmentResource(BaseContentResource):
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
        import_id_fields = model.natural_key_fields()


class PackageLangpacksResource(BaseContentResource):
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
        import_id_fields = model.natural_key_fields()


class RepoMetadataFileResource(BaseContentResource):
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
        import_id_fields = model.natural_key_fields()


class UpdateRecordResource(BaseContentResource):
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
        import_id_fields = model.natural_key_fields()


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
