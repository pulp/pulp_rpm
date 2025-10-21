import createrepo_c as cr
import logging
import traceback
from gettext import gettext as _
from tempfile import TemporaryDirectory

from django.conf import settings
from django.db import DatabaseError
from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers
from rest_framework.exceptions import NotAcceptable

from pulpcore.plugin.models import Artifact
from pulpcore.plugin.serializers import (
    ArtifactSerializer,
    ContentChecksumSerializer,
    SingleArtifactContentUploadSerializer,
)
from pulpcore.plugin.models import UploadChunk
from pulpcore.plugin.files import PulpTemporaryUploadedFile
from tempfile import NamedTemporaryFile
from pulpcore.plugin.util import get_domain_pk

from pulp_rpm.app.models import Package
from pulp_rpm.app.shared_utils import format_nvra, read_crpackage_from_artifact

log = logging.getLogger(__name__)


@extend_schema_serializer(
    deprecate_fields=[
        "location_href",
        "location_base",
    ]
)
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
        allow_blank=True,
        required=False,
        read_only=True,
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
        help_text=_(
            "The target architecture for a package." "For example, 'x86_64', 'i686', or 'noarch'"
        ),
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
        allow_blank=True,
        required=False,
        read_only=True,
    )
    description = serializers.CharField(
        help_text=_("In-depth description of the packaged software"),
        allow_blank=True,
        required=False,
        read_only=True,
    )
    url = serializers.CharField(
        help_text=_("URL with more information about the packaged software"),
        allow_blank=True,
        required=False,
        read_only=True,
    )

    changelogs = serializers.JSONField(
        help_text=_("Changelogs that package contains"),
        default="[]",
        required=False,
        read_only=True,
    )
    files = serializers.JSONField(
        help_text=_("Files that package contains"),
        default="[]",
        required=False,
        read_only=True,
    )

    requires = serializers.JSONField(
        help_text=_("Capabilities the package requires"),
        default="[]",
        required=False,
        read_only=True,
    )
    provides = serializers.JSONField(
        help_text=_("Capabilities the package provides"),
        default="[]",
        required=False,
        read_only=True,
    )
    conflicts = serializers.JSONField(
        help_text=_("Capabilities the package conflicts"),
        default="[]",
        required=False,
        read_only=True,
    )
    obsoletes = serializers.JSONField(
        help_text=_("Capabilities the package obsoletes"),
        default="[]",
        required=False,
        read_only=True,
    )
    suggests = serializers.JSONField(
        help_text=_("Capabilities the package suggests"),
        default="[]",
        required=False,
        read_only=True,
    )
    enhances = serializers.JSONField(
        help_text=_("Capabilities the package enhances"),
        default="[]",
        required=False,
        read_only=True,
    )
    recommends = serializers.JSONField(
        help_text=_("Capabilities the package recommends"),
        default="[]",
        required=False,
        read_only=True,
    )
    supplements = serializers.JSONField(
        help_text=_("Capabilities the package supplements"),
        default="[]",
        required=False,
        read_only=True,
    )

    location_base = serializers.CharField(
        help_text=_(
            "DEPRECATED: Base location of this package. "
            "This field will be removed in a future release of pulp_rpm."
        ),
        allow_blank=True,
        required=False,
        read_only=True,
    )
    location_href = serializers.CharField(
        help_text=_(
            "DEPRECATED: Relative location of package to the repodata. "
            "This field will be removed in a future release of pulp_rpm."
        ),
        read_only=True,
    )

    rpm_buildhost = serializers.CharField(
        help_text=_("Hostname of the system that built the package"),
        allow_blank=True,
        required=False,
        read_only=True,
    )
    rpm_group = serializers.CharField(
        help_text=_("RPM group (See: http://fedoraproject.org/wiki/RPMGroups)"),
        allow_blank=True,
        required=False,
        read_only=True,
    )
    rpm_license = serializers.CharField(
        help_text=_("License term applicable to the package software (GPLv2, etc.)"),
        allow_blank=True,
        required=False,
        read_only=True,
    )
    rpm_packager = serializers.CharField(
        help_text=_("Person or persons responsible for creating the package"),
        allow_blank=True,
        required=False,
        read_only=True,
    )
    rpm_sourcerpm = serializers.CharField(
        help_text=_("Name of the source package (srpm) the package was built from"),
        allow_blank=True,
        required=False,
        read_only=True,
    )
    rpm_vendor = serializers.CharField(
        help_text=_("Name of the organization that produced the package"),
        allow_blank=True,
        required=False,
        read_only=True,
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
        required=False,
        read_only=True,
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
        help_text=_(
            "The 'file' time attribute in the primary XML - "
            "file mtime in seconds since the epoch."
        ),
        read_only=True,
    )

    def __init__(self, *args, **kwargs):
        """Initializer for RpmPackageSerializer."""

        super().__init__(*args, **kwargs)
        if "relative_path" in self.fields:
            self.fields["relative_path"].required = False

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
            new_pkg = Package.createrepo_to_dict(read_crpackage_from_artifact(data["artifact"]))
        except OSError:
            log.info(traceback.format_exc())
            raise NotAcceptable(detail="RPM file cannot be parsed for metadata")

        filename = (
            format_nvra(
                new_pkg["name"],
                new_pkg["version"],
                new_pkg["release"],
                new_pkg["arch"],
            )
            + ".rpm"
        )
        if not data.get("relative_path"):
            data["relative_path"] = filename
            new_pkg["location_href"] = filename
        else:
            new_pkg["location_href"] = data["relative_path"]

        data.update(new_pkg)
        return data

    def retrieve(self, validated_data):
        return Package.objects.filter(
            pkgId=validated_data["pkgId"],
            pulp_domain=get_domain_pk(),
        ).first()

    class Meta:
        fields = (
            ContentChecksumSerializer.Meta.fields
            + SingleArtifactContentUploadSerializer.Meta.fields
            + (
                "name",
                "epoch",
                "version",
                "release",
                "arch",
                "pkgId",
                "checksum_type",
                "summary",
                "description",
                "url",
                "changelogs",
                "files",
                "requires",
                "provides",
                "conflicts",
                "obsoletes",
                "suggests",
                "enhances",
                "recommends",
                "supplements",
                "location_base",
                "location_href",
                "rpm_buildhost",
                "rpm_group",
                "rpm_license",
                "rpm_packager",
                "rpm_sourcerpm",
                "rpm_vendor",
                "rpm_header_start",
                "rpm_header_end",
                "is_modular",
                "size_archive",
                "size_installed",
                "size_package",
                "time_build",
                "time_file",
            )
        )
        model = Package

    def validate(self, data):
        validated_data = super().validate(data)
        sign_package = self.context.get("sign_package", None)
        # choose branch, if not set externally
        if sign_package is None:
            sign_package = bool(
                validated_data.get("repository")
                and validated_data["repository"].package_signing_service
            )
            self.context["sign_package"] = sign_package

        # normal branch
        if sign_package is False:
            return validated_data

        # signing branch
        if not validated_data["repository"].package_signing_fingerprint:
            raise serializers.ValidationError(
                _(
                    "To sign a package on upload, the associated Repository must set both"
                    "'package_signing_service' and 'package_signing_fingerprint'."
                )
            )

        if not validated_data.get("file") and not validated_data.get("upload"):
            raise serializers.ValidationError(
                _("To sign a package on upload, a file or upload must be provided.")
            )

        return validated_data


