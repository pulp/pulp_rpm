import copy
import createrepo_c
import json
from gettext import gettext as _

from django.db import IntegrityError
from jsonschema import Draft7Validator
from rest_framework import serializers
from rest_framework.exceptions import NotAcceptable

from pulpcore.plugin.models import (
    AsciiArmoredDetachedSigningService,
    Remote,
)
from pulpcore.plugin.serializers import (
    ArtifactSerializer,
    ContentChecksumSerializer,
    DetailRelatedField,
    ModelSerializer,
    MultipleArtifactContentSerializer,
    NoArtifactContentSerializer,
    PublicationDistributionSerializer,
    PublicationSerializer,
    RepositorySyncURLSerializer,
    RelatedField,
    RemoteSerializer,
    RepositorySerializer,
    SingleArtifactContentUploadSerializer,
    validate_unknown_fields,
)

from pulp_rpm.app.advisory import hash_update_record
from pulp_rpm.app.constants import CHECKSUM_CHOICES, CHECKSUM_TYPES

from pulp_rpm.app.fields import (
    UpdateCollectionPackagesField,
    UpdateReferenceField,
)

from pulp_rpm.app.constants import (
    CR_UPDATE_REFERENCE_ATTRS,
    PULP_UPDATE_COLLECTION_ATTRS,
    PULP_UPDATE_RECORD_ATTRS,
    PULP_UPDATE_REFERENCE_ATTRS,
    SKIP_TYPES
)

from pulp_rpm.app.models import (
    Addon,
    Checksum,
    DistributionTree,
    Image,
    Modulemd,
    ModulemdDefaults,
    Package,
    PackageCategory,
    PackageEnvironment,
    PackageGroup,
    PackageLangpacks,
    RepoMetadataFile,
    RpmDistribution,
    RpmRemote,
    RpmRepository,
    RpmPublication,
    UpdateRecord,
    UpdateCollection,
    Variant,
    UpdateCollectionPackage,
    UpdateReference
)
from pulp_rpm.app.shared_utils import _prepare_package
from pulp_rpm.app.schema import COPY_CONFIG_SCHEMA


