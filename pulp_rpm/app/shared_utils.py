import shutil
import tempfile
from collections import defaultdict
from hashlib import sha256

import createrepo_c as cr
import rpm_rs
from django.conf import settings
from django.utils.dateparse import parse_datetime

from pulp_rpm.app.constants import CR_HEADER_FLAGS
from pulp_rpm.app.rpm_version import RpmVersion


def annotate_with_age(qs):
    """Provide an "age" score for each Package object in the queryset.

    Annotate the Package objects with an "age". Age is calculated by partitioning the
    Packages by name and architecture and ordering the packages in each group by 'evr',
    which is the relative "age" within the group. The newest package gets age=1, second
    newest age=2, and so on.

    A second partition by architecture is important because there can be packages with
    the same name and version numbers but they are not interchangeable because they have
    differing arch, such as 'x86_64' and 'i686', or 'src' (SRPM) and any other arch.
    """
    # Get packages in current queryset with their basic info
    packages = list(qs.values("pk", "name", "arch", "epoch", "version", "release"))

    # Group packages by name and arch
    groups = defaultdict(list)
    for pkg in packages:
        key = (pkg["name"], pkg["arch"])
        groups[key].append(pkg)

    # Calculate age for each group
    age_mapping = {}
    for group_packages in groups.values():
        # Sort by EVR (newest first)
        group_packages.sort(
            key=lambda p: RpmVersion(p["epoch"], p["version"], p["release"]), reverse=True
        )

        # Assign ages (1 = newest, 2 = second newest, etc.)
        for age, pkg in enumerate(group_packages, 1):
            age_mapping[pkg["pk"]] = age

    # Create a queryset with age annotation
    # We'll use a CASE statement to map PKs to ages
    from django.db.models import Case, IntegerField, When

    when_clauses = [When(pk=pk, then=age) for pk, age in age_mapping.items()]

    return qs.annotate(age=Case(*when_clauses, output_field=IntegerField()))


def format_nevra(name=None, epoch=0, version=None, release=None, arch=None):
    """Generate Name-Epoch-Version-Release-Arch string."""
    return "{name}-{epoch}:{version}-{release}.{arch}".format(
        name=name, epoch=epoch, version=version, release=release, arch=arch
    )


def format_nvra(name=None, version=None, release=None, arch=None):
    """Generate Name-Version-Release-Arch from a package metadata."""
    return "{name}-{version}-{release}.{arch}".format(
        name=name,
        version=version,
        release=release,
        arch=arch,
    )


def format_nevra_short(name=None, epoch=0, version=None, release=None, arch=None):
    """Returns NEVRA or NVRA based on epoch."""
    if int(epoch) > 0:
        return format_nevra(name, epoch, version, release, arch)
    return format_nvra(name, version, release, arch)


_VERSION_PREFIX = {
    rpm_rs.SignatureVersion.V4: "v4",
    rpm_rs.SignatureVersion.V6: "v6",
}


def format_signing_keys(signatures):
    """Format rpm_rs signature objects into prefixed fingerprint strings.

    Returns prefixed, uppercased fingerprints (e.g. "v4:ABCD1234...") consistent
    with PgpKeyFingerprintField normalization.
    """
    return [
        f"{_VERSION_PREFIX[sig.version]}:{sig.fingerprint.upper()}"
        for sig in signatures
        if sig.fingerprint is not None
    ]


def extract_signing_keys(path):
    """Extract signing key fingerprints from an RPM file using rpm_rs."""
    pkg = rpm_rs.Package.open(path)
    return format_signing_keys(pkg.signatures())


def read_crpackage_from_artifact(artifact, working_dir="."):
    """
    Helper function for creating package.

    Copy file to a temp directory and parse it.

    Returns: (cr_package, signing_keys) tuple

    Args:
        artifact: inited and validated artifact to save
    """
    filename = f"{artifact.pulp_id}.rpm"
    artifact_file = artifact.pulp_domain.get_storage().open(artifact.file.name)
    with tempfile.NamedTemporaryFile("wb", dir=working_dir, suffix=filename) as temp_file:
        shutil.copyfileobj(artifact_file, temp_file)
        temp_file.flush()
        cr_pkginfo = cr.package_from_rpm(
            temp_file.name,
            changelog_limit=settings.KEEP_CHANGELOG_LIMIT,
            header_reading_flags=CR_HEADER_FLAGS,
        )
        signing_keys = extract_signing_keys(temp_file.name)

    artifact_file.close()
    return cr_pkginfo, signing_keys


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
        for comp_a, comp_b in zip(version_components, target_version_components):
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


def parse_time(value):
    """
    Parse datetime values from a string.

    Able to distinguish between timestamp and iso format.

    Args:
        value(str): unformatted time value

    Returns:
        int | datetime | None: formatted time value
    """
    return int(value) if value.isdigit() else parse_datetime(value)
