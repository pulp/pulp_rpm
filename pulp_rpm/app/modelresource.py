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
    UpdateCollection,
    UpdateCollectionPackage,
    UpdateRecord,
    UpdateReference,
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
        exclude = BaseContentResource.Meta.exclude + (
            "collections",
            "references",
        )


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
        import_id_fields = ("name",)
        fields = ("name", "pulp_type", "description", "original_checksum_types", "sub_repo")


class UpdateCollectionResource(QueryModelResource):
    """
    Resource for import/export of rpm_updatecollection entities.
    """

    update_record = fields.Field(
        column_name="update_record",
        attribute="update_record",
        widget=ForeignKeyWidget(UpdateRecord, field="digest"),
    )

    def set_up_queryset(self):
        """
        Set up a queryset for UpdateCollections.

        Returns:
            UpdateCollections belonging to UpdateRecords for a specified repo-version.

        """
        return UpdateCollection.objects.filter(
            update_record__in=UpdateRecord.objects.filter(
                pk__in=self.repo_version.content
            )
        )

    class Meta:
        model = UpdateCollection
        exclude = QueryModelResource.Meta.exclude + ("packages",)
        import_id_fields = tuple(
            chain.from_iterable(UpdateCollection._meta.unique_together)
        )


class UpdateReferenceResource(QueryModelResource):
    """
    Resource for import/export of rpm_updatereference entities.
    """

    update_record = fields.Field(
        column_name="update_record",
        attribute="update_record",
        widget=ForeignKeyWidget(UpdateRecord, field="digest"),
    )

    def set_up_queryset(self):
        """
        Set up a queryset for UpdateReferences.

        Returns:
            UpdateReferences belonging to UpdateRecords for a specified repo-version.

        """
        return UpdateReference.objects.filter(
            update_record__in=UpdateRecord.objects.filter(pk__in=self.repo_version.content)
        )

    class Meta:
        model = UpdateReference
        import_id_fields = (
            "href",
            "ref_type",
            "update_record",
        )


class UpdateCollectionPackageResource(QueryModelResource):
    """
    Resource for import/export of rpm_updatecollectionpackage entities.
    """

    class UpdateCollectionForeignKeyWidget(ForeignKeyWidget):
        """
        Class that lets us specify a multi-key link to UpdateCollection.

        Format is str(<name>|<update_record.digest>), to be used at import-row time.
        """

        def render(self, value, obj):
            """Render formatted string to use as unique-identifier."""
            return f"{obj.update_collection.name}|{obj.update_collection.update_record.digest}"

    update_collection = fields.Field(
        column_name="update_collection",
        attribute="update_collection",
        widget=UpdateCollectionForeignKeyWidget(UpdateCollection),
    )

    def before_import_row(self, row, **kwargs):
        """
        Find the new-uuid of the UpdateCollection for this row.

        We start with the update_collection identified as "<uc-name>|<uc-updaterecord-digest>"
        Find the UpdateRecord, find the UpdateCollection by (name,update-record), and then
        replace row[update_collection] with the pulp_id of the (previously-saved) UpdateCollection.

        Args:
            row (tablib.Dataset row): import-row representing a single UpdateCollectionPackage.
            kwargs: args passed along from the import() call.
        """
        (uc_name, uc_updrec_digest) = row["update_collection"].split("|")
        uc_updrecord = UpdateRecord.objects.filter(digest=uc_updrec_digest).first()
        uc = UpdateCollection.objects.filter(
            name=uc_name, update_record=uc_updrecord
        ).first()
        row["update_collection"] = str(uc.pulp_id)

    def set_up_queryset(self):
        """
        Set up a queryset for UpdateCollectionPackages.

        Returns:
            UpdateCollectionPackages specific to a specified repo-version.

        """
        return UpdateCollectionPackage.objects.filter(
            update_collection__in=UpdateCollection.objects.filter(
                update_record__in=UpdateRecord.objects.filter(
                    pk__in=self.repo_version.content
                )
            )
        )

    class Meta:
        model = UpdateCollectionPackage
        import_id_fields = (
            "name",
            "epoch",
            "version",
            "release",
            "sum",
            "filename",
            "update_collection"
        )


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
    UpdateReferenceResource,
    UpdateCollectionResource,
    UpdateCollectionPackageResource,
]