class PackageSerializer(SingleArtifactContentUploadSerializer, ContentChecksumSerializer):
    """
    A Serializer for Package.

    Add serializers for the new fields defined in Package and add those fields to the Meta class
    keeping fields from the parent class as well. Provide help_text.
    """

    name = serializers.CharField(
        help_text=_("Name of the package"),
        read_only=True,
    )
    epoch = serializers.CharField(
        help_text=_("The package's epoch"),
        allow_blank=True, required=False, read_only=True,
    )
    version = serializers.CharField(
        help_text=_("The version of the package. For example, '2.8.0'"),
        read_only=True,
    )
    release = serializers.CharField(
        help_text=_("The release of a particular version of the package. e.g. '1.el7' or '3.f24'"),
        read_only=True,
    )
    arch = serializers.CharField(
        help_text=_("The target architecture for a package."
                    "For example, 'x86_64', 'i686', or 'noarch'"),
        read_only=True,
    )

    pkgId = serializers.CharField(
        help_text=_("Checksum of the package file"),
        read_only=True,
    )
    checksum_type = serializers.CharField(
        help_text=_("Type of checksum, e.g. 'sha256', 'md5'"),
        read_only=True,
    )

    summary = serializers.CharField(
        help_text=_("Short description of the packaged software"),
        allow_blank=True, required=False, read_only=True,
    )
    description = serializers.CharField(
        help_text=_("In-depth description of the packaged software"),
        allow_blank=True, required=False, read_only=True,
    )
    url = serializers.CharField(
        help_text=_("URL with more information about the packaged software"),
        allow_blank=True, required=False, read_only=True,
    )

    changelogs = serializers.JSONField(
        help_text=_("Changelogs that package contains"),
        default="[]", required=False, read_only=True,
    )
    files = serializers.JSONField(
        help_text=_("Files that package contains"),
        default="[]", required=False, read_only=True,
    )

    requires = serializers.JSONField(
        help_text=_("Capabilities the package requires"),
        default="[]", required=False, read_only=True,
    )
    provides = serializers.JSONField(
        help_text=_("Capabilities the package provides"),
        default="[]", required=False, read_only=True,
    )
    conflicts = serializers.JSONField(
        help_text=_("Capabilities the package conflicts"),
        default="[]", required=False, read_only=True,
    )
    obsoletes = serializers.JSONField(
        help_text=_("Capabilities the package obsoletes"),
        default="[]", required=False, read_only=True,
    )
    suggests = serializers.JSONField(
        help_text=_("Capabilities the package suggests"),
        default="[]", required=False, read_only=True,
    )
    enhances = serializers.JSONField(
        help_text=_("Capabilities the package enhances"),
        default="[]", required=False, read_only=True,
    )
    recommends = serializers.JSONField(
        help_text=_("Capabilities the package recommends"),
        default="[]", required=False, read_only=True,
    )
    supplements = serializers.JSONField(
        help_text=_("Capabilities the package supplements"),
        default="[]", required=False, read_only=True,
    )

    location_base = serializers.CharField(
        help_text=_("Base location of this package"),
        allow_blank=True, required=False, read_only=True,
    )
    location_href = serializers.CharField(
        help_text=_("Relative location of package to the repodata"),
        read_only=True,
    )

    rpm_buildhost = serializers.CharField(
        help_text=_("Hostname of the system that built the package"),
        allow_blank=True, required=False, read_only=True,
    )
    rpm_group = serializers.CharField(
        help_text=_("RPM group (See: http://fedoraproject.org/wiki/RPMGroups)"),
        allow_blank=True, required=False, read_only=True,
    )
    rpm_license = serializers.CharField(
        help_text=_("License term applicable to the package software (GPLv2, etc.)"),
        allow_blank=True, required=False, read_only=True,
    )
    rpm_packager = serializers.CharField(
        help_text=_("Person or persons responsible for creating the package"),
        allow_blank=True, required=False, read_only=True,
    )
    rpm_sourcerpm = serializers.CharField(
        help_text=_("Name of the source package (srpm) the package was built from"),
        allow_blank=True, required=False, read_only=True,
    )
    rpm_vendor = serializers.CharField(
        help_text=_("Name of the organization that produced the package"),
        allow_blank=True, required=False, read_only=True,
    )
    rpm_header_start = serializers.IntegerField(
        help_text=_("First byte of the header"),
        read_only=True,
    )
    rpm_header_end = serializers.IntegerField(
        help_text=_("Last byte of the header"),
        read_only=True,
    )
    is_modular = serializers.BooleanField(
        help_text=_("Flag to identify if the package is modular"),
        required=False, read_only=True,
    )

    size_archive = serializers.IntegerField(
        help_text=_("Size, in bytes, of the archive portion of the original package file"),
        read_only=True,
    )
    size_installed = serializers.IntegerField(
        help_text=_("Total size, in bytes, of every file installed by this package"),
        read_only=True,
    )
    size_package = serializers.IntegerField(
        help_text=_("Size, in bytes, of the package"),
        read_only=True,
    )

    time_build = serializers.IntegerField(
        help_text=_("Time the package was built in seconds since the epoch"),
        read_only=True,
    )
    time_file = serializers.IntegerField(
        help_text=_("The 'file' time attribute in the primary XML - "
                    "file mtime in seconds since the epoch."),
        read_only=True,
    )

    def deferred_validate(self, data):
        """
        Validate the rpm package data.

        Args:
            data (dict): Data to be validated

        Returns:
            dict: Data that has been validated

        """
        data = super().deferred_validate(data)
        # export META from rpm and prepare dict as saveable format
        try:
            new_pkg = _prepare_package(data["artifact"], data["relative_path"])
        except OSError:
            raise NotAcceptable(detail='RPM file cannot be parsed for metadata.')

        attrs = {key: new_pkg[key] for key in Package.natural_key_fields()}
        package = Package.objects.filter(**attrs)

        if package.exists():
            keywords = ('name', 'epoch', 'version', 'release', 'arch', 'checksum_type', 'pkgId')
            error_data = ", ".join(
                ["=".join(item) for item in new_pkg.items() if item[0] in keywords]
            )

            raise serializers.ValidationError(
                _(
                    "There is already a package with: {values}."
                ).format(values=error_data)
            )

        data.update(new_pkg)
        return data

    class Meta:
        fields = SingleArtifactContentUploadSerializer.Meta.fields + (
            'name', 'epoch', 'version', 'release', 'arch', 'pkgId', 'checksum_type',
            'summary', 'description', 'url', 'changelogs', 'files',
            'requires', 'provides', 'conflicts', 'obsoletes',
            'suggests', 'enhances', 'recommends', 'sha256',
            'supplements', 'location_base', 'location_href',
            'rpm_buildhost', 'rpm_group', 'rpm_license',
            'rpm_packager', 'rpm_sourcerpm', 'rpm_vendor',
            'rpm_header_start', 'rpm_header_end', 'is_modular',
            'size_archive', 'size_installed', 'size_package',
            'time_build', 'time_file'
        )
        model = Package


