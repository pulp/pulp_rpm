from gettext import gettext as _

from rest_framework import serializers
from rest_framework.exceptions import NotAcceptable

from pulpcore.plugin.serializers import (
    ContentChecksumSerializer,
    SingleArtifactContentUploadSerializer,
)

from pulp_rpm.app.models import Package
from pulp_rpm.app.shared_utils import _prepare_package


class PackageSerializer(
    SingleArtifactContentUploadSerializer, ContentChecksumSerializer
):
    """
    A Serializer for Package.

    Add serializers for the new fields defined in Package and add those fields to the Meta class
    keeping fields from the parent class as well. Provide help_text.
    """

    name = serializers.CharField(help_text=_("Name of the package"), read_only=True,)
    epoch = serializers.CharField(
        help_text=_("The package's epoch"),
        allow_blank=True,
        required=False,
        read_only=True,
    )
    version = serializers.CharField(
        help_text=_("The version of the package. For example, '2.8.0'"), read_only=True,
    )
    release = serializers.CharField(
        help_text=_(
            "The release of a particular version of the package. e.g. '1.el7' or '3.f24'"
        ),
        read_only=True,
    )
    arch = serializers.CharField(
        help_text=_(
            "The target architecture for a package."
            "For example, 'x86_64', 'i686', or 'noarch'"
        ),
        read_only=True,
    )

    pkgId = serializers.CharField(
        help_text=_("Checksum of the package file"), read_only=True,
    )
    checksum_type = serializers.CharField(
        help_text=_("Type of checksum, e.g. 'sha256', 'md5'"), read_only=True,
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
        help_text=_("Base location of this package"),
        allow_blank=True,
        required=False,
        read_only=True,
    )
    location_href = serializers.CharField(
        help_text=_("Relative location of package to the repodata"), read_only=True,
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
        help_text=_("First byte of the header"), read_only=True,
    )
    rpm_header_end = serializers.IntegerField(
        help_text=_("Last byte of the header"), read_only=True,
    )
    is_modular = serializers.BooleanField(
        help_text=_("Flag to identify if the package is modular"),
        required=False,
        read_only=True,
    )

    size_archive = serializers.IntegerField(
        help_text=_(
            "Size, in bytes, of the archive portion of the original package file"
        ),
        read_only=True,
    )
    size_installed = serializers.IntegerField(
        help_text=_("Total size, in bytes, of every file installed by this package"),
        read_only=True,
    )
    size_package = serializers.IntegerField(
        help_text=_("Size, in bytes, of the package"), read_only=True,
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
            raise NotAcceptable(detail="RPM file cannot be parsed for metadata.")

        attrs = {key: new_pkg[key] for key in Package.natural_key_fields()}
        package = Package.objects.filter(**attrs)

        if package.exists():
            keywords = (
                "name",
                "epoch",
                "version",
                "release",
                "arch",
                "checksum_type",
                "pkgId",
            )
            error_data = ", ".join(
                ["=".join(item) for item in new_pkg.items() if item[0] in keywords]
            )

            raise serializers.ValidationError(
                _("There is already a package with: {values}.").format(
                    values=error_data
                )
            )

        data.update(new_pkg)
        return data

    class Meta:
        fields = SingleArtifactContentUploadSerializer.Meta.fields + (
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
            "sha256",
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
        model = Package


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
