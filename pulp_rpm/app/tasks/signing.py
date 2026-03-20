import asyncio
import logging
import re
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile

import createrepo_c as cr
from django.conf import settings

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


def _sign_package(package, signing_service, signing_fingerprint):
    """
    Sign a package or reuse an existing signed result.

    Returns None if already signed with the fingerprint, otherwise a
    tuple of (original_package_id, new_package_id).
    """
    # the viewset is currently already checking (and rejecting) on demand content
    # but in the future we could just download it instead
    content_artifact = package.contentartifact_set.first()
    artifact_obj = content_artifact.artifact
    package_id = str(package.pk)

    with NamedTemporaryFile(mode="wb", dir=".", delete=False) as final_package:
        artifact_file = artifact_obj.file
        _save_file(artifact_file, final_package)

        # check if the package is already signed with our fingerprint
        if _verify_package_fingerprint(final_package.name, signing_fingerprint):
            return None

        # check if the package has been signed in the past with our fingerprint and replace
        # it with the previously-created signed package if so
        if existing_result := RpmPackageSigningResult.objects.filter(
            original_package_sha256=content_artifact.artifact.sha256,
            package_signing_fingerprint=signing_fingerprint,
        ).first():
            return (package_id, str(existing_result.result_package.pk))

        # create a new signed version of the package
        log.info(f"Signing package {package.filename}.")
        signed_package_path = _sign_file(final_package, signing_service, signing_fingerprint)
        # Compute signing keys while the signed file is still on the local filesystem.
        signing_keys = _update_signing_keys(
            str(signed_package_path),
            (package.signing_keys or []) + [signing_fingerprint],
        )
        # Read all updated metadata from the signed RPM
        cr_pkg = cr.package_from_rpm(str(signed_package_path))
        new_pkg_dict = Package.createrepo_to_dict(cr_pkg)
        artifact = _save_artifact(signed_package_path)
        extra_fields = {}
        if settings.RPM_SIGNING_COPY_LABELS:
            extra_fields["pulp_labels"] = package.pulp_labels
        signed_package = Package(
            **new_pkg_dict,
            signing_keys=signing_keys,
            is_modular=package.is_modular,
            **extra_fields,
        )
        signed_package.location_href = signed_package.filename
        signed_package.save()
        ContentArtifact.objects.create(
            artifact=artifact,
            content=signed_package,
            relative_path=content_artifact.relative_path,
        )
        RpmPackageSigningResult.objects.create(
            original_package_sha256=artifact_obj.sha256,
            package_signing_fingerprint=signing_fingerprint,
            result_package=signed_package,
        )

        resource = CreatedResource(content_object=signed_package)
        resource.save()
        log.info(f"Signed package {package.filename}.")
        return (package_id, str(signed_package.pk))


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
    # signing_keys field. if this package is being created then it won't have been previously
    # signed by Pulp.
    context["signing_key"] = signing_fingerprint

    general_create(app_label, serializer_name, data=data, context=context, *args, **kwargs)


def signed_add_and_remove(
    repository_pk, add_content_units, remove_content_units, base_version_pk=None
):
    repo = RpmRepository.objects.get(pk=repository_pk)

    if repo.package_signing_service:
        add_content_units = set(add_content_units)
        packages = list(Package.objects.filter(pk__in=add_content_units).all())

        async def _sign_packages():
            semaphore = asyncio.Semaphore(settings.MAX_PACKAGE_SIGNING_WORKERS)

            async def _bounded_sign(pkg):
                async with semaphore:
                    return await asyncio.to_thread(
                        _sign_package,
                        pkg,
                        repo.package_signing_service,
                        repo.package_signing_fingerprint,
                    )

            return await asyncio.gather(*(_bounded_sign(pkg) for pkg in packages))

        for result in asyncio.run(_sign_packages()):
            if not result:
                continue
            old_id, new_id = result
            add_content_units.discard(old_id)
            add_content_units.add(new_id)

        add_content_units = list(add_content_units)

    return add_and_remove(repository_pk, add_content_units, remove_content_units, base_version_pk)