class MinimalPackageSerializer(PackageSerializer):
    """
    A minimal serializer for RPM packages.
    """

    class Meta:
        fields = SingleArtifactContentUploadSerializer.Meta.fields + (
            "name",
            "epoch",
            "version",
            "release",
            "arch",
            "pkgId",
            "checksum_type",
        )
        model = Package


class PackageUploadSerializer(PackageSerializer):
    """
    Serializer for requests to synchronously upload RPM packages.
    """

    class Meta(PackageSerializer.Meta):
        # This API does not support uploading to a repository.
        # It doesn't support custom relative_path either.
        fields = tuple(
            f for f in PackageSerializer.Meta.fields if f not in ["repository", "relative_path"]
        )
        model = Package
        # Name used for the OpenAPI request object
        ref_name = "RPMPackageUploadSerializer"

    def validate(self, data):

        uploaded_file = data.get("file")
        artifact = data.get("artifact")
        upload = data.get("upload")

        # export META from rpm and prepare dict as saveable format
        try:
            if uploaded_file:
                cr_object = cr.package_from_rpm(
                    uploaded_file.file.name, changelog_limit=settings.KEEP_CHANGELOG_LIMIT
                )
                new_pkg = Package.createrepo_to_dict(cr_object)
            elif upload:
                # Handle chunked upload

                chunks = UploadChunk.objects.filter(upload=upload).order_by("offset")
                with NamedTemporaryFile(
                    mode="ab", dir=settings.WORKING_DIRECTORY, delete=False
                ) as temp_file:
                    for chunk in chunks:
                        temp_file.write(chunk.file.read())
                        chunk.file.close()
                    temp_file.flush()

                # Now we have a file, read metadata from it
                cr_object = cr.package_from_rpm(
                    temp_file.name, changelog_limit=settings.KEEP_CHANGELOG_LIMIT
                )
                new_pkg = Package.createrepo_to_dict(cr_object)

                # Convert to PulpTemporaryUploadedFile for later artifact creation
                data["file"] = PulpTemporaryUploadedFile.from_file(open(temp_file.name, "rb"))
                data.pop("upload")  # Remove upload from data
            elif artifact:
                with TemporaryDirectory(dir=settings.WORKING_DIRECTORY) as working_dir_rel_path:
                    new_pkg = Package.createrepo_to_dict(
                        read_crpackage_from_artifact(artifact, working_dir=working_dir_rel_path)
                    )
        except OSError as e:
            log.info(traceback.format_exc())
            raise NotAcceptable(detail="RPM file cannot be parsed for metadata") from e

        # Get or create the Artifact
        if "file" in data:
            file = data.pop("file")
            # if artifact already exists, let's use it
            try:
                artifact = Artifact.objects.get(
                    sha256=file.hashers["sha256"].hexdigest(), pulp_domain=get_domain_pk()
                )
                if not artifact.pulp_domain.get_storage().exists(artifact.file.name):
                    artifact.file = file
                    artifact.save()
                else:
                    artifact.touch()
            except (Artifact.DoesNotExist, DatabaseError):
                artifact_data = {"file": file}
                serializer = ArtifactSerializer(data=artifact_data)
                serializer.is_valid(raise_exception=True)
                artifact = serializer.save()
            data["artifact"] = artifact

        filename = (
            format_nvra(
                new_pkg["name"],
                new_pkg["version"],
                new_pkg["release"],
                new_pkg["arch"],
            )
            + ".rpm"
        )

        data["relative_path"] = filename
        new_pkg["location_href"] = filename

        data.update(new_pkg)
        return data
