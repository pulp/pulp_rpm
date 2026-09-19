from gettext import gettext as _

from rest_framework import serializers

from pulpcore.plugin.serializers import IdentityField


class ContentViewPackageSerializer(serializers.Serializer):
    """
    A lightweight representation of a Package for Content View search results.

    Used by the ``packages/`` (typeahead) and ``packages/list/`` search endpoints. Instances
    may originate from any domain the ContentView's Distributions span, so ``pulp_href``
    resolves per-object using each Package's own domain.
    """

    pulp_href = IdentityField(view_name="content-rpm/packages-detail")
    name = serializers.CharField(help_text=_("Name of the package"))
    epoch = serializers.CharField(help_text=_("The package's epoch"))
    version = serializers.CharField(help_text=_("The version of the package"))
    release = serializers.CharField(help_text=_("The release of the package"))
    arch = serializers.CharField(help_text=_("The target architecture for the package"))
    summary = serializers.CharField(help_text=_("Short description of the packaged software"))
    description = serializers.CharField(help_text=_("In-depth description of the package"))
    checksum_type = serializers.CharField(help_text=_("Type of checksum, e.g. 'sha256'"))
    pkgId = serializers.CharField(help_text=_("Checksum of the package file"))
    url = serializers.CharField(help_text=_("URL with more information about the package"))
    location_href = serializers.CharField(help_text=_("Relative location of the package"))
    is_modular = serializers.BooleanField(help_text=_("Whether the package is modular"))


class ContentViewPackageGroupSerializer(serializers.Serializer):
    """A representation of a PackageGroup for Content View search results."""

    pulp_href = IdentityField(view_name="content-rpm/packagegroups-detail")
    id = serializers.CharField(help_text=_("ID of the group"))
    name = serializers.CharField(help_text=_("Name of the group"))
    description = serializers.CharField(help_text=_("Description of the group"))
    packages = serializers.JSONField(help_text=_("The list of packages in this group"))


class ContentViewPackageEnvironmentSerializer(serializers.Serializer):
    """A representation of a PackageEnvironment for Content View search results."""

    pulp_href = IdentityField(view_name="content-rpm/packageenvironments-detail")
    id = serializers.CharField(help_text=_("ID of the environment"))
    name = serializers.CharField(help_text=_("The name of the environment"))
    description = serializers.CharField(help_text=_("The description of the environment"))
    group_ids = serializers.JSONField(help_text=_("A list of group ids"))


class ContentViewUpdateReferenceSerializer(serializers.Serializer):
    """A representation of an UpdateReference, used to surface CVEs on errata search results."""

    href = serializers.CharField(help_text=_("Reference URL"))
    ref_id = serializers.CharField(help_text=_("ID of the reference"))
    title = serializers.CharField(help_text=_("Title of the reference"))
    ref_type = serializers.CharField(help_text=_("Type of the reference, e.g. 'cve'"))


class ContentViewErrataSerializer(serializers.Serializer):
    """A representation of an UpdateRecord (advisory/errata) for Content View search results."""

    pulp_href = IdentityField(view_name="content-rpm/advisories-detail")
    id = serializers.CharField(help_text=_("Update id (e.g. RHEA-2013:1777)"))
    updated_date = serializers.CharField(help_text=_("Date when the update was updated"))
    issued_date = serializers.CharField(help_text=_("Date when the update was issued"))
    description = serializers.CharField(help_text=_("Update description"))
    title = serializers.CharField(help_text=_("Update name"))
    summary = serializers.CharField(help_text=_("Short summary"))
    version = serializers.CharField(help_text=_("Update version"))
    type = serializers.CharField(help_text=_("Update type ('enhancement', 'bugfix', ...)"))
    severity = serializers.CharField(help_text=_("Severity"))
    solution = serializers.CharField(help_text=_("Solution"))
    release = serializers.CharField(help_text=_("Update release"))
    rights = serializers.CharField(help_text=_("Copyrights"))
    reboot_suggested = serializers.BooleanField(help_text=_("Whether a reboot is suggested"))
    cves = serializers.SerializerMethodField(help_text=_("CVE references attached to this errata"))

    def get_cves(self, obj):
        return ContentViewUpdateReferenceSerializer(
            [ref for ref in obj.references.all() if ref.ref_type == "cve"], many=True
        ).data


class ContentViewModuleStreamSerializer(serializers.Serializer):
    """A representation of a Modulemd for Content View search results."""

    pulp_href = IdentityField(view_name="content-rpm/modulemds-detail")
    name = serializers.CharField(help_text=_("Name of the modulemd"))
    stream = serializers.CharField(help_text=_("The modulemd's stream"))
    version = serializers.CharField(help_text=_("The version of the modulemd"))
    context = serializers.CharField(help_text=_("The modulemd's context flag"))
    arch = serializers.CharField(help_text=_("Module artifact architecture"))
    description = serializers.CharField(help_text=_("A verbose description of the module"))
    profiles = serializers.JSONField(help_text=_("Package lists of installable profiles"))
    packages = serializers.SerializerMethodField(help_text=_("Names of packages in this module"))

    def get_packages(self, obj):
        return list(obj.packages.values_list("name", flat=True))
