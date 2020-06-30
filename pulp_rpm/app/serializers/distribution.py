from gettext import gettext as _

from rest_framework import serializers

from pulpcore.plugin.serializers import (
    ArtifactSerializer,
    MultipleArtifactContentSerializer,
)

from pulp_rpm.app.models import (
    Addon,
    Checksum,
    DistributionTree,
    Image,
    Variant,
)


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
        fields = ("addon_id", "uid", "name", "type", "packages")


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
            "variant_id",
            "uid",
            "name",
            "type",
            "packages",
            "source_packages",
            "source_repository",
            "debug_packages",
            "debug_repository",
            "identity",
        )


class DistributionTreeSerializer(MultipleArtifactContentSerializer):
    """
    DistributionTree serializer.
    """

    header_version = serializers.CharField(help_text=_("Header Version."))
    release_name = serializers.CharField(help_text=_("Release name."))
    release_short = serializers.CharField(help_text=_("Release short name."))
    release_version = serializers.CharField(help_text=_("Release version."))
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

    discnum = serializers.IntegerField(help_text=_("Disc number."), allow_null=True)
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
            "pulp_href",
            "header_version",
            "release_name",
            "release_short",
            "release_version",
            "release_is_layered",
            "base_product_name",
            "base_product_short",
            "base_product_version",
            "arch",
            "build_timestamp",
            "instimage",
            "mainimage",
            "discnum",
            "totaldiscs",
            "addons",
            "checksums",
            "images",
            "variants",
        )
