from itertools import chain

from import_export import fields
from import_export.widgets import ForeignKeyWidget

from pulpcore.plugin.importexport import BaseContentResource, QueryModelResource
from pulpcore.plugin.models import Content
from pulp_rpm.app.models import (
    Addon,
    Checksum,
    DistributionTree,
    Image,
    Modulemd,
    ModulemdDefaults,
    Package,
    PackageCategory,
    PackageGroup,
    PackageEnvironment,
    PackageLangpacks,
    RepoMetadataFile,
    RpmRepository,
    UpdateRecord,
    Variant,
)


class RpmContentResource(BaseContentResource):
    """
    Resource for import/export of rpm content.

    This Content Resource also handles exporting of any content for subrepos.
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize the RpmContentResource.
        """
        self.content_mapping = {}
        super().__init__(*args, **kwargs)

    def _add_to_mapping(self, repo, uuids):
        if not uuids.exists():
            return

        self.content_mapping[repo.name] = list(map(str, uuids))

    def set_up_queryset(self):
        """
        Return Content for a RepositoryVersion while populating content_mapping.

        Returns:
            django.db.models.QuerySet: The Content to export for a RepositoryVersion

        """
        content = self.Meta.model.objects.filter(pk__in=self.repo_version.content)
        self._add_to_mapping(self.repo_version.repository, content.values_list("pulp_id",
                                                                               flat=True))

        tree = DistributionTree.objects.filter(pk__in=self.repo_version.content).first()
        if tree:
            for repo in tree.repositories():
                version = repo.latest_version()
                content |= self.Meta.model.objects.filter(pk__in=version.content)
                self._add_to_mapping(repo, version.content.values_list("pulp_id", flat=True))

        return content


class ModulemdResource(RpmContentResource):
    """
    Resource for import/export of rpm_modulemd entities.
    """

    class Meta:
        model = Modulemd
        import_id_fields = model.natural_key_fields()


class ModulemdDefaultsResource(RpmContentResource):
    """
    Resource for import/export of rpm_modulemddefaults entities.
    """

    class Meta:
        model = ModulemdDefaults
        import_id_fields = model.natural_key_fields()


class PackageResource(RpmContentResource):
    """
    Resource for import/export of rpm_package entities.
    """

    class Meta:
        model = Package
        import_id_fields = model.natural_key_fields()


class PackageCategoryResource(RpmContentResource):
    """
    Resource for import/export of rpm_packagecategory entities.
    """

    class Meta:
        model = PackageCategory
        import_id_fields = model.natural_key_fields()


class PackageGroupResource(RpmContentResource):
    """
    Resource for import/export of rpm_packagegroup entities.
    """

    class Meta:
        model = PackageGroup
        import_id_fields = model.natural_key_fields()


class PackageEnvironmentResource(RpmContentResource):
    """
    Resource for import/export of rpm_packageenvironment entities.
    """

    class Meta:
        model = PackageEnvironment
        import_id_fields = model.natural_key_fields()


class PackageLangpacksResource(RpmContentResource):
    """
    Resource for import/export of rpm_packagelangpack entities.
    """

    class Meta:
        model = PackageLangpacks
        import_id_fields = model.natural_key_fields()


class RepoMetadataFileResource(RpmContentResource):
    """
    Resource for import/export of rpm_repometadatafile entities.
    """

    class Meta:
        model = RepoMetadataFile
        import_id_fields = model.natural_key_fields()


class UpdateRecordResource(RpmContentResource):
    """
    Resource for import/export of rpm_updaterecord entities.
    """

    class Meta:
        model = UpdateRecord
        import_id_fields = model.natural_key_fields()


# Distribution Tree

class DistributionTreeResource(RpmContentResource):
    """
    Resource for import/export of rpm_distributiontree entities.
    """

    class Meta:
        model = DistributionTree
        import_id_fields = model.natural_key_fields()


class ChecksumResource(QueryModelResource):
    """
    Resource for import/export of rpm_checksum entities.
    """

    def before_import_row(self, row, **kwargs):
        """
        Finds and sets distribution tree using upstream_id.

        Args:
            row (tablib.Dataset row): incoming import-row representing a single Checksum.
            kwargs: args passed along from the import() call.

        """
        tree = DistributionTree.objects.get(upstream_id=row["distribution_tree"])
        row["distribution_tree"] = str(tree.pk)

    def set_up_queryset(self):
        """
        Set up a queryset for RepositoryVersion distribution tree checksums.

        Returns:
            django.db.models.QuerySet: The checksums contained in the repo version

        """
        tree = DistributionTree.objects.filter(pk__in=self.repo_version.content).first()
        if tree:
            return Checksum.objects.filter(distribution_tree=tree)
        else:
            return Checksum.objects.none()

    class Meta:
        model = Checksum
        import_id_fields = tuple(chain.from_iterable(Checksum._meta.unique_together))