class MinimalPackageSerializer(PackageSerializer):
    """
    A minimal serializer for RPM packages.
    """

    class Meta:
        fields = SingleArtifactContentUploadSerializer.Meta.fields + (
            'name', 'epoch', 'version', 'release', 'arch', 'pkgId', 'checksum_type',
        )
        model = Package


class RpmRepositorySerializer(RepositorySerializer):
    """
    Serializer for Rpm Repositories.
    """

    metadata_signing_service = serializers.HyperlinkedRelatedField(
        help_text="A reference to an associated signing service.",
        view_name='signing-services-detail',
        queryset=AsciiArmoredDetachedSigningService.objects.all(),
        many=False,
        required=False,
        allow_null=True
    )

    class Meta:
        fields = RepositorySerializer.Meta.fields + ('metadata_signing_service',)
        model = RpmRepository


class RpmRemoteSerializer(RemoteSerializer):
    """
    A Serializer for RpmRemote.
    """

    policy = serializers.ChoiceField(
        help_text="The policy to use when downloading content. The possible values include: "
                  "'immediate', 'on_demand', and 'streamed'. 'immediate' is the default.",
        choices=Remote.POLICY_CHOICES,
        default=Remote.IMMEDIATE
    )

    class Meta:
        fields = RemoteSerializer.Meta.fields
        model = RpmRemote


class RpmPublicationSerializer(PublicationSerializer):
    """
    A Serializer for RpmPublication.
    """

    metadata_checksum_type = serializers.ChoiceField(
        help_text=_("The checksum type for metadata."),
        choices=CHECKSUM_CHOICES,
        default=CHECKSUM_TYPES.SHA256,
    )
    package_checksum_type = serializers.ChoiceField(
        help_text=_("The checksum type for packages."),
        choices=CHECKSUM_CHOICES,
        default=CHECKSUM_TYPES.SHA256,
    )

    class Meta:
        fields = PublicationSerializer.Meta.fields + (
            "metadata_checksum_type", "package_checksum_type"
        )
        model = RpmPublication


class UpdateCollectionSerializer(ModelSerializer):
    """
    A Serializer for UpdateCollection.
    """

    name = serializers.CharField(
        help_text=_("Collection name."),
        allow_blank=True,
        allow_null=True
    )

    shortname = serializers.CharField(
        help_text=_("Collection short name."),
        allow_blank=True,
        allow_null=True
    )

    packages = UpdateCollectionPackagesField(
        source='*', read_only=True,
        help_text=_("List of packages")
    )

    class Meta:
        fields = ("name", "shortname", "packages")
        model = UpdateCollection


