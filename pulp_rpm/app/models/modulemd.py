from logging import getLogger

from django.contrib.postgres.fields import JSONField
from django.db import models

from pulpcore.plugin.models import Content

from pulp_rpm.app.models.package import Package

log = getLogger(__name__)


class Modulemd(Content):
    """
    The "Modulemd" content type. Modularity support.

    Fields:
        name (Text):
            Name of the modulemd
        stream (Text):
            The modulemd's stream
        version (Text):
            The version of the modulemd.
        context (Text):
            The context flag serves to distinguish module builds with the
            same name, stream and version and plays an important role in
            future automatic module stream name expansion.
        arch (Text):
            Module artifact architecture.
        dependencies (Text):
            Module dependencies, if any.
        artifacts (Text):
            Artifacts shipped with this module.
        packages (Text):
            List of Packages connected to this modulemd.
    """

    TYPE = "modulemd"

    # required metadata
    name = models.CharField(max_length=255)
    stream = models.CharField(max_length=255)
    version = models.CharField(max_length=255)
    context = models.CharField(max_length=255)
    arch = models.CharField(max_length=255)

    dependencies = JSONField(default=list)
    artifacts = JSONField(default=list)
    packages = models.ManyToManyField(Package)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = (
            'name', 'stream', 'version', 'context', 'arch'
        )


class ModulemdDefaults(Content):
    """
    The "Modulemd Defaults" content type. Modularity support.

    Fields:
        module (Text):
            Modulemd name.
        stream (Text):
            Modulemd default stream.
        profiles (Text):
            Default profiles for modulemd streams.
        digest (Text):
            Modulemd digest
    """

    TYPE = "modulemd_defaults"

    module = models.CharField(max_length=255)
    stream = models.CharField(max_length=255)
    profiles = JSONField(default=list)

    digest = models.CharField(unique=True, max_length=64)

    repo_key_fields = ('module',)

    @classmethod
    def natural_key_fields(cls):
        """
        Digest is used as a natural key for ModulemdDefaults.
        """
        return ('digest',)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
