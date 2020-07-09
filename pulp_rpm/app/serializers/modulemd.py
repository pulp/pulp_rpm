from gettext import gettext as _

from rest_framework import serializers

from pulpcore.plugin.serializers import (
    ContentChecksumSerializer,
    DetailRelatedField,
    SingleArtifactContentUploadSerializer,
)

from pulp_rpm.app.models import (
    Modulemd,
    ModulemdDefaults,
    Package,
)


class ModulemdSerializer(
    SingleArtifactContentUploadSerializer, ContentChecksumSerializer
):
    """
    Modulemd serializer.
    """

    name = serializers.CharField(help_text=_("Modulemd name."),)
    stream = serializers.CharField(help_text=_("Stream name."),)
    version = serializers.CharField(help_text=_("Modulemd version."),)
    context = serializers.CharField(help_text=_("Modulemd context."),)
    arch = serializers.CharField(help_text=_("Modulemd architecture."),)
    artifacts = serializers.JSONField(
        help_text=_("Modulemd artifacts."), allow_null=True
    )
    dependencies = serializers.JSONField(
        help_text=_("Modulemd dependencies."), allow_null=True
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
        many=True,
    )

    class Meta:
        fields = SingleArtifactContentUploadSerializer.Meta.fields + (
            "name",
            "stream",
            "version",
            "context",
            "arch",
            "artifacts",
            "dependencies",
            "packages",
            "sha256",
        )
        model = Modulemd


class ModulemdDefaultsSerializer(
    SingleArtifactContentUploadSerializer, ContentChecksumSerializer
):
    """
    ModulemdDefaults serializer.
    """

    module = serializers.CharField(help_text=_("Modulemd name."))
    stream = serializers.CharField(help_text=_("Modulemd default stream."))
    profiles = serializers.JSONField(
        help_text=_("Default profiles for modulemd streams.")
    )

    class Meta:
        fields = SingleArtifactContentUploadSerializer.Meta.fields + (
            "module",
            "stream",
            "profiles",
            "sha256",
        )
        model = ModulemdDefaults
