from tempfile import NamedTemporaryFile

from pulpcore.plugin.models import Artifact, CreatedResource, PulpTemporaryFile
from pulpcore.plugin.tasking import general_create
from pulpcore.plugin.util import get_url

from pulp_rpm.app.models.content import RpmPackageSigningService


def sign_and_create(
    app_label, serializer_name, signing_service_pk, temporary_file_pk, *args, **kwargs
):
    data = kwargs.pop("data", None)
    context = kwargs.pop("context", {})

    # Get unsigned package file and sign it
    package_signing_service = RpmPackageSigningService.objects.get(pk=signing_service_pk)
    uploaded_package = PulpTemporaryFile.objects.get(pk=temporary_file_pk)
    with NamedTemporaryFile(mode="wb", dir=".", delete=False) as final_package:
        with uploaded_package.file.open() as unsigned_package_file:
            final_package.write(unsigned_package_file.read())
            final_package.flush()
        package_signing_service.sign(final_package.name)

        artifact = Artifact.init_and_validate(final_package.name)
        artifact.save()
        resource = CreatedResource(content_object=artifact)
        resource.save()
    uploaded_package.delete()

    # Create Package content
    data["artifact"] = get_url(artifact)
    general_create(app_label, serializer_name, data=data, context=context, *args, **kwargs)
