from logging import getLogger

from django.db import models

from pulpcore.plugin.models import Content
from pulp_rpm.app.constants import CHECKSUM_CHOICES

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

    TYPE = "repo_metadata_file"
    UNSUPPORTED_METADATA = ["prestodelta", "deltainfo"]

    data_type = models.TextField()
    checksum_type = models.TextField(choices=CHECKSUM_CHOICES)
    checksum = models.TextField()
    relative_path = models.TextField()

    repo_key_fields = ("data_type",)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = ("data_type", "checksum", "relative_path")

    @property
    def unsupported_metadata_type(self):
        """
        Metadata files that are known to contain deltarpm's are unsupported!
        """
        return self.data_type in self.UNSUPPORTED_METADATA
