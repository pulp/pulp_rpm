from django.db import DatabaseError
from django.db.utils import IntegrityError
from pulpcore.app.apps import get_plugin_config
from pulpcore.app.models import CreatedResource
from pulpcore.plugin.models import Artifact, MasterModel

from pulp_rpm.app.models.content import RpmPackageSigningService


def sign_and_create(
    app_label, serializer_name, temporary_file_path, signing_service_pk, *args, **kwargs
):
    data = kwargs.pop("data", None)
    context = kwargs.pop("context", {})
    serializer_class = get_plugin_config(app_label).named_serializers[serializer_name]

    # Sign pkg and create Artifact
    package_signing_service = RpmPackageSigningService.objects.get(pk=signing_service_pk)
    package_signing_service.sign(temporary_file_path)

    # Create/Get Artifact
    artifact = Artifact.init_and_validate(temporary_file_path)
    try:
        artifact.save()
    except IntegrityError:
        # if artifact already exists, let's use it
        pulp_domain = context["request"].pulp_domain
        try:
            artifact = Artifact.objects.get(sha256=artifact.sha256, pulp_domain=pulp_domain)
            artifact.touch()
        except (Artifact.DoesNotExist, DatabaseError):
            # the artifact has since been removed from when we first attempted to save it
            artifact.save()
            resource = CreatedResource(content_object=artifact)
            resource.save()
    data["artifact"] = artifact

    # Create Package
    serializer = serializer_class(data=data, context=context)
    serializer.is_valid(raise_exception=True)
    instance = serializer.save()
    if isinstance(instance, MasterModel):
        instance = instance.cast()
    resource = CreatedResource(content_object=instance)
    resource.save()
