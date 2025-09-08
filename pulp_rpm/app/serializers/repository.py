from gettext import gettext as _

from django.conf import settings
from drf_spectacular.utils import extend_schema_serializer
from jsonschema import Draft7Validator
from pulpcore.plugin.models import (
    AsciiArmoredDetachedSigningService,
    Publication,
    Remote,
    Content,
    RepositoryVersion,
)
from pulpcore.plugin.serializers import (
    DetailRelatedField,
    DistributionSerializer,
    PublicationSerializer,
    RelatedField,
    RemoteSerializer,
    RepositorySerializer,
    RepositorySyncURLSerializer,
    ValidateFieldsMixin,
)
from pulpcore.plugin.util import get_domain, resolve_prn
from rest_framework import serializers

from pulp_rpm.app.constants import (
    ALLOWED_CHECKSUM_ERROR_MSG,
    ALLOWED_PUBLISH_CHECKSUM_ERROR_MSG,
    ALLOWED_PUBLISH_CHECKSUMS,
    CHECKSUM_CHOICES,
    COMPRESSION_CHOICES,
    LAYOUT_CHOICES,
    SKIP_TYPES,
    SYNC_POLICY_CHOICES,
)
from pulp_rpm.app.models import (
    RpmDistribution,
    RpmPackageSigningService,
    RpmPublication,
    RpmRemote,
    RpmRepository,
    UlnRemote,
)
from pulp_rpm.app.schema import COPY_CONFIG_SCHEMA
from urllib.parse import urlparse
from textwrap import dedent

# avoid calling into dynaconf many times
ALLOWED_CONTENT_CHECKSUMS = settings.ALLOWED_CONTENT_CHECKSUMS


