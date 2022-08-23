from gettext import gettext as _

from rest_framework import serializers

from pulpcore.plugin.serializers import (
    DetailRelatedField,
    NoArtifactContentSerializer,
)

from pulp_rpm.app.models import (
    Modulemd,
    ModulemdDefaults,
    ModulemdObsolete,
    Package,
)


class ModulemdSerializer(NoArtifactContentSerializer):
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
    static_context = serializers.BooleanField(
        help_text=_("Modulemd static-context flag."),
        required=False,
    )
    context = serializers.CharField(
        help_text=_("Modulemd context."),
    )
    arch = serializers.CharField(
        help_text=_("Modulemd architecture."),
    )
    artifacts = serializers.JSONField(help_text=_("Modulemd artifacts."), allow_null=True)
    dependencies = serializers.JSONField(help_text=_("Modulemd dependencies."), allow_null=True)
    # TODO: The performance of this is not great, there's a noticable difference in response
    # time before/after. Since this will only return Package content hrefs, we might benefit
    # from creating a specialized version of this Field that can skip some of the work.
    description = serializers.CharField(help_text=_("Description of module."))
    packages = DetailRelatedField(
        help_text=_("Modulemd artifacts' packages."),
        allow_null=True,
        required=False,
        queryset=Package.objects.all(),
        view_name="content-rpm/packages-detail",
        many=True,
    )
    profiles = serializers.JSONField(help_text=_("Modulemd profiles."), allow_null=True)
    snippet = serializers.CharField(help_text=_("Modulemd snippet"), write_only=True)

    class Meta:
        fields = NoArtifactContentSerializer.Meta.fields + (
            "name",
            "stream",
            "version",
            "static_context",
            "context",
            "arch",
            "artifacts",
            "dependencies",
            "packages",
            "snippet",
            "profiles",
            "description",
        )
        model = Modulemd


class ModulemdDefaultsSerializer(NoArtifactContentSerializer):
    """
    ModulemdDefaults serializer.
    """

    module = serializers.CharField(help_text=_("Modulemd name."))
    stream = serializers.CharField(help_text=_("Modulemd default stream."))
    profiles = serializers.JSONField(help_text=_("Default profiles for modulemd streams."))
    snippet = serializers.CharField(help_text=_("Modulemd default snippet"), write_only=True)

    class Meta:
        fields = NoArtifactContentSerializer.Meta.fields + (
            "module",
            "stream",
            "profiles",
            "snippet",
        )
        model = ModulemdDefaults


class ModulemdObsoleteSerializer(NoArtifactContentSerializer):
    """
    ModulemdObsolete serializer.
    """

    modified = serializers.DateTimeField(help_text=_("Obsolete modified time."))
    module_name = serializers.CharField(help_text=_("Modulemd name."))
    module_stream = serializers.CharField(help_text=_("Modulemd's stream."))
    message = serializers.CharField(help_text=_("Obsolete description."))

    override_previous = serializers.CharField(
        help_text=_("Reset previous obsoletes."), allow_null=True
    )
    module_context = serializers.CharField(help_text=_("Modulemd's context."), allow_null=True)
    eol_date = serializers.DateTimeField(help_text=_("End of Life date."), allow_null=True)
    obsoleted_by_module_name = serializers.CharField(
        help_text=_("Obsolete by module name."), allow_null=True
    )
    obsoleted_by_module_stream = serializers.CharField(
        help_text=_("Obsolete by module stream."), allow_null=True
    )

    snippet = serializers.CharField(help_text=_("Module Obsolete snippet."), write_only=True)

    class Meta:
        fields = NoArtifactContentSerializer.Meta.fields + (
            "modified",
            "module_name",
            "module_stream",
            "message",
            "override_previous",
            "module_context",
            "eol_date",
            "obsoleted_by_module_name",
            "obsoleted_by_module_stream",
            "snippet",
        )
        model = ModulemdObsolete
