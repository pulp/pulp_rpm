from logging import getLogger

from django.db import models

from pulpcore.plugin.models import Content
from pulpcore.plugin.util import get_domain_pk
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

    _pulp_domain = models.ForeignKey("core.Domain", default=get_domain_pk, on_delete=models.PROTECT)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = ("_pulp_domain", "data_type", "checksum", "relative_path")

    @property
    def unsupported_metadata_type(self):
        """
        Metadata files that are known to contain deltarpm's are unsupported!
        """
        return self.data_type in self.UNSUPPORTED_METADATA
