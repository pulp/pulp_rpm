from gettext import gettext as _

from rest_framework import serializers

from pulpcore.plugin.serializers import ContentSerializer, RemoteSerializer, PublisherSerializer

from pulp_rpm.app.models import Package, RpmRemote, RpmPublisher, UpdateRecord


class PackageSerializer(ContentSerializer):
    """
    A Serializer for Package.

    Add serializers for the new fields defined in Package and add those fields to the Meta class
    keeping fields from the parent class as well. Provide help_text.
    """

    name = serializers.CharField(
        help_text=_("Name of the package"),
    )
    epoch = serializers.CharField(
        help_text=_("The package's epoch"),
    )
    version = serializers.CharField(
        help_text=_("The version of the package. For example, '2.8.0'"),
    )
    release = serializers.CharField(
        help_text=_("The release of a particular version of the package. e.g. '1.el7' or '3.f24'"),
    )
    arch = serializers.CharField(
        help_text=_("The target architecture for a package."
                    "For example, 'x86_64', 'i686', or 'noarch'"),
    )

    pkgId = serializers.CharField(
        help_text=_("Checksum of the package file"),
    )
    checksum_type = serializers.CharField(
        help_text=_("Type of checksum, e.g. 'sha256', 'md5'"),
    )

    summary = serializers.CharField(
        help_text=_("Short description of the packaged software"),
    )
    description = serializers.CharField(
        help_text=_("In-depth description of the packaged software"),
    )
    url = serializers.CharField(
        help_text=_("URL with more information about the packaged software"),
    )

    changelogs = serializers.CharField(
        help_text=_("Changelogs that package contains"),
    )
    files = serializers.CharField(
        help_text=_("Files that package contains"),
    )

    requires = serializers.CharField(
        help_text=_("Capabilities the package requires"),
    )
    provides = serializers.CharField(
        help_text=_("Capabilities the package provides"),
    )
    conflicts = serializers.CharField(
        help_text=_("Capabilities the package conflicts"),
    )
    obsoletes = serializers.CharField(
        help_text=_("Capabilities the package obsoletes"),
    )
    suggests = serializers.CharField(
        help_text=_("Capabilities the package suggests"),
    )
    enhances = serializers.CharField(
        help_text=_("Capabilities the package enhances"),
    )
    recommends = serializers.CharField(
        help_text=_("Capabilities the package recommends"),
    )
    supplements = serializers.CharField(
        help_text=_("Capabilities the package supplements"),
    )

    location_base = serializers.CharField(
        help_text=_("Base location of this package"),
    )
    location_href = serializers.CharField(
        help_text=_("Relative location of package to the repodata"),
    )

    rpm_buildhost = serializers.CharField(
        help_text=_("Hostname of the system that built the package"),
    )
    rpm_group = serializers.CharField(
        help_text=_("RPM group (See: http://fedoraproject.org/wiki/RPMGroups)"),
    )
    rpm_license = serializers.CharField(
        help_text=_("License term applicable to the package software (GPLv2, etc.)"),
    )
    rpm_packager = serializers.CharField(
        help_text=_("Person or persons responsible for creating the package"),
    )
    rpm_sourcerpm = serializers.CharField(
        help_text=_("Name of the source package (srpm) the package was built from"),
    )
    rpm_vendor = serializers.CharField(
        help_text=_("Name of the organization that produced the package"),
    )
    rpm_header_start = serializers.IntegerField(
        help_text=_("First byte of the header"),
    )
    rpm_header_end = serializers.IntegerField(
        help_text=_("Last byte of the header"),
    )

    size_archive = serializers.IntegerField(
        help_text=_("Size, in bytes, of the archive portion of the original package file")
    )
    size_installed = serializers.IntegerField(
        help_text=_("Total size, in bytes, of every file installed by this package")
    )
    size_package = serializers.IntegerField(
        help_text=_("Size, in bytes, of the package")
    )

    time_build = serializers.IntegerField(
        help_text=_("Time the package was built in seconds since the epoch")
    )
    time_file = serializers.IntegerField(
        help_text=_("The 'file' time attribute in the primary XML - "
                    "file mtime in seconds since the epoch.")
    )

    class Meta:
        fields = ContentSerializer.Meta.fields + (
            'name', 'epoch', 'version', 'release', 'arch', 'pkgId', 'checksum_type',
            'summary', 'description', 'url', 'changelogs', 'files',
            'requires', 'provides', 'conflicts', 'obsoletes',
            'suggests', 'enhances', 'recommends', 'supplements',
            'location_base', 'location_href',
            'rpm_buildhost', 'rpm_group', 'rpm_license',
            'rpm_packager', 'rpm_sourcerpm', 'rpm_vendor',
            'rpm_header_start', 'rpm_header_end',
            'size_archive', 'size_installed', 'size_package',
            'time_build', 'time_file'
        )
        model = Package


class MinimalPackageSerializer(PackageSerializer):
    """
    A minimal serializer for RPM packages.
    """

    class Meta:
        fields = ContentSerializer.Meta.fields + (
            'name', 'epoch', 'version', 'release', 'arch', 'pkgId', 'checksum_type',
        )
        model = Package


class RpmRemoteSerializer(RemoteSerializer):
    """
    A Serializer for RpmRemote.
    """

    class Meta:
        fields = RemoteSerializer.Meta.fields
        model = RpmRemote


class RpmPublisherSerializer(PublisherSerializer):
    """
    A Serializer for RpmPublisher.
    """

    class Meta:
        fields = PublisherSerializer.Meta.fields
        model = RpmPublisher


class UpdateRecordSerializer(ContentSerializer):
    """
    A Serializer for UpdateRecord.
    """

    errata_id = serializers.CharField(
        help_text=_("Update id (short update name, e.g. RHEA-2013:1777)")
    )
    updated_date = serializers.CharField(
        help_text=_("Date when the update was updated (e.g. '2013-12-02 00:00:00')")
    )

    description = serializers.CharField(
        help_text=_("Update description")
    )
    issued_date = serializers.CharField(
        help_text=_("Date when the update was issued (e.g. '2013-12-02 00:00:00')")
    )
    fromstr = serializers.CharField(
        help_text=_("Source of the update (e.g. security@redhat.com)")
    )
    status = serializers.CharField(
        help_text=_("Update status ('final', ...)")
    )
    title = serializers.CharField(
        help_text=_("Update name")
    )
    summary = serializers.CharField(
        help_text=_("Short summary")
    )
    version = serializers.CharField(
        help_text=_("Update version (probably always an integer number)")
    )

    update_type = serializers.CharField(
        help_text=_("Update type ('enhancement', 'bugfix', ...)")
    )
    severity = serializers.CharField(
        help_text=_("Severity")
    )
    solution = serializers.CharField(
        help_text=_("Solution")
    )
    release = serializers.CharField(
        help_text=_("Update release")
    )
    rights = serializers.CharField(
        help_text=_("Copyrights")
    )

    pushcount = serializers.CharField(
        help_text=_("Push count")
    )

    class Meta:
        fields = ContentSerializer.Meta.fields + (
            'errata_id', 'updated_date', 'description', 'issued_date',
            'fromstr', 'status', 'title', 'summary', 'version',
            'update_type', 'severity', 'solution', 'release', 'rights',
            'pushcount'
        )
        model = UpdateRecord


class MinimalUpdateRecordSerializer(UpdateRecordSerializer):
    """
    A minimal serializer for RPM update records.
    """

    class Meta:
        fields = ContentSerializer.Meta.fields + (
            'errata_id', 'title', 'severity', 'update_type'
        )
        model = UpdateRecord
