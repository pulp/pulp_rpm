from itertools import chain

from import_export import fields
from import_export.widgets import ForeignKeyWidget, ManyToManyWidget
from pulpcore.plugin.util import get_domain

from pulpcore.plugin.importexport import BaseContentResource, QueryModelResource
from pulpcore.plugin.modelresources import RepositoryResource
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
        self._add_to_mapping(
            self.repo_version.repository, content.values_list("pulp_id", flat=True)
        )

        tree = DistributionTree.objects.filter(pk__in=self.repo_version.content).first()
        if tree:
            for repo in tree.repositories():
                version = repo.latest_version()
                content |= self.Meta.model.objects.filter(pk__in=version.content)
                self._add_to_mapping(repo, version.content.values_list("pulp_id", flat=True))

        return content.order_by("content_ptr_id")

    def dehydrate__pulp_domain(self, content):
        return str(content._pulp_domain_id)


class ModulemdResource(RpmContentResource):
    """
    Resource for import/export of rpm_modulemd entities.
    """

    packages = fields.Field(
        column_name="package_ids",
        attribute="packages",
        widget=ManyToManyWidget(model=Package, separator=",", field="pkgId"),
    )

    def before_import_row(self, row, row_number=None, **kwargs):
        super().before_import_row(row, row_number=row_number, **kwargs)

        if "packages" in row:
            pulp_ids = row["packages"].split(",")
            pkgids = (
                Package.objects.select_related("content_ptr")
                .filter(content_ptr__upstream_id__in=pulp_ids, pulp_domain=get_domain())
                .values_list("pkgId", flat=True)
            )
            row["package_ids"] = ",".join(pkgids)
            del row["packages"]

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
        super().before_import_row(row, **kwargs)
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
            return Checksum.objects.filter(distribution_tree=tree).order_by("pulp_id")
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
        super().before_import_row(row, **kwargs)

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
            return Image.objects.filter(distribution_tree=tree).order_by("pulp_id")
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
        widget=ForeignKeyWidget(RpmRepository, "name"),
    )

    def before_import_row(self, row, **kwargs):
        """
        Finds and sets distribution tree using upstream_id.

        Args:
            row (tablib.Dataset row): incoming import-row representing a single Addon.
            kwargs: args passed along from the import() call.

        """
        super().before_import_row(row, **kwargs)

        tree = DistributionTree.objects.get(
            upstream_id=row["distribution_tree"], pulp_domain=get_domain()
        )
        row["distribution_tree"] = str(tree.pk)

    def set_up_queryset(self):
        """
        Set up a queryset for RepositoryVersion distribution tree addons.

        Returns:
            django.db.models.QuerySet: The addons contained in the repo version

        """
        tree = DistributionTree.objects.filter(pk__in=self.repo_version.content).first()
        if tree:
            return Addon.objects.filter(distribution_tree=tree).order_by("pulp_id")
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
        widget=ForeignKeyWidget(RpmRepository, "name"),
    )

    def before_import_row(self, row, **kwargs):
        """
        Finds and sets distribution tree using upstream_id.

        Args:
            row (tablib.Dataset row): incoming import-row representing a single Variant.
            kwargs: args passed along from the import() call.

        """
        super().before_import_row(row, **kwargs)

        tree = DistributionTree.objects.get(
            upstream_id=row["distribution_tree"], pulp_domain=get_domain()
        )
        row["distribution_tree"] = str(tree.pk)

    def set_up_queryset(self):
        """
        Set up a queryset for RepositoryVersion distribution tree variants.

        Returns:
            django.db.models.QuerySet: The variants contained in the repo version

        """
        tree = DistributionTree.objects.filter(pk__in=self.repo_version.content).first()
        if tree:
            return Variant.objects.filter(distribution_tree=tree).order_by("pulp_id")
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
        fields = ("name", "pulp_type", "description", "user_hidden")


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
        return (
            UpdateCollection.objects.filter(
                update_record__in=UpdateRecord.objects.filter(pk__in=self.repo_version.content)
            )
            .order_by("pulp_id")
            .select_related("update_record")
        )

    class Meta:
        model = UpdateCollection
        exclude = QueryModelResource.Meta.exclude + ("packages",)
        import_id_fields = tuple(chain.from_iterable(UpdateCollection._meta.unique_together))


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
        return (
            UpdateReference.objects.filter(
                update_record__in=UpdateRecord.objects.filter(pk__in=self.repo_version.content)
            )
            .order_by("pulp_id")
            .select_related("update_record")
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

        def render(self, value, obj=None, **kwargs):
            """Render formatted string to use as unique-identifier."""
            return f"{value.name}|{value.update_record.digest}" if value else ""

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
        super().before_import_row(row, **kwargs)

        (uc_name, uc_updrec_digest) = row["update_collection"].split("|")
        uc_updrecord = UpdateRecord.objects.filter(
            digest=uc_updrec_digest, pulp_domain=get_domain()
        ).first()
        uc = UpdateCollection.objects.filter(name=uc_name, update_record=uc_updrecord).first()
        row["update_collection"] = str(uc.pulp_id)

    def get_instance(self, instance_loader, row):
        """
        If all 'import_id_fields' are present in the dataset,
        get instance of UpdateCollectionPackage manually as duplicates
        could appear. Otherwise, returns `None`.
        """
        import_id_fields = [self.fields[f] for f in self.get_import_id_fields()]
        for field in import_id_fields:
            if field.column_name not in row:
                return

        # We need to clear empty values in a row which is a job of `instance_loader`,
        # but we don't call it to avoid failures with usage `get`s.
        # https://github.com/django-import-export/django-import-export/blob/main/import_export/instance_loaders.py#L28
        cleaned_row = {}
        for field in row.keys():
            if row[field]:
                cleaned_row[field] = row[field]

        return UpdateCollectionPackage.objects.filter(**cleaned_row).first()

    def set_up_queryset(self):
        """
        Set up a queryset for UpdateCollectionPackages.

        Returns:
            UpdateCollectionPackages specific to a specified repo-version.

        """
        return (
            UpdateCollectionPackage.objects.filter(
                update_collection__in=UpdateCollection.objects.filter(
                    update_record__in=UpdateRecord.objects.filter(pk__in=self.repo_version.content)
                )
            )
            .order_by("name", "epoch", "version", "release", "arch")
            .select_related("update_collection", "update_collection__update_record")
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
            "update_collection",
        )


class RpmRepositoryResource(RepositoryResource):
    """
    A resource for importing/exporting RPM repository entities.
    """

    def set_up_queryset(self):
        """
        Set up a queryset for RpmRepositories.

        Returns:
            A queryset containing one repository that will be exported.
        """
        return RpmRepository.objects.filter(pk=self.repo_version.repository)

    class Meta:
        model = RpmRepository
        exclude = RepositoryResource.Meta.exclude + ("most_recent_version",)


IMPORT_ORDER = [
    RpmRepositoryResource,
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
