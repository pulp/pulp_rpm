from gettext import gettext as _
from rest_framework import serializers

from pulpcore.plugin.serializers import (
    ContentChecksumSerializer,
    SingleArtifactContentUploadSerializer,
)
from pulpcore.plugin.util import get_domain_pk

from pulp_rpm.app.models import RepoMetadataFile


class RepoMetadataFileSerializer(SingleArtifactContentUploadSerializer, ContentChecksumSerializer):
    """
    RepoMetadataFile serializer.
    """

    data_type = serializers.CharField(help_text=_("Metadata type."))
    checksum_type = serializers.CharField(help_text=_("Checksum type for the file."))
    checksum = serializers.CharField(help_text=_("Checksum for the file."))
    relative_path = serializers.CharField(help_text=_("Relative path of the file."))

    # Mirror unique_together from the Model
    def retrieve(self, validated_data):
        content = RepoMetadataFile.objects.filter(
            data_type=validated_data["data_type"],
            checksum=validated_data["checksum"],
            relative_path=validated_data["relative_path"],
            pulp_domain=get_domain_pk(),
        )
        return content.first()

    class Meta:
        fields = (
            ContentChecksumSerializer.Meta.fields
            + SingleArtifactContentUploadSerializer.Meta.fields
            + (
                "data_type",
                "checksum_type",
                "checksum",
            )
        )
        model = RepoMetadataFile
