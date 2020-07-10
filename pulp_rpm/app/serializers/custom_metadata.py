from gettext import gettext as _
from rest_framework import serializers

from pulpcore.plugin.serializers import (
    ContentChecksumSerializer,
    SingleArtifactContentUploadSerializer,
)

from pulp_rpm.app.models import RepoMetadataFile


class RepoMetadataFileSerializer(
    SingleArtifactContentUploadSerializer, ContentChecksumSerializer
):
    """
    RepoMetadataFile serializer.
    """

    data_type = serializers.CharField(help_text=_("Metadata type."))
    checksum_type = serializers.CharField(help_text=_("Checksum type for the file."))
    checksum = serializers.CharField(help_text=_("Checksum for the file."))
    relative_path = serializers.CharField(help_text=_("Relative path of the file."))

    class Meta:
        fields = SingleArtifactContentUploadSerializer.Meta.fields + (
            "data_type",
            "checksum_type",
            "checksum",
            "sha256"
        )
        model = RepoMetadataFile
