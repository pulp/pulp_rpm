"""Utilities for tests for the rpm plugin."""

import gzip
import os
import subprocess

import pyzstd
import requests

from pulp_rpm.tests.functional.constants import (
    PRIVATE_GPG_KEY_URL,
    PACKAGES_DIRECTORY,
)


def gen_rpm_content_attrs(artifact, rpm_name):
    """Generate a dict with content unit attributes.

    :param artifact: A dict of info about the artifact.
    :returns: A semi-random dict for use in creating a content unit.
    """
    return {"artifact": artifact.pulp_href, "relative_path": rpm_name}


def init_signed_repo_configuration():
    """Initialize the configuration required for verifying a signed repository.

    This function downloads and imports a private GPG key by invoking subprocess
    commands. Then, it creates a new signing service on the fly.
    """
    # download the private key
    priv_key = subprocess.run(
        ("wget", "-q", "-O", "-", PRIVATE_GPG_KEY_URL), stdout=subprocess.PIPE
    ).stdout
    # import the downloaded private key
    subprocess.run(("gpg", "--import"), input=priv_key)

    # set the imported key to the maximum trust level
    key_fingerprint = "0C1A894EBB86AFAE218424CADDEF3019C2D4A8CF"
    completed_process = subprocess.run(("echo", f"{key_fingerprint}:6:"), stdout=subprocess.PIPE)
    subprocess.run(("gpg", "--import-ownertrust"), input=completed_process.stdout)

    # create a new signing service
    utils_dir_path = os.path.dirname(os.path.realpath(__file__))
    signing_script_path = os.path.join(utils_dir_path, "sign-metadata.sh")

    return subprocess.run(
        (
            "pulpcore-manager",
            "add-signing-service",
            "sign-metadata",
            f"{signing_script_path}",
            "pulp-fixture-signing-key",
        )
    )


def get_package_repo_path(package_filename):
    """Get package repo path with directory structure.

    Args:
        package_filename(str): filename of RPM package

    Returns:
        (str): full path of RPM package in published repository

    """
    return os.path.join(PACKAGES_DIRECTORY, package_filename.lower()[0], package_filename)


def download_and_decompress_file(url):
    # Tests work normally but fails for S3 due '.gz'
    # Why is it only compressed for S3?
    resp = requests.get(url)
    decompression = None
    if url.endswith(".gz"):
        decompression = gzip.decompress
    elif url.endswith(".zst"):
        decompression = pyzstd.decompress

    if decompression:
        return decompression(resp.content)
    else:
        # FIXME: fix this as in CI primary/update_info.xml has '.gz' but it is not gzipped
        return resp.content
