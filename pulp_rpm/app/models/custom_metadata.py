from logging import getLogger

from django.db import models

from pulpcore.plugin.models import Content

log = getLogger(__name__)


class RepoMetadataFile(Content):
    """
    Model for custom/unknown repository metadata.

    Fields:
        data_type (Text):
            Metadata type
        checksum_type (Text):
            Checksum type for the file
        checksum (Text):
            Checksum value for the file

    """

    TYPE = 'repo_metadata_file'

    data_type = models.CharField(max_length=20)
    checksum_type = models.CharField(max_length=6)
    checksum = models.CharField(max_length=128)

    repo_key_fields = ('data_type',)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = ("data_type", "checksum")
