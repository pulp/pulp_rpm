from logging import getLogger

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
        static_context (Boolean):
            If True, then the context flag is a string of up to thirteen [a-zA-Z0-9_] characters
            representing a build and runtime configuration for this stream. If False or unset, then
            the context flag is filled in by the buildsystem with a short hash of the module's
            NSV and expanded dependencies.
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
        snippet (Text):
            A string to hold modulemd-obsolete snippet
    """

    TYPE = "modulemd"

    # required metadata
    name = models.TextField()
    stream = models.TextField()
    version = models.TextField()
    context = models.TextField()
    arch = models.TextField()

    static_context = models.BooleanField(null=True)
    dependencies = models.JSONField(default=list)
    artifacts = models.JSONField(default=list)
    packages = models.ManyToManyField(Package)
    profiles = models.JSONField(default=dict)
    description = models.TextField()

    snippet = models.TextField()

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = ("name", "stream", "version", "context", "arch")


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
        snippet (Text):
            A string to hold modulemd-obsolete snippet
    """

    TYPE = "modulemd_defaults"

    module = models.TextField()
    stream = models.TextField()
    profiles = models.JSONField(default=list)
    digest = models.TextField(unique=True)

    snippet = models.TextField()

    repo_key_fields = ("module",)

    @classmethod
    def natural_key_fields(cls):
        """
        Digest is used as a natural key for ModulemdDefaults.
        """
        return ("digest",)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"


class ModulemdObsolete(Content):
    """
    The "Modulemd Obsoletes" content type.

    Fields:
        modified (models.DateTimeField):
            A DateTime field representing last modification of modulemd obsolete.
        reset (Bool):
            A boolean option to reset all previously specified obsoletes
        module (Text):
            A string representing a Name of a module that is EOLed
        stream (Text):
            A string representing a Stream of a module that is EOLed
        context (Text):
            A string representing a Context of a module that is EOLed
        eol_date (models.DateTimeField):
            A DateTime field representing end of life date.
        message (Text):
            A string describing the change, reason, etc.
        obsolete_by (JSON):
            A dict to provide details about the obsoleting module and stream
        snippet (Text):
            A string to hold modulemd-obsolete snippet
    """

    TYPE = "modulemd_obsolete"

    # Mandatory fields
    modified = models.DateTimeField()
    module_name = models.TextField()
    module_stream = models.TextField()
    message = models.TextField()

    # Optional fields
    override_previous = models.BooleanField(null=True)
    module_context = models.TextField(null=True)
    eol_date = models.DateTimeField(null=True)
    obsoleted_by_module_name = models.TextField(null=True)
    obsoleted_by_module_stream = models.TextField(null=True)

    snippet = models.TextField()

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = ("modified", "module_name", "module_stream")