class UpdateRecordSerializer(SingleArtifactContentUploadSerializer):
    """
    A Serializer for UpdateRecord.
    """

    id = serializers.CharField(
        help_text=_("Update id (short update name, e.g. RHEA-2013:1777)"),
        read_only=True
    )
    updated_date = serializers.CharField(
        help_text=_("Date when the update was updated (e.g. '2013-12-02 00:00:00')"),
        read_only=True
    )

    description = serializers.CharField(
        help_text=_("Update description"),
        allow_blank=True,
        read_only=True
    )
    issued_date = serializers.CharField(
        help_text=_("Date when the update was issued (e.g. '2013-12-02 00:00:00')"),
        read_only=True
    )
    fromstr = serializers.CharField(
        help_text=_("Source of the update (e.g. security@redhat.com)"),
        allow_blank=True,
        read_only=True
    )
    status = serializers.CharField(
        help_text=_("Update status ('final', ...)"),
        allow_blank=True,
        read_only=True
    )
    title = serializers.CharField(
        help_text=_("Update name"),
        allow_blank=True,
        read_only=True
    )
    summary = serializers.CharField(
        help_text=_("Short summary"),
        allow_blank=True,
        read_only=True
    )
    version = serializers.CharField(
        help_text=_("Update version (probably always an integer number)"),
        allow_blank=True,
        read_only=True
    )

    type = serializers.CharField(
        help_text=_("Update type ('enhancement', 'bugfix', ...)"),
        allow_blank=True,
        read_only=True
    )
    severity = serializers.CharField(
        help_text=_("Severity"),
        allow_blank=True,
        read_only=True
    )
    solution = serializers.CharField(
        help_text=_("Solution"),
        allow_blank=True,
        read_only=True
    )
    release = serializers.CharField(
        help_text=_("Update release"),
        allow_blank=True,
        read_only=True
    )
    rights = serializers.CharField(
        help_text=_("Copyrights"),
        allow_blank=True,
        read_only=True
    )
    pushcount = serializers.CharField(
        help_text=_("Push count"),
        allow_blank=True,
        read_only=True
    )
    reboot_suggested = serializers.BooleanField(
        help_text=_("Reboot suggested"),
        read_only=True
    )
    pkglist = UpdateCollectionSerializer(
        source='collections', read_only=True,
        many=True, help_text=_("List of packages")
    )
    references = UpdateReferenceField(
        source='pk', read_only=True,
        help_text=_("List of references")
    )

    def create(self, validated_data):
        """
        Create UpdateRecord and its subclasses from JSON file.

        Returns:
            UpdateRecord instance

        """
        references = validated_data.pop("references", [])
        pkglist = validated_data.pop("pkglist", [])
        update_collection_packages_to_save = list()
        update_references_to_save = list()
        try:
            update_record = super().create(validated_data)
        except IntegrityError:
            raise serializers.ValidationError("Advisory already exists in Pulp.")

        for collection in pkglist:
            new_coll = copy.deepcopy(collection)
            packages = new_coll.pop("packages", [])
            new_coll[PULP_UPDATE_COLLECTION_ATTRS.SHORTNAME] = new_coll.pop(
                "short", ""
            )
            coll = UpdateCollection(**new_coll)
            coll.save()
            coll.update_record.add(update_record)
            for package in packages:
                pkg = UpdateCollectionPackage(**package)
                try:
                    pkg.sum_type = createrepo_c.checksum_type(pkg.sum_type)
                except TypeError:
                    raise TypeError(f'"{pkg.sum_type}" is not supported.')
                pkg.update_collection = coll
                update_collection_packages_to_save.append(pkg)
        for reference in references:
            new_ref = dict()
            new_ref[PULP_UPDATE_REFERENCE_ATTRS.HREF] = reference.get(
                CR_UPDATE_REFERENCE_ATTRS.HREF, ""
            )
            new_ref[PULP_UPDATE_REFERENCE_ATTRS.ID] = reference.get(
                CR_UPDATE_REFERENCE_ATTRS.ID, ""
            )
            new_ref[PULP_UPDATE_REFERENCE_ATTRS.TITLE] = reference.get(
                CR_UPDATE_REFERENCE_ATTRS.TITLE, ""
            )
            new_ref[PULP_UPDATE_REFERENCE_ATTRS.TYPE] = reference.get(
                CR_UPDATE_REFERENCE_ATTRS.TYPE, ""
            )
            ref = UpdateReference(**new_ref)
            ref.update_record = update_record
            update_references_to_save.append(ref)

        if update_collection_packages_to_save:
            UpdateCollectionPackage.objects.bulk_create(update_collection_packages_to_save)
        if update_references_to_save:
            UpdateReference.objects.bulk_create(update_references_to_save)

        cr_update_record = update_record.to_createrepo_c()
        update_record.digest = hash_update_record(cr_update_record)
        update_record.save()

        return update_record

    def validate(self, data):
        """
        Read a file for a JSON data and validate a UpdateRecord data.

        Also change few fields to match Pulp internals if exists as this is usually handle by
        createrepo_c which is not used here.
        """
        update_record_data = dict()
        if 'file' in data:
            update_record_data.update(json.loads(data['file'].read()))
            update_record_data.update(data)
        elif 'artifact' in data:
            update_record_data.update(json.loads(data['artifact'].file.read()))
            update_record_data.update(data)
        else:
            raise serializers.ValidationError("Only creation with file or artifact is allowed.")

        update_record_data[PULP_UPDATE_RECORD_ATTRS.FROMSTR] = update_record_data.pop(
            'from', update_record_data.get(PULP_UPDATE_RECORD_ATTRS.FROMSTR, "")
        )
        update_record_data[PULP_UPDATE_RECORD_ATTRS.ISSUED_DATE] = update_record_data.pop(
            'issued', update_record_data.get(PULP_UPDATE_RECORD_ATTRS.ISSUED_DATE, "")
        )
        update_record_data[PULP_UPDATE_RECORD_ATTRS.UPDATED_DATE] = update_record_data.pop(
            'updated', update_record_data.get(PULP_UPDATE_RECORD_ATTRS.UPDATED_DATE, "")
        )

        if not update_record_data.get(PULP_UPDATE_RECORD_ATTRS.ID) or \
           not update_record_data.get(PULP_UPDATE_RECORD_ATTRS.UPDATED_DATE) or \
           not update_record_data.get(PULP_UPDATE_RECORD_ATTRS.ISSUED_DATE):
            raise serializers.ValidationError(
                "All '{}', '{}' and '{}' must be specified.".format(
                    PULP_UPDATE_RECORD_ATTRS.ID,
                    PULP_UPDATE_RECORD_ATTRS.UPDATED_DATE,
                    PULP_UPDATE_RECORD_ATTRS.ISSUED_DATE
                )
            )

        validated_data = super().validate(update_record_data)
        return validated_data

    class Meta:
        fields = SingleArtifactContentUploadSerializer.Meta.fields + (
            'id', 'updated_date', 'description', 'issued_date',
            'fromstr', 'status', 'title', 'summary', 'version',
            'type', 'severity', 'solution', 'release', 'rights',
            'pushcount', 'pkglist', 'references', 'reboot_suggested'
        )
        model = UpdateRecord


