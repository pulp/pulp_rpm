from tempfile import NamedTemporaryFile

from pulpcore.app.apps import get_plugin_config
from pulpcore.plugin.models import Artifact, CreatedResource, MasterModel
from pulpcore.plugin.util import extract_pk, get_url

from pulp_rpm.app.models.content import RpmPackageSigningService


def sign_and_create(app_label, serializer_name, signing_service_pk, *args, **kwargs):
    data = kwargs.pop("data", None)
    context = kwargs.pop("context", {})
    serializer_class = get_plugin_config(app_label).named_serializers[serializer_name]
    package_signing_service = RpmPackageSigningService.objects.get(pk=signing_service_pk)

    # Get unsigned packaged from Artifact
    unsigned_artifact = Artifact.objects.get(pk=extract_pk(data["artifact"]))

    with NamedTemporaryFile(mode="wb", dir=".", delete=False) as final_package:
        # Get copy of package
        with unsigned_artifact.file.open() as unsigned_package:
            final_package.write(unsigned_package.read())
            final_package.flush()
        # Sign package
        package_signing_service.sign(final_package.name)
        # Create new artifact from signed package
        artifact = Artifact.init_and_validate(final_package.name)
        artifact.save()
        resource = CreatedResource(content_object=artifact)
        resource.save()

    # Replace data["artifact"] with signed one
    data["artifact"] = get_url(artifact)

    # Create Package
    serializer = serializer_class(data=data, context=context)
    serializer.is_valid(raise_exception=True)
    instance = serializer.save()
    if isinstance(instance, MasterModel):
        instance = instance.cast()
    resource = CreatedResource(content_object=instance)
    resource.save()
