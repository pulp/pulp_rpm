import logging
import re
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile

from pulpcore.plugin.models import (
    Artifact,
    ContentArtifact,
    CreatedResource,
    PulpTemporaryFile,
    UploadChunk,
    Upload,
)
from pulpcore.plugin.tasking import add_and_remove, general_create
from pulpcore.plugin.util import get_url

from pulp_rpm.app.constants import CHECKSUM_TYPES
from pulp_rpm.app.models.content import RpmPackageSigningResult, RpmPackageSigningService
from pulp_rpm.app.models.package import Package
from pulp_rpm.app.models.repository import RpmRepository


log = logging.getLogger(__name__)


def _save_file(fileobj, final_package):
    with fileobj.file.open() as fd:
        final_package.write(fd.read())
    final_package.flush()


def _save_upload(uploadobj, final_package):
    chunks = UploadChunk.objects.filter(upload=uploadobj).order_by("offset")
    for chunk in chunks:
        final_package.write(chunk.file.read())
        chunk.file.close()
    final_package.flush()


def _verify_package_fingerprint(path, signing_fingerprint):
    """Verify if the package at path is signed with signing_fingerprint or not."""
    completed_process = subprocess.run(
        ("rpm", "-Kv", path),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed_process.stderr:
        raise Exception(
            f"Failed to verify package signature: {completed_process.stdout} "
            f"{completed_process.stderr}."
        )

    # check for `key ID` followed by a string of hex digits
    key_ids = re.findall(r"key ID ([0-9A-Fa-f]+)", completed_process.stdout, re.IGNORECASE)
    # check for `key fingerprint:` followed by a string of hex digits
    fingerprints = re.findall(
        r"key fingerprint:\s*([0-9A-Fa-f]+)", completed_process.stdout, re.IGNORECASE
    )
    for candidate in key_ids + fingerprints:
        if signing_fingerprint.lower().endswith(candidate.lower()):
            return True

    return False


def _update_signing_keys(package_file, keys):
    """Return a filtered list of signing keys verified against the package file.

    Verifies each key in keys against the package file and removes any that are not
    present on the package.
    """
    return [key for key in (keys or []) if _verify_package_fingerprint(package_file, key)]


def _sign_file(package_file, signing_service, signing_fingerprint):
    """Sign a package and return the local path of the signed file."""
    result = signing_service.sign(package_file.name, pubkey_fingerprint=signing_fingerprint)
    signed_package_path = Path(result["rpm_package"])
    if not signed_package_path.exists():
        raise Exception(f"Signing script did not create the signed package: {result}")
    return signed_package_path


def _save_artifact(artifact_path):
    """Save an artifact."""
    artifact = Artifact.init_and_validate(str(artifact_path))
    artifact.save()
    resource = CreatedResource(content_object=artifact)
    resource.save()
    return artifact


def sign_and_create(
    app_label,
    serializer_name,
    signing_service_pk,
    signing_fingerprint,
    temporary_file_pk,
    *args,
    **kwargs,
):
    data = kwargs.pop("data", None)
    context = kwargs.pop("context", {})

    # Get unsigned package file and sign it
    package_signing_service = RpmPackageSigningService.objects.get(pk=signing_service_pk)
    with NamedTemporaryFile(mode="wb", dir=".", delete=False) as final_package:
        try:
            uploaded_package = PulpTemporaryFile.objects.get(pk=temporary_file_pk)
            _save_file(uploaded_package, final_package)
        except PulpTemporaryFile.DoesNotExist:
            uploaded_package = Upload.objects.get(pk=temporary_file_pk)
            _save_upload(uploaded_package, final_package)

        signed_package_path = _sign_file(
            final_package, package_signing_service, signing_fingerprint
        )
        artifact = _save_artifact(signed_package_path)
    uploaded_package.delete()

    # Create Package content
    data["artifact"] = get_url(artifact)
    # The Package serializer validation method have two branches: the signing and non-signing.
    # Here, the package is already signed, so we need to update the context for a proper validation.
    context["sign_package"] = False
    # The request data is immutable when there's an upload, so we can't delete the upload out of the
    # request data like we do for a file.  Instead, we'll delete it here.
    if "upload" in data:
        del data["upload"]

    # set the signing key in the context so that it gets added to the created package's
    # pulp_signing_keys field. if this package is being created then it won't have been previously
    # signed by Pulp.
    context["signing_key"] = signing_fingerprint

    general_create(app_label, serializer_name, data=data, context=context, *args, **kwargs)


def signed_add_and_remove(
    repository_pk, add_content_units, remove_content_units, base_version_pk=None
):
    repo = RpmRepository.objects.get(pk=repository_pk)

    if repo.package_signing_service:
        # sign each package and replace it in the add_content_units list
        for package in Package.objects.filter(pk__in=add_content_units).iterator():
            # the viewset is currently already checking (and rejecting) on demand content
            # but in the future we could just download it instead
            content_artifact = package.contentartifact_set.first()
            artifact_obj = content_artifact.artifact
            package_id = str(package.pk)

            with NamedTemporaryFile(mode="wb", dir=".", delete=False) as final_package:
                artifact_file = artifact_obj.file
                _save_file(artifact_file, final_package)

                # check if the package is already signed with our fingerprint
                if _verify_package_fingerprint(
                    final_package.name, repo.package_signing_fingerprint
                ):
                    continue

                # check if the package has been signed in the past with our fingerprint and replace
                # it with the previously-created signed package if so
                if existing_result := RpmPackageSigningResult.objects.filter(
                    original_package_sha256=content_artifact.artifact.sha256,
                    package_signing_fingerprint=repo.package_signing_fingerprint,
                ).first():
                    while package_id in add_content_units:
                        add_content_units.remove(package_id)
                    add_content_units.append(str(existing_result.result_package.pk))
                    continue

                # create a new signed version of the package
                signed_package_path = _sign_file(
                    final_package, repo.package_signing_service, repo.package_signing_fingerprint
                )
                # Compute signing keys while the signed file is still on the local filesystem.
                signing_keys = _update_signing_keys(
                    str(signed_package_path),
                    (package.pulp_signing_keys or []) + [repo.package_signing_fingerprint],
                )
                artifact = _save_artifact(signed_package_path)
                signed_package = package
                signed_package.pk = None
                signed_package.pulp_id = None
                signed_package.pkgId = artifact.sha256
                signed_package.checksum_type = CHECKSUM_TYPES.SHA256
                signed_package.pulp_signing_keys = signing_keys
                signed_package.save()
                ContentArtifact.objects.create(
                    artifact=artifact,
                    content=signed_package,
                    relative_path=content_artifact.relative_path,
                )
                RpmPackageSigningResult.objects.create(
                    original_package_sha256=artifact_obj.sha256,
                    package_signing_fingerprint=repo.package_signing_fingerprint,
                    result_package=signed_package,
                )

                resource = CreatedResource(content_object=signed_package)
                resource.save()
                while package_id in add_content_units:
                    add_content_units.remove(package_id)
                add_content_units.append(str(signed_package.pk))

    return add_and_remove(repository_pk, add_content_units, remove_content_units, base_version_pk)