class MinimalUpdateRecordSerializer(UpdateRecordSerializer):
    """
    A minimal serializer for RPM update records.
    """

    class Meta:
        fields = SingleArtifactContentUploadSerializer.Meta.fields + (
            'id', 'title', 'severity', 'type'
        )
        model = UpdateRecord


class RpmDistributionSerializer(PublicationDistributionSerializer):
    """
    Serializer for RPM Distributions.
    """

    class Meta:
        fields = PublicationDistributionSerializer.Meta.fields
        model = RpmDistribution


class RpmRepositorySyncURLSerializer(RepositorySyncURLSerializer):
    """
    Serializer for RPM Sync.
    """

    skip_types = serializers.ListField(
        help_text=_("List of content types to skip during sync."),
        required=False,
        default=[],
        child=serializers.ChoiceField(
            [(skip_type, skip_type) for skip_type in SKIP_TYPES]
        )
    )
    optimize = serializers.BooleanField(
        help_text=_("Whether or not to optimize sync."),
        required=False,
        default=True
    )


class CopySerializer(serializers.Serializer):
    """
    A serializer for Content Copy API.
    """

    config = serializers.JSONField(
        help_text=_("A JSON document describing sources, destinations, and content to be copied"),
    )

    dependency_solving = serializers.BooleanField(
        help_text=_('Also copy dependencies of the content being copied.'),
        default=True
    )

    def validate(self, data):
        """
        Validate that the Serializer contains valid data.

        Set the RpmRepository based on the RepositoryVersion if only the latter is provided.
        Set the RepositoryVersion based on the RpmRepository if only the latter is provided.
        Convert the human-friendly names of the content types into what Pulp needs to query on.

        """
        super().validate(data)

        if hasattr(self, 'initial_data'):
            validate_unknown_fields(self.initial_data, self.fields)

        if 'config' in data:
            validator = Draft7Validator(COPY_CONFIG_SCHEMA)

            err = []
            for error in sorted(validator.iter_errors(data['config']), key=str):
                err.append(error.message)
            if err:
                raise serializers.ValidationError(
                    _("Provided copy criteria is invalid:'{}'".format(err))
                )

        return data


