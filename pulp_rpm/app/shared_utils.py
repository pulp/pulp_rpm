import createrepo_c
import tempfile
import shutil

from django.core.files.storage import default_storage as storage

from pulp_rpm.app.models import Package


def _prepare_package(artifact, filename):
    """
    Helper function for creating package.

    Copy file to a temp directory under
    the user provided filename.

    Returns: artifact model as dict

    Args:
        artifact: inited and validated artifact to save
        filename: name of file uploaded by user
    """
    artifact_file = storage.open(artifact.file.name)
    with tempfile.NamedTemporaryFile('wb', suffix=filename) as temp_file:
        shutil.copyfileobj(artifact_file, temp_file)
        temp_file.flush()
        cr_pkginfo = createrepo_c.package_from_rpm(temp_file.name)

    package = Package.createrepo_to_dict(cr_pkginfo)

    package['location_href'] = filename
    return package


def is_previous_version(version, target_version):
    """
    Compare version with a target version.

    Able to compare versions with integers only.

    Args:
        version(str): version to compare
        target_version(str): version to compare with

    Returns:
        bool: True if versions are the same or if the version is older than the target version.

    """
    if version is None or target_version is None:
        # if any of the versions are empty, they can't be compared and
        # a target_version need to be picked
        return True

    if version.isdigit() and target_version.isdigit():
        return int(version) <= int(target_version)

    if "." in version and len(version.split(".")) == len(target_version.split(".")):
        ver = version.split(".")
        for index, target in enumerate(target_version.split(".")):
            is_digit = ver[index].isdigit() and target.isdigit()
            if is_digit and int(ver[index]) < int(target):
                return True

        if is_digit:
            return int(ver[index]) <= int(target)

    if version:
        return version == target_version

    return False
