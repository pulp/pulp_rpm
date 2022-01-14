import createrepo_c
import tempfile
import shutil

from hashlib import sha256

from django.conf import settings
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
    with tempfile.NamedTemporaryFile("wb", dir=".", suffix=filename) as temp_file:
        shutil.copyfileobj(artifact_file, temp_file)
        temp_file.flush()
        cr_pkginfo = createrepo_c.package_from_rpm(
            temp_file.name, changelog_limit=settings.KEEP_CHANGELOG_LIMIT
        )

    package = Package.createrepo_to_dict(cr_pkginfo)

    package["location_href"] = filename
    artifact_file.close()
    return package


def urlpath_sanitize(*args):
    """
    Join an arbitrary number of strings into a /-separated path.

    Replaces uses of urljoin() that don't want/need urljoin's subtle semantics.

    Returns: single string provided arguments separated by single-slashes

    Args:
        Arbitrary list of arguments to be join()ed
    """
    segments = []
    for a in args + ("",):
        stripped = a.strip("/")
        if stripped:
            segments.append(stripped)
    return "/".join(segments)


def get_sha256(file_path):
    """
    Get sha256 of file.

    Args:
        file_path(string): path of file

    Returns:
        String: SHA256 of file

    """
    try:
        with open(file_path, "rb") as file_obj:
            return sha256(file_obj.read()).hexdigest()
    except FileNotFoundError:
        return None


def is_previous_version(version, target_version):
    """
    Compare version with a target version.

    Able to compare versions with integers only. Returns False for non-integer/non-1.2.3 versions.

    Args:
        version(str): version to compare
        target_version(str): version to compare with

    Returns:
        bool: True if versions are the same or if the version is older than the target version.

    """
    # if any of the versions are empty, they can't be compared and
    # a target_version need to be picked
    if version is None or target_version is None:
        return True

    # Handle equals
    if version == target_version:
        return True

    # Handle integers
    if version.isdigit() and target_version.isdigit():
        return int(version) <= int(target_version)

    # Handle 1.2.3
    version_components = version.split(".")
    target_version_components = target_version.split(".")

    if len(version_components) == len(target_version_components):
        for (comp_a, comp_b) in zip(version_components, target_version_components):
            if comp_a.isdigit() and comp_b.isdigit():
                # if both strings contain numeric information, convert them to ints and compare
                a = int(comp_a)
                b = int(comp_b)
                if a == b:
                    # this 'place' is equal, move to next
                    continue
                else:
                    # not equal, return comparison
                    return a < b
            else:
                # if one of the versions contains non-numeric information we cannot compare
                return False
        else:
            # All places compared, is_prev=>T if last place is equal
            return int(comp_a) == int(comp_b)
    # len wasn't equal
    return False