class PackageGroupSerializer(NoArtifactContentSerializer):
    """
    PackageGroup serializer.
    """

    id = serializers.CharField(
        help_text=_("PackageGroup id."),
    )
    default = serializers.BooleanField(
        help_text=_("PackageGroup default."),
        required=False
    )
    user_visible = serializers.BooleanField(
        help_text=_("PackageGroup user visibility."),
        required=False
    )
    display_order = serializers.IntegerField(
        help_text=_("PackageGroup display order."),
        allow_null=True
    )
    name = serializers.CharField(
        help_text=_("PackageGroup name."),
        allow_blank=True
    )
    description = serializers.CharField(
        help_text=_("PackageGroup description."),
        allow_blank=True
    )
    packages = serializers.JSONField(
        help_text=_("PackageGroup package list."),
        allow_null=True
    )
    biarch_only = serializers.BooleanField(
        help_text=_("PackageGroup biarch only."),
        required=False
    )
    desc_by_lang = serializers.JSONField(
        help_text=_("PackageGroup description by language."),
        allow_null=True
    )
    name_by_lang = serializers.JSONField(
        help_text=_("PackageGroup name by language."),
        allow_null=True
    )
    digest = serializers.CharField(
        help_text=_("PackageGroup digest."),
    )
    related_packages = RelatedField(
        help_text=_("Packages related to this PackageGroup."),
        allow_null=True,
        required=False,
        queryset=Package.objects.all(),
        many=True,
        view_name='content-rpm/packages-detail'
    )

    class Meta:
        fields = NoArtifactContentSerializer.Meta.fields + (
            'id', 'default', 'user_visible', 'display_order',
            'name', 'description', 'packages', 'biarch_only',
            'desc_by_lang', 'name_by_lang', 'digest', 'related_packages'
        )
        model = PackageGroup


class PackageCategorySerializer(NoArtifactContentSerializer):
    """
    PackageCategory serializer.
    """

    id = serializers.CharField(
        help_text=_("Category id."),
    )
    name = serializers.CharField(
        help_text=_("Category name."),
        allow_blank=True
    )
    description = serializers.CharField(
        help_text=_("Category description."),
        allow_blank=True
    )
    display_order = serializers.IntegerField(
        help_text=_("Category display order."),
        allow_null=True
    )
    group_ids = serializers.JSONField(
        help_text=_("Category group list."),
        allow_null=True
    )
    desc_by_lang = serializers.JSONField(
        help_text=_("Category description by language."),
        allow_null=True
    )
    name_by_lang = serializers.JSONField(
        help_text=_("Category name by language."),
        allow_null=True
    )
    digest = serializers.CharField(
        help_text=_("Category digest."),
    )
    packagegroups = RelatedField(
        help_text=_("PackageGroups related to this category."),
        allow_null=True,
        required=False,
        queryset=PackageGroup.objects.all(),
        many=True,
        view_name='content-rpm/packagegroups-detail'
    )

    class Meta:
        fields = NoArtifactContentSerializer.Meta.fields + (
            'id', 'name', 'description', 'display_order',
            'group_ids', 'desc_by_lang', 'name_by_lang', 'digest',
            'packagegroups'
        )
        model = PackageCategory


class PackageEnvironmentSerializer(NoArtifactContentSerializer):
    """
    PackageEnvironment serializer.
    """

    id = serializers.CharField(
        help_text=_("Environment id."),
    )
    name = serializers.CharField(
        help_text=_("Environment name."),
        allow_blank=True
    )
    description = serializers.CharField(
        help_text=_("Environment description."),
        allow_blank=True
    )
    display_order = serializers.IntegerField(
        help_text=_("Environment display order."),
        allow_null=True
    )
    group_ids = serializers.JSONField(
        help_text=_("Environment group list."),
        allow_null=True
    )
    option_ids = serializers.JSONField(
        help_text=_("Environment option ids"),
        allow_null=True
    )
    desc_by_lang = serializers.JSONField(
        help_text=_("Environment description by language."),
        allow_null=True
    )
    name_by_lang = serializers.JSONField(
        help_text=_("Environment name by language."),
        allow_null=True
    )
    digest = serializers.CharField(
        help_text=_("Environment digest.")
    )
    packagegroups = RelatedField(
        help_text=_("Groups related to this Environment."),
        allow_null=True,
        required=False,
        queryset=PackageGroup.objects.all(),
        many=True,
        view_name='content-rpm/packagegroups-detail'
    )
    optionalgroups = RelatedField(
        help_text=_("Groups optionally related to this Environment."),
        allow_null=True,
        required=False,
        queryset=PackageGroup.objects.all(),
        many=True,
        view_name='content-rpm/packagegroups-detail'
    )

    class Meta:
        fields = NoArtifactContentSerializer.Meta.fields + (
            'id', 'name', 'description', 'display_order',
            'group_ids', 'option_ids', 'desc_by_lang', 'name_by_lang',
            'digest', 'packagegroups', 'optionalgroups'
        )
        model = PackageEnvironment


