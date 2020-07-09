from gettext import gettext as _

from rest_framework import serializers

from pulpcore.plugin.serializers import NoArtifactContentSerializer

from pulp_rpm.app.models import (
    PackageCategory,
    PackageEnvironment,
    PackageGroup,
    PackageLangpacks,
)


class PackageGroupSerializer(NoArtifactContentSerializer):
    """
    PackageGroup serializer.
    """

    id = serializers.CharField(help_text=_("PackageGroup id."),)
    default = serializers.BooleanField(
        help_text=_("PackageGroup default."), required=False
    )
    user_visible = serializers.BooleanField(
        help_text=_("PackageGroup user visibility."), required=False
    )
    display_order = serializers.IntegerField(
        help_text=_("PackageGroup display order."), allow_null=True
    )
    name = serializers.CharField(help_text=_("PackageGroup name."), allow_blank=True)
    description = serializers.CharField(
        help_text=_("PackageGroup description."), allow_blank=True
    )
    packages = serializers.JSONField(
        help_text=_("PackageGroup package list."), allow_null=True
    )
    biarch_only = serializers.BooleanField(
        help_text=_("PackageGroup biarch only."), required=False
    )
    desc_by_lang = serializers.JSONField(
        help_text=_("PackageGroup description by language."), allow_null=True
    )
    name_by_lang = serializers.JSONField(
        help_text=_("PackageGroup name by language."), allow_null=True
    )
    digest = serializers.CharField(help_text=_("PackageGroup digest."),)

    class Meta:
        fields = NoArtifactContentSerializer.Meta.fields + (
            "id",
            "default",
            "user_visible",
            "display_order",
            "name",
            "description",
            "packages",
            "biarch_only",
            "desc_by_lang",
            "name_by_lang",
            "digest",
        )
        model = PackageGroup


class PackageCategorySerializer(NoArtifactContentSerializer):
    """
    PackageCategory serializer.
    """

    id = serializers.CharField(help_text=_("Category id."),)
    name = serializers.CharField(help_text=_("Category name."), allow_blank=True)
    description = serializers.CharField(
        help_text=_("Category description."), allow_blank=True
    )
    display_order = serializers.IntegerField(
        help_text=_("Category display order."), allow_null=True
    )
    group_ids = serializers.JSONField(
        help_text=_("Category group list."), allow_null=True
    )
    desc_by_lang = serializers.JSONField(
        help_text=_("Category description by language."), allow_null=True
    )
    name_by_lang = serializers.JSONField(
        help_text=_("Category name by language."), allow_null=True
    )
    digest = serializers.CharField(help_text=_("Category digest."),)

    class Meta:
        fields = NoArtifactContentSerializer.Meta.fields + (
            "id",
            "name",
            "description",
            "display_order",
            "group_ids",
            "desc_by_lang",
            "name_by_lang",
            "digest",
        )
        model = PackageCategory


class PackageEnvironmentSerializer(NoArtifactContentSerializer):
    """
    PackageEnvironment serializer.
    """

    id = serializers.CharField(help_text=_("Environment id."),)
    name = serializers.CharField(help_text=_("Environment name."), allow_blank=True)
    description = serializers.CharField(
        help_text=_("Environment description."), allow_blank=True
    )
    display_order = serializers.IntegerField(
        help_text=_("Environment display order."), allow_null=True
    )
    group_ids = serializers.JSONField(
        help_text=_("Environment group list."), allow_null=True
    )
    option_ids = serializers.JSONField(
        help_text=_("Environment option ids"), allow_null=True
    )
    desc_by_lang = serializers.JSONField(
        help_text=_("Environment description by language."), allow_null=True
    )
    name_by_lang = serializers.JSONField(
        help_text=_("Environment name by language."), allow_null=True
    )
    digest = serializers.CharField(help_text=_("Environment digest."))

    class Meta:
        fields = NoArtifactContentSerializer.Meta.fields + (
            "id",
            "name",
            "description",
            "display_order",
            "group_ids",
            "option_ids",
            "desc_by_lang",
            "name_by_lang",
            "digest",
        )
        model = PackageEnvironment


class PackageLangpacksSerializer(NoArtifactContentSerializer):
    """
    PackageLangpacks serializer.
    """

    matches = serializers.JSONField(help_text=_("Langpacks matches."), allow_null=True)
    digest = serializers.CharField(help_text=_("Langpacks digest."), allow_null=True)

    class Meta:
        fields = NoArtifactContentSerializer.Meta.fields + ("matches", "digest")
        model = PackageLangpacks