class ImageResource(QueryModelResource):
    """
    Resource for import/export of rpm_image entities.
    """

    def before_import_row(self, row, **kwargs):
        """
        Finds and sets distribution tree using upstream_id.

        Args:
            row (tablib.Dataset row): incoming import-row representing a single Image.
            kwargs: args passed along from the import() call.

        """
        tree = DistributionTree.objects.get(upstream_id=row["distribution_tree"])
        row["distribution_tree"] = str(tree.pk)

    def set_up_queryset(self):
        """
        Set up a queryset for RepositoryVersion distribution tree images.

        Returns:
            django.db.models.QuerySet: The images contained in the repo version

        """
        tree = DistributionTree.objects.filter(pk__in=self.repo_version.content).first()
        if tree:
            return Image.objects.filter(distribution_tree=tree)
        else:
            return Image.objects.none()

    class Meta:
        model = Image
        import_id_fields = tuple(chain.from_iterable(Image._meta.unique_together))


class AddonResource(QueryModelResource):
    """
    Resource for import/export of rpm_addon entities.
    """

    repository = fields.Field(
        column_name="repository",
        attribute="repository",
        widget=ForeignKeyWidget(RpmRepository, "name")
    )

    def before_import_row(self, row, **kwargs):
        """
        Finds and sets distribution tree using upstream_id.

        Args:
            row (tablib.Dataset row): incoming import-row representing a single Addon.
            kwargs: args passed along from the import() call.

        """
        tree = DistributionTree.objects.get(upstream_id=row["distribution_tree"])
        row["distribution_tree"] = str(tree.pk)

    def set_up_queryset(self):
        """
        Set up a queryset for RepositoryVersion distribution tree addons.

        Returns:
            django.db.models.QuerySet: The addons contained in the repo version

        """
        tree = DistributionTree.objects.filter(pk__in=self.repo_version.content).first()
        if tree:
            return Addon.objects.filter(distribution_tree=tree)
        else:
            return Addon.objects.none()

    class Meta:
        model = Addon
        import_id_fields = tuple(chain.from_iterable(Addon._meta.unique_together))


class VariantResource(QueryModelResource):
    """
    Resource for import/export of rpm_variant entities.
    """

    repository = fields.Field(
        column_name="repository",
        attribute="repository",
        widget=ForeignKeyWidget(RpmRepository, "name")
    )

    def before_import_row(self, row, **kwargs):
        """
        Finds and sets distribution tree using upstream_id.

        Args:
            row (tablib.Dataset row): incoming import-row representing a single Variant.
            kwargs: args passed along from the import() call.

        """
        tree = DistributionTree.objects.get(upstream_id=row["distribution_tree"])
        row["distribution_tree"] = str(tree.pk)

    def set_up_queryset(self):
        """
        Set up a queryset for RepositoryVersion distribution tree variants.

        Returns:
            django.db.models.QuerySet: The variants contained in the repo version

        """
        tree = DistributionTree.objects.filter(pk__in=self.repo_version.content).first()
        if tree:
            return Variant.objects.filter(distribution_tree=tree)
        else:
            return Variant.objects.none()

    class Meta:
        model = Variant
        import_id_fields = tuple(chain.from_iterable(Variant._meta.unique_together))


class DistributionTreeRepositoryResource(QueryModelResource):
    """
    Resource for import/export of distribution tree subrepos.
    """

    def set_up_queryset(self):
        """
        Set up a queryset for RepositoryVersion distribution tree repos.

        Returns:
            django.db.models.QuerySet: The subrepos contained in the repo version

        """
        try:
            tree = self.repo_version.content.get(pulp_type=DistributionTree.get_pulp_type())
        except Content.DoesNotExist:
            return []
        else:
            return tree.cast().repositories()

    class Meta:
        model = RpmRepository
        import_id_fields = ('name',)
        fields = ("name", "pulp_type", "description", "original_checksum_types", "sub_repo")


IMPORT_ORDER = [
    PackageResource,
    ModulemdResource,
    ModulemdDefaultsResource,
    PackageGroupResource,
    PackageCategoryResource,
    PackageEnvironmentResource,
    PackageLangpacksResource,
    UpdateRecordResource,
    RepoMetadataFileResource,
    DistributionTreeResource,
    DistributionTreeRepositoryResource,
    ChecksumResource,
    ImageResource,
    AddonResource,
    VariantResource,
]