class PackageLangpacksSerializer(NoArtifactContentSerializer):
    """
    PackageLangpacks serializer.
    """

    matches = serializers.JSONField(
        help_text=_("Langpacks matches."),
        allow_null=True
    )
    digest = serializers.CharField(
        help_text=_("Langpacks digest."),
        allow_null=True
    )

    class Meta:
        fields = NoArtifactContentSerializer.Meta.fields + (
            'matches', 'digest'
        )
        model = PackageLangpacks


class ModulemdSerializer(SingleArtifactContentUploadSerializer, ContentChecksumSerializer):
    """
    Modulemd serializer.
    """

    name = serializers.CharField(
        help_text=_("Modulemd name."),
    )
    stream = serializers.CharField(
        help_text=_("Stream name."),
    )
    version = serializers.CharField(
        help_text=_("Modulemd version."),
    )
    context = serializers.CharField(
        help_text=_("Modulemd context."),
    )
    arch = serializers.CharField(
        help_text=_("Modulemd architecture."),
    )
    artifacts = serializers.JSONField(
        help_text=_("Modulemd artifacts."),
        allow_null=True
    )
    dependencies = serializers.JSONField(
        help_text=_("Modulemd dependencies."),
        allow_null=True
    )
    # TODO: The performance of this is not great, there's a noticable difference in response
    # time before/after. Since this will only return Package content hrefs, we might benefit
    # from creating a specialized version of this Field that can skip some of the work.
    packages = DetailRelatedField(
        help_text=_("Modulemd artifacts' packages."),
        allow_null=True,
        required=False,
        queryset=Package.objects.all(),
        view_name="content-rpm/packages-detail",
        many=True
    )

    class Meta:
        fields = SingleArtifactContentUploadSerializer.Meta.fields + (
            'name', 'stream', 'version', 'context', 'arch',
            'artifacts', 'dependencies', 'packages', 'sha256'
        )
        model = Modulemd


class ModulemdDefaultsSerializer(SingleArtifactContentUploadSerializer, ContentChecksumSerializer):
    """
    ModulemdDefaults serializer.
    """

    module = serializers.CharField(
        help_text=_("Modulemd name.")
    )
    stream = serializers.CharField(
        help_text=_("Modulemd default stream.")
    )
    profiles = serializers.JSONField(
        help_text=_("Default profiles for modulemd streams.")
    )

    class Meta:
        fields = SingleArtifactContentUploadSerializer.Meta.fields + (
            'module', 'stream', 'profiles', 'sha256'
        )
        model = ModulemdDefaults


class AddonSerializer(serializers.ModelSerializer):
    """
    Addon serializer.
    """

    addon_id = serializers.CharField(help_text=_("Addon id."))
    uid = serializers.CharField(help_text=_("Addon uid."))
    name = serializers.CharField(help_text=_("Addon name."))
    type = serializers.CharField(help_text=_("Addon type."))
    packages = serializers.CharField(
        help_text=_("Relative path to directory with binary RPMs.")
    )

    class Meta:
        model = Addon
        fields = (
            "addon_id", "uid", "name", "type", "packages"
        )


class ChecksumSerializer(serializers.ModelSerializer):
    """
    Checksum serializer.
    """

    path = serializers.CharField(help_text=_("File path."))
    checksum = serializers.CharField(help_text=_("Checksum for the file."))

    class Meta:
        model = Checksum
        fields = ("path", "checksum")