@extend_schema_serializer(
    deprecate_fields=[
        "metadata_checksum_type",
        "package_checksum_type",
        "gpgcheck",
        "repo_gpgcheck",
        "sqlite_metadata",
    ]
)
class RpmRepositorySerializer(RepositorySerializer):
    """
    Serializer for Rpm Repositories.
    """

    autopublish = serializers.BooleanField(
        help_text=_(
            "Whether to automatically create publications for new repository versions, "
            "and update any distributions pointing to this repository."
        ),
        default=False,
        required=False,
    )
    metadata_signing_service = RelatedField(
        help_text="A reference to an associated signing service.",
        view_name="signing-services-detail",
        queryset=AsciiArmoredDetachedSigningService.objects.all(),
        many=False,
        required=False,
        allow_null=True,
    )
    package_signing_service = RelatedField(
        help_text="A reference to an associated package signing service.",
        view_name="signing-services-detail",
        queryset=RpmPackageSigningService.objects.all(),
        many=False,
        required=False,
        allow_null=True,
    )
    package_signing_fingerprint = serializers.CharField(
        help_text=_(
            "The pubkey V4 fingerprint (160 bits) to be passed to the package signing service."
            "The signing service will use that on signing operations related to this repository."
        ),
        max_length=40,
        required=False,
        allow_blank=True,
        default="",
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
    checksum_type = serializers.ChoiceField(
        help_text=_("The preferred checksum type during repo publish."),
        choices=CHECKSUM_CHOICES,
        required=False,
        allow_null=True,
    )
    metadata_checksum_type = serializers.ChoiceField(
        help_text=_(
            "REMOVED: The checksum type to use for metadata. Not operational since pulp_rpm "
            "3.30.0 release. Use 'checksum_type' instead."
        ),
        choices=CHECKSUM_CHOICES,
        read_only=True,
    )
    package_checksum_type = serializers.ChoiceField(
        help_text=_(
            "REMOVED: The checksum type for packages. Not operational since pulp_rpm 3.30.0 "
            "release. Use 'checksum_type' instead."
        ),
        choices=CHECKSUM_CHOICES,
        required=False,
        allow_null=True,
        read_only=True,
    )
    compression_type = serializers.ChoiceField(
        help_text=_("The compression type to use for metadata files."),
        choices=COMPRESSION_CHOICES,
        required=False,
        allow_null=True,
    )
    layout = serializers.ChoiceField(
        help_text=_("How to layout the packages within the published repository."),
        choices=LAYOUT_CHOICES,
        required=False,
        allow_null=True,
    )
    gpgcheck = serializers.IntegerField(
        help_text=_(
            "REMOVED: An option specifying whether a client should perform a GPG signature "
            "check on packages. Not operational since pulp_rpm 3.30.0 release. "
            "Set these values using 'repo_config' instead."
        ),
        max_value=1,
        min_value=0,
        read_only=True,
    )
    repo_gpgcheck = serializers.IntegerField(
        help_text=_(
            "REMOVED: An option specifying whether a client should perform a GPG signature "
            "check on the repodata. Not operational since pulp_rpm 3.30.0 release. "
            "Set these values using 'repo_config' instead."
        ),
        max_value=1,
        min_value=0,
        read_only=True,
    )
    sqlite_metadata = serializers.BooleanField(
        help_text=_(
            "REMOVED: An option specifying whether Pulp should generate SQLite metadata. "
            "Not operation since pulp_rpm 3.25.0 release"
        ),
        default=False,
        read_only=True,
    )
    repo_config = serializers.JSONField(
        required=False,
        help_text=_(
            "A JSON document describing the config.repo file Pulp should generate for this repo"
        ),
    )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Import workflow may cause these fields to be stored as "" in the database
        # This ensure the correct type of  None | Enum in the response
        for field in (
            "checksum_type",
            "metadata_checksum_type",
            "package_checksum_type",
            "compression_type",
            "layout",
        ):
            field_data = data.get(field)
            if field_data == "":
                data[field] = None
        # The current API field definition expects empty string for nullable values,
        # but some migration paths can set an empty string to none in the database.
        if "package_signing_fingerprint" in data and data["package_signing_fingerprint"] is None:
            data["package_signing_fingerprint"] = ""
        return data

    def validate(self, data):
        """Validate data."""
        if checksum_type := data.get("checksum_type"):
            if checksum_type not in ALLOWED_CONTENT_CHECKSUMS:
                raise serializers.ValidationError({"checksum_type": _(ALLOWED_CHECKSUM_ERROR_MSG)})

            if checksum_type not in ALLOWED_PUBLISH_CHECKSUMS:
                raise serializers.ValidationError(
                    {"checksum_type": _(ALLOWED_PUBLISH_CHECKSUM_ERROR_MSG)}
                )

        validated_data = super().validate(data)
        return validated_data

    class Meta:
        fields = RepositorySerializer.Meta.fields + (
            "autopublish",
            "metadata_signing_service",
            "package_signing_service",
            "package_signing_fingerprint",
            "retain_package_versions",
            "checksum_type",
            "metadata_checksum_type",
            "package_checksum_type",
            "gpgcheck",
            "repo_gpgcheck",
            "sqlite_metadata",
            "repo_config",
            "compression_type",
            "layout",
        )
        model = RpmRepository


class RpmBaseRemoteSerializer(RemoteSerializer):
    """
    A common base serializer for multiple RPM based remotes.
    """

    policy = serializers.ChoiceField(
        help_text=_(
            "The policy to use when downloading content. The possible values include: "
            "'immediate', 'on_demand', and 'streamed'. 'immediate' is the default."
        ),
        choices=Remote.POLICY_CHOICES,
        default=Remote.IMMEDIATE,
    )


class RpmRemoteSerializer(RpmBaseRemoteSerializer):
    """
    A Serializer for RpmRemote.
    """

    sles_auth_token = serializers.CharField(
        help_text=_("Authentication token for SLES repositories."),
        required=False,
        allow_null=True,
    )

    def validate_url(self, value):
        ALLOWED = ("http", "https", "file")
        protocol = urlparse(value).scheme
        if protocol not in ALLOWED:
            raise serializers.ValidationError(
                f"The url {repr(value)} is not valid. It must start with: {ALLOWED}."
            )
        return value

    class Meta:
        fields = RemoteSerializer.Meta.fields + ("sles_auth_token",)
        model = RpmRemote


class UlnRemoteSerializer(RpmBaseRemoteSerializer):
    """
    A Serializer for UlnRemote.
    """

    username = serializers.CharField(
        help_text=_("Your ULN account username."),
        required=True,
        write_only=True,
    )
    password = serializers.CharField(
        help_text=_("Your ULN account password."),
        required=True,
        write_only=True,
        style={"input_type": "password"},
    )

    url = serializers.CharField(
        help_text=_(
            "The ULN repo URL of the remote content source."
            '"This is "uln://" followed by the channel name. E.g.: "uln://ol7_x86_64_oracle"'
        ),
        required=True,
    )

    uln_server_base_url = serializers.CharField(
        help_text=_(
            "Base URL of the ULN server. If the uln_server_base_url is not provided pulp_rpm will"
            "use the contents of the DEFAULT_ULN_SERVER_BASE_URL setting instead."
        ),
        required=False,
        allow_null=True,
    )

    def validate_url(self, value):
        ALLOWED = ("uln",)
        protocol = urlparse(value).scheme
        if protocol not in ALLOWED:
            raise serializers.ValidationError(
                f"The url {repr(value)} is not valid. It must start with: {ALLOWED}."
            )
        return value

    class Meta:
        fields = RemoteSerializer.Meta.fields + ("uln_server_base_url",)
        model = UlnRemote


@extend_schema_serializer(
    deprecate_fields=[
        "metadata_checksum_type",
        "package_checksum_type",
        "gpgcheck",
        "repo_gpgcheck",
        "sqlite_metadata",
    ]
)
class RpmPublicationSerializer(PublicationSerializer):
    """
    A Serializer for RpmPublication.
    """

    metadata_checksum_type = serializers.ChoiceField(
        help_text=_(
            "REMOVED: The checksum type for metadata. Not operational since pulp_rpm 3.30.0 "
            "release. Use 'checksum_type' instead."
        ),
        choices=CHECKSUM_CHOICES,
        read_only=True,
    )
    package_checksum_type = serializers.ChoiceField(
        help_text=_(
            "REMOVED: The checksum type for packages. Not operational since pulp_rpm 3.30.0 "
            "release. Use 'checksum_type' instead."
        ),
        choices=CHECKSUM_CHOICES,
        read_only=True,
    )
    checkpoint = serializers.BooleanField(required=False)
    checksum_type = serializers.ChoiceField(
        help_text=_("The preferred checksum type used during repo publishes."),
        choices=CHECKSUM_CHOICES,
        required=False,
    )
    compression_type = serializers.ChoiceField(
        help_text=_("The compression type to use for metadata files."),
        choices=COMPRESSION_CHOICES,
        required=False,
    )
    layout = serializers.ChoiceField(
        help_text=_("How to layout the packages within the published repository."),
        choices=LAYOUT_CHOICES,
        required=False,
        allow_null=True,
    )
    gpgcheck = serializers.IntegerField(
        help_text=_(
            "REMOVED: An option specifying whether a client should perform "
            "a GPG signature check on packages. Not operational since pulp_rpm 3.30.0 release. "
            "Set these values using 'repo_config' instead."
        ),
        max_value=1,
        min_value=0,
        read_only=True,
    )
    repo_gpgcheck = serializers.IntegerField(
        help_text=_(
            "REMOVED: An option specifying whether a client should perform "
            "a GPG signature check on the repodata. Not operational since pulp_rpm 3.30.0 release. "
            "Set these values using 'repo_config' instead."
        ),
        max_value=1,
        min_value=0,
        read_only=True,
    )
    sqlite_metadata = serializers.BooleanField(
        help_text=_(
            "REMOVED: An option specifying whether Pulp should generate SQLite metadata. "
            "Not operational since pulp_rpm 3.25.0 release"
        ),
        default=False,
        read_only=True,
    )
    repo_config = serializers.JSONField(
        required=False,
        help_text=_(
            "A JSON document describing the config.repo file Pulp should generate for this repo"
        ),
    )

    def validate(self, data):
        """Validate data."""
        if checksum_type := data.get("checksum_type"):
            if checksum_type not in ALLOWED_CONTENT_CHECKSUMS:
                raise serializers.ValidationError(ALLOWED_CHECKSUM_ERROR_MSG)

            if checksum_type not in ALLOWED_PUBLISH_CHECKSUMS:
                raise serializers.ValidationError(ALLOWED_PUBLISH_CHECKSUM_ERROR_MSG)

        validated_data = super().validate(data)
        return validated_data

    class Meta:
        fields = PublicationSerializer.Meta.fields + (
            "checkpoint",
            "checksum_type",
            "metadata_checksum_type",
            "package_checksum_type",
            "gpgcheck",
            "repo_gpgcheck",
            "sqlite_metadata",
            "repo_config",
            "compression_type",
            "layout",
        )
        model = RpmPublication


class RpmDistributionSerializer(DistributionSerializer):
    """
    Serializer for RPM Distributions.
    """

    publication = DetailRelatedField(
        required=False,
        help_text=_("Publication to be served"),
        view_name_pattern=r"publications(-.*/.*)?-detail",
        queryset=Publication.objects.exclude(complete=False),
        allow_null=True,
    )
    generate_repo_config = serializers.BooleanField(
        default=False,
        required=False,
        help_text=_("An option specifying whether Pulp should generate *.repo files."),
    )
    checkpoint = serializers.BooleanField(required=False)

    class Meta:
        fields = DistributionSerializer.Meta.fields + (
            "publication",
            "generate_repo_config",
            "checkpoint",
        )
        model = RpmDistribution


class RpmRepositorySyncURLSerializer(RepositorySyncURLSerializer):
    """
    Serializer for RPM Sync.
    """

    mirror = serializers.BooleanField(
        required=False,
        allow_null=True,
        help_text=_(
            "DEPRECATED: If ``True``, ``sync_policy`` will default to 'mirror_complete' "
            "instead of 'additive'."
        ),
    )
    sync_policy = serializers.ChoiceField(
        help_text=_(
            "Options: 'additive', 'mirror_complete', 'mirror_content_only'. Default: 'additive'. "
            "Modifies how the sync is performed. 'mirror_complete' will clone the original "
            "metadata and create an automatic publication from it, but comes with some "
            "limitations and does not work for certain repositories. 'mirror_content_only' will "
            "change the repository contents to match the remote but the metadata will be "
            "regenerated and will not be bit-for-bit identical. 'additive' will retain the "
            "existing contents of the repository and add the contents of the repository being "
            "synced."
        ),
        choices=SYNC_POLICY_CHOICES,
        required=False,
        allow_null=True,
    )
    skip_types = serializers.ListField(
        help_text=_("List of content types to skip during sync."),
        required=False,
        default=[],
        child=serializers.ChoiceField([(skip_type, skip_type) for skip_type in SKIP_TYPES]),
    )
    optimize = serializers.BooleanField(
        help_text=_("Whether or not to optimize sync."), required=False, default=True
    )

    def validate(self, data):
        """
        Validate sync parameters.
        """
        data = super().validate(data)

        if "mirror" in data and "sync_policy" in data:
            raise serializers.ValidationError(
                _(
                    "Cannot use 'mirror' and 'sync_policy' options simultaneously. The 'mirror' "
                    "option is deprecated, please use 'sync_policy' only."
                )
            )

        return data


class CopySerializer(ValidateFieldsMixin, serializers.Serializer):
    """
    A serializer for Content Copy API.
    """

    config = serializers.JSONField(
        help_text=_(
            dedent(
                """\
        Content to be copied into the given destinations from the given sources.

        Its a list of dictionaries with the following available fields:

        ```json
        [
          {
            "source_repo_version": <RepositoryVersion [pulp_href|prn]>,
            "dest_repo": <RpmRepository [pulp_href|prn]>,
            "dest_base_version": <int>,
            "content": [<Content [pulp_href|prn]>, ...]
          },
          ...
        ]
        ```

        If domains are enabled, the refered pulp objects must be part of the current domain.

        For usage examples, refer to the advanced copy guide:
        <https://pulpproject.org/pulp_rpm/docs/user/guides/modify/#advanced-copy-workflow>
        """
            )
        ),
    )

    dependency_solving = serializers.BooleanField(
        help_text=_("Also copy dependencies of the content being copied."), default=True
    )

    def validate(self, data):
        """
        Validate that the Serializer contains valid data.

        Make sure the config-JSON matches the config-schema.
        Check for cross-domain references (if domain-enabled).
        """

        def raise_validation(field, domain, id=""):
            id = f"\n{id}" if id else ""
            raise serializers.ValidationError(
                _("The field {} contains object(s) not in {} domain.{}".format(field, domain, id))
            )

        def parse_reference(ref) -> tuple[str, str, bool]:
            """Extract info from prn/href to enable checking domains.

            This is used for:
            1. In case of HREFS, avoid expensive extract_pk(href) to get pks.
            2. HREF and PRNs have different information hardcoded available.
               E.g: RepositoryVerseion HREF has its Repository pk; PRNs have the RepoVer pk.

            Returns a tuple with (pk, class_name, is_prn)
            """
            if ref.startswith("prn:"):
                ref_class, pk = resolve_prn(ref)
                return (pk, ref_class, True)
            # content:    ${BASE}/content/rpm/packages/${UUID}/
            # repository: ${BASE}/repositories/rpm/rpm/${UUID}/
            # repover:    ${BASE}/repositories/rpm/rpm/${UUID}/versions/0/
            url = urlparse(ref).path.strip("/").split("/")
            ref_class = RpmRepository if "/repositories/" in ref else Content
            is_repover_href = url[-1].isdigit() and url[-2] == "versions"
            uuid = url[-3] if is_repover_href else url[-1]
            if len(uuid) < 32:
                raise serializers.ValidationError(
                    _("The href path should end with a uuid pk: {}".format(ref))
                )
            return (uuid, ref_class, False)

        def check_domain(entry, name, curr_domain):
            """Check domain for RpmRepository and RepositoryVersion objects."""
            href_or_prn = entry[name]
            resource_pk, ref_class, is_prn = parse_reference(href_or_prn)
            try:
                if ref_class is RepositoryVersion and is_prn:
                    resource_domain_pk = (
                        RepositoryVersion.objects.select_related("repository")
                        .values("repository__pulp_domain")
                        .get(pk=resource_pk)["repository__pulp_domain"]
                    )
                elif ref_class is RpmRepository:
                    resource_domain_pk = RpmRepository.objects.values("pulp_domain").get(
                        pk=resource_pk
                    )["pulp_domain"]
                else:
                    raise serializers.ValidationError(
                        _(
                            "Expected RpmRepository or RepositoryVersion ref_class. "
                            "Got {} from {}.".format(ref_class, href_or_prn)
                        )
                    )
            except RepositoryVersion.DoesNotExit as e:
                raise serializers.ValidationError from e
            except RpmRepository.DoesNotExit as e:
                raise serializers.ValidationError from e

            if resource_domain_pk != curr_domain.pk:
                raise_validation(name, curr_domain.name, resource_domain_pk)

        def check_cross_domain_config(cfg):
            """Check that all config-elts are in 'our' domain."""
            # copy-cfg is a list of dictionaries.
            # source_repo_version and dest_repo are required fields.
            # Insure curr-domain exists in src/dest/dest_base_version/content-list hrefs
            curr_domain = get_domain()
            for entry in cfg:
                # Check required fields individually
                check_domain(entry, "source_repo_version", curr_domain)
                check_domain(entry, "dest_repo", curr_domain)

                # Check content generically to avoid timeout of multiple calls
                content_list = entry.get("content", None)
                if content_list:
                    content_list = [parse_reference(v)[0] for v in content_list]
                    distinct = (
                        Content.objects.filter(pk__in=content_list).values("pulp_domain").distinct()
                    )
                    domain_ok = (
                        len(distinct) == 1 and distinct.first()["pulp_domain"] == curr_domain.pk
                    )
                    if not domain_ok:
                        raise_validation("content", curr_domain.name)

        super().validate(data)
        if "config" in data:
            # Make sure config is valid JSON
            validator = Draft7Validator(COPY_CONFIG_SCHEMA)

            err = []
            for error in sorted(validator.iter_errors(data["config"]), key=str):
                err.append(error.message)
            if err:
                raise serializers.ValidationError(
                    _("Provided copy criteria is invalid:'{}'".format(err))
                )

            if settings.DOMAIN_ENABLED:
                check_cross_domain_config(data["config"])

        return data
