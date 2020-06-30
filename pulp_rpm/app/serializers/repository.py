from gettext import gettext as _

from jsonschema import Draft7Validator
from rest_framework import serializers

from pulpcore.plugin.models import (
    AsciiArmoredDetachedSigningService,
    Remote,
)
from pulpcore.plugin.serializers import (
    PublicationDistributionSerializer,
    PublicationSerializer,
    RemoteSerializer,
    RepositorySerializer,
    RepositorySyncURLSerializer,
    validate_unknown_fields,
)

from pulp_rpm.app.constants import CHECKSUM_CHOICES, CHECKSUM_TYPES, SKIP_TYPES
from pulp_rpm.app.models import (
    RpmDistribution,
    RpmRemote,
    RpmRepository,
    RpmPublication,
)
from pulp_rpm.app.schema import COPY_CONFIG_SCHEMA


class RpmRepositorySerializer(RepositorySerializer):
    """
    Serializer for Rpm Repositories.
    """

    metadata_signing_service = serializers.HyperlinkedRelatedField(
        help_text="A reference to an associated signing service.",
        view_name="signing-services-detail",
        queryset=AsciiArmoredDetachedSigningService.objects.all(),
        many=False,
        required=False,
        allow_null=True,
    )
    retain_package_versions = serializers.IntegerField(
        help_text=_(
            "The number of versions of each package to keep in the repository; "
            "older versions will be purged. The default is '0', which will disable "
            "this feature and keep all versions of each package."
        ),
        min_value=0,
        required=False,
    )

    class Meta:
        fields = RepositorySerializer.Meta.fields + (
            "metadata_signing_service",
            "retain_package_versions",
        )
        model = RpmRepository


class RpmRemoteSerializer(RemoteSerializer):
    """
    A Serializer for RpmRemote.
    """

    sles_auth_token = serializers.CharField(
        help_text=_("Authentication token for SLES repositories."),
        required=False,
        allow_null=True,
    )

    policy = serializers.ChoiceField(
        help_text=_(
            "The policy to use when downloading content. The possible values include: "
            "'immediate', 'on_demand', and 'streamed'. 'immediate' is the default."
        ),
        choices=Remote.POLICY_CHOICES,
        default=Remote.IMMEDIATE,
    )

    class Meta:
        fields = RemoteSerializer.Meta.fields + ("sles_auth_token",)
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
            "metadata_checksum_type",
            "package_checksum_type",
        )
        model = RpmPublication


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
        ),
    )
    optimize = serializers.BooleanField(
        help_text=_("Whether or not to optimize sync."), required=False, default=True
    )


class CopySerializer(serializers.Serializer):
    """
    A serializer for Content Copy API.
    """

    config = serializers.JSONField(
        help_text=_(
            "A JSON document describing sources, destinations, and content to be copied"
        ),
    )

    dependency_solving = serializers.BooleanField(
        help_text=_("Also copy dependencies of the content being copied."), default=True
    )

    def validate(self, data):
        """
        Validate that the Serializer contains valid data.

        Set the RpmRepository based on the RepositoryVersion if only the latter is provided.
        Set the RepositoryVersion based on the RpmRepository if only the latter is provided.
        Convert the human-friendly names of the content types into what Pulp needs to query on.

        """
        super().validate(data)

        if hasattr(self, "initial_data"):
            validate_unknown_fields(self.initial_data, self.fields)

        if "config" in data:
            validator = Draft7Validator(COPY_CONFIG_SCHEMA)

            err = []
            for error in sorted(validator.iter_errors(data["config"]), key=str):
                err.append(error.message)
            if err:
                raise serializers.ValidationError(
                    _("Provided copy criteria is invalid:'{}'".format(err))
                )

        return data