class ImageSerializer(serializers.ModelSerializer):
    """
    Image serializer.
    """

    name = serializers.CharField(help_text=_("File name."))
    path = serializers.CharField(help_text=_("File path."))
    platforms = serializers.CharField(help_text=_("Compatible platforms."))
    artifact = ArtifactSerializer()

    class Meta:
        model = Image
        fields = ("name", "path", "platforms", "artifact")


class VariantSerializer(serializers.ModelSerializer):
    """
    Variant serializer.
    """

    variant_id = serializers.CharField(help_text=_("Variant id."))
    uid = serializers.CharField(help_text=_("Variant uid."))
    name = serializers.CharField(help_text=_("Variant name."))
    type = serializers.CharField(help_text=_("Variant type."))
    packages = serializers.CharField(
        help_text=_("Relative path to directory with binary RPMs.")
    )
    source_packages = serializers.CharField(
        help_text=_("Relative path to directory with source RPMs.")
    )
    source_repository = serializers.CharField(
        help_text=_("Relative path to YUM repository with source RPMs.")
    )
    debug_packages = serializers.CharField(
        help_text=_("Relative path to directory with debug RPMs.")
    )
    debug_repository = serializers.CharField(
        help_text=_("Relative path to YUM repository with debug RPMs.")
    )
    identity = serializers.CharField(
        help_text=_("Relative path to a pem file that identifies a product.")
    )

    class Meta:
        model = Variant
        fields = (
            "variant_id", "uid", "name", "type", "packages",
            "source_packages", "source_repository", "debug_packages",
            "debug_repository", "identity"
        )


class DistributionTreeSerializer(MultipleArtifactContentSerializer):
    """
    DistributionTree serializer.
    """

    header_version = serializers.CharField(
        help_text=_("Header Version.")
    )
    release_name = serializers.CharField(
        help_text=_("Release name.")
    )
    release_short = serializers.CharField(
        help_text=_("Release short name.")
    )
    release_version = serializers.CharField(
        help_text=_("Release version.")
    )
    release_is_layered = serializers.BooleanField(
        help_text=_("Typically False for an operating system, True otherwise.")
    )

    base_product_name = serializers.CharField(
        help_text=_("Base Product name."), allow_null=True
    )
    base_product_short = serializers.CharField(
        help_text=_("Base Product short name."), allow_null=True
    )
    base_product_version = serializers.CharField(
        help_text=_("Base Product version."), allow_null=True
    )

    arch = serializers.CharField(help_text=_("Tree architecturerch."))
    build_timestamp = serializers.FloatField(help_text=_("Tree build time timestamp."))

    instimage = serializers.CharField(
        help_text=_("Relative path to Anaconda instimage."), allow_null=True
    )
    mainimage = serializers.CharField(
        help_text=_("Relative path to Anaconda stage2 image."), allow_null=True
    )

    discnum = serializers.IntegerField(
        help_text=_("Disc number."), allow_null=True
    )
    totaldiscs = serializers.IntegerField(
        help_text=_("Number of discs in media set."), allow_null=True
    )

    addons = AddonSerializer(many=True)

    checksums = ChecksumSerializer(many=True)

    images = ImageSerializer(many=True)

    variants = VariantSerializer(many=True)

    class Meta:
        model = DistributionTree
        fields = (
            "pulp_href", "header_version", "release_name", "release_short", "release_version",
            "release_is_layered", "base_product_name", "base_product_short",
            "base_product_version", "arch", "build_timestamp", "instimage", "mainimage",
            "discnum", "totaldiscs", "addons", "checksums", "images", "variants"
        )


class RepoMetadataFileSerializer(SingleArtifactContentUploadSerializer, ContentChecksumSerializer):
    """
    RepoMetadataFile serializer.
    """

    data_type = serializers.CharField(
        help_text=_("Metadata type.")
    )
    checksum_type = serializers.CharField(
        help_text=_("Checksum type for the file.")
    )
    checksum = serializers.CharField(
        help_text=_("Checksum for the file.")
    )

    class Meta:
        fields = SingleArtifactContentUploadSerializer.Meta.fields + (
            'data_type', 'checksum_type', 'checksum', 'sha256'
        )
        model = RepoMetadataFile
