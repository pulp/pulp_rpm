"""Utilities for tests for the rpm plugin."""

import dataclasses
import gzip
import hashlib
import os
import tempfile
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple, Optional

import createrepo_c as cr
import pyzstd
import requests
import rpm_rs

from pulp_rpm.tests.functional.constants import (
    PACKAGES_DIRECTORY,
    RPM_NAMESPACES,
)


def gen_rpm_content_attrs(artifact, rpm_name):
    """Generate a dict with content unit attributes.

    :param artifact: A dict of info about the artifact.
    :returns: A semi-random dict for use in creating a content unit.
    """
    return {"artifact": artifact.pulp_href, "relative_path": rpm_name}


def get_package_repo_path(package_filename):
    """Get package repo path with directory structure.

    Args:
        package_filename(str): filename of RPM package

    Returns:
        (str): full path of RPM package in published repository

    """
    return os.path.join(PACKAGES_DIRECTORY, package_filename.lower()[0], package_filename)


def fetch_url(url):
    """Download a URL and return its content bytes, raising on HTTP error."""
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.content


def download_and_decompress_file(url):
    # Tests work normally but fails for S3 due '.gz'
    # Why is it only compressed for S3?
    resp = requests.get(url)
    resp.raise_for_status()
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


def get_metadata_content_helper(base_url, repomd_elem, meta_type):
    """Return the decompressed bytes of a named metadata file from a parsed repomd element.

    Don't use this with large repos because it will blow up.
    """
    xpath_data = "{{{}}}data".format(RPM_NAMESPACES["metadata/repo"])
    data_elems = [e for e in repomd_elem.findall(xpath_data) if e.get("type") == meta_type]
    if not data_elems:
        return None

    xpath_location = "{{{}}}location".format(RPM_NAMESPACES["metadata/repo"])
    location_href = data_elems[0].find(xpath_location).get("href")

    return download_and_decompress_file(os.path.join(base_url, location_href))


class Nevra(NamedTuple):
    name: str
    epoch: int
    version: str
    release: str
    arch: str

    def to_nvra(self) -> str:
        return f"{self.name}-{self.version}-{self.release}.{self.arch}"


SALT = uuid.uuid4().hex


@dataclass
class MetaPackage:
    """Simplified package representation."""

    nevra: Nevra
    digest: str
    time_build: int
    location: str

    @classmethod
    def generate_nevra(cls, n: int) -> Nevra:
        return Nevra(
            name=f"pkg{n}-{SALT[:8]}",
            epoch=0,
            version=f"{n}.0",
            release=f"{n}",
            arch="noarch",
        )

    @classmethod
    def generate_digest(cls, n: int) -> str:
        return hashlib.sha256(f"digest-{SALT}-{n}".encode()).hexdigest()


def build_rpm(nevra: Nevra, path: Path, signer=None) -> None:
    """Build a minimal RPM file at path using rpm_rs.

    If `signer` (an `rpm_rs.Signer`) is given, the package is signed.
    """
    builder = rpm_rs.PackageBuilder(nevra.name, nevra.version, "GPLv2", nevra.arch)
    builder.release(nevra.release)
    if signer is not None:
        builder.build_and_sign(signer).write_file(path)
    else:
        builder.build().write_file(path)


def normalized_location(pkg: MetaPackage, prefix: bool = True) -> MetaPackage:
    """Return a copy of pkg with location set to the canonical NVRA filename."""
    filename = f"{pkg.nevra.to_nvra()}.rpm"
    if prefix:
        filename = f"Packages/{pkg.nevra.name[0]}/{filename}"
    return dataclasses.replace(pkg, location=filename)


@dataclass
class RemoteRepository:
    url: str


class PackageList(list[MetaPackage]):
    """Parsed package list from an RPM repository. Behaves as a list of MetaPackage."""

    def filter(self, name: str) -> "PackageList":
        return PackageList(p for p in self if p.nevra.name == name)


class PackageListFetcher:
    """Builds PackageList instances; wires in the packages API for Pulp-side queries."""

    def __init__(self, rpm_package_api):
        self._rpm_package_api = rpm_package_api

    def from_repository_metadata(self, url: str) -> PackageList:
        """Build from a file:// or http(s):// URL pointing to an RPM repository."""
        if url.startswith("file://"):
            repodata = Path(url[len("file://") :]) / "repodata"
            primary = next(repodata.glob("*primary.xml*"))
            return self._from_path(str(primary))
        return self._from_http_url(url)

    def from_pulp_repoversion(self, repoversion_href: str) -> PackageList:
        """Build from a Pulp repository version using the packages API."""
        response = self._rpm_package_api.list(repository_version=repoversion_href, limit=1000)
        packages = [
            MetaPackage(
                nevra=Nevra(
                    name=pkg.name,
                    epoch=int(pkg.epoch),
                    version=pkg.version,
                    release=pkg.release,
                    arch=pkg.arch,
                ),
                digest=pkg.pkg_id,
                time_build=pkg.time_build,
                location=pkg.location_href,
            )
            for pkg in response.results
        ]
        return PackageList(packages)

    @staticmethod
    def _from_path(path: str) -> PackageList:
        reader = cr.RepositoryReader.from_metadata_files(path, None, None)
        packages_dict = reader.parse_packages(only_primary=True)[0]
        entries = [
            MetaPackage(
                nevra=Nevra(
                    name=p.name,
                    epoch=int(p.epoch),
                    version=p.version,
                    release=p.release,
                    arch=p.arch,
                ),
                digest=p.pkgId,
                time_build=p.time_build,
                location=p.location_href,
            )
            for p in packages_dict.values()
        ]
        return PackageList(entries)

    @staticmethod
    def _from_http_url(base_url: str) -> PackageList:
        repomd_url = base_url.rstrip("/") + "/repodata/repomd.xml"
        repomd = ET.fromstring(fetch_url(repomd_url))
        content = get_metadata_content_helper(base_url, repomd, "primary")
        assert content is not None, "No primary metadata found in repomd.xml"
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
            f.write(content)
            tmp = f.name
        try:
            return PackageListFetcher._from_path(tmp)
        finally:
            os.unlink(tmp)


class RepositoryBuilder:
    """Builds a RPM repository that can be consumed by Pulp."""

    def __init__(self, tmp_path: Path):
        self._tmp_path = tmp_path

    def build(
        self,
        packages: list[MetaPackage],
        base_path: Optional[str] = None,
        real_packages: bool = False,
    ) -> RemoteRepository:
        """Build an RPM repository from a list of MetaPackage descriptors.

        When real_packages is False (default), only repodata XML is generated
        with stub metadata — no actual .rpm files exist on disk.  This is
        sufficient for on_demand sync tests.

        When real_packages is True, a real .rpm file is built for each package
        using rpm_rs and the metadata is derived from the actual RPM headers
        via createrepo_c.  The resulting repo can be synced with any policy.
        """
        base_path = base_path or str(uuid.uuid4())
        repo_dir = self._tmp_path / base_path
        repo_dir.mkdir(parents=True, exist_ok=True)

        if real_packages:
            rpm_paths = []
            for pkg in packages:
                rpm_path = repo_dir / f"{pkg.nevra.to_nvra()}.rpm"
                build_rpm(pkg.nevra, rpm_path)
                rpm_paths.append(rpm_path)

            with cr.RepositoryWriter(str(repo_dir), compression=cr.NO_COMPRESSION) as writer:
                writer.set_num_of_pkgs(len(rpm_paths))
                for rpm_path in rpm_paths:
                    writer.add_pkg_from_file(str(rpm_path))
        else:
            cr_packages = []
            for pkg in packages:
                cr_pkg = cr.Package()
                cr_pkg.name = pkg.nevra.name
                cr_pkg.arch = pkg.nevra.arch
                cr_pkg.epoch = str(pkg.nevra.epoch)
                cr_pkg.version = pkg.nevra.version
                cr_pkg.release = pkg.nevra.release
                cr_pkg.pkgId = pkg.digest
                cr_pkg.checksum_type = "sha256"
                cr_pkg.location_href = pkg.location
                cr_pkg.summary = f"Headless package {pkg.nevra.name}"
                cr_pkg.description = ""
                cr_pkg.size_package = 0
                cr_pkg.size_installed = 0
                cr_pkg.size_archive = 0
                cr_pkg.time_file = 0
                cr_pkg.time_build = pkg.time_build
                cr_pkg.rpm_header_start = 0
                cr_pkg.rpm_header_end = 0
                cr_pkg.rpm_license = ""
                cr_pkg.rpm_vendor = ""
                cr_pkg.rpm_group = ""
                cr_pkg.rpm_buildhost = ""
                cr_pkg.rpm_sourcerpm = ""
                cr_packages.append(cr_pkg)

            with cr.RepositoryWriter(str(repo_dir), compression=cr.NO_COMPRESSION) as writer:
                writer.set_num_of_pkgs(len(cr_packages))
                for cr_pkg in cr_packages:
                    writer.add_pkg(cr_pkg)

        return RemoteRepository(url=f"file://{repo_dir.absolute()}")

    def build_from_files(
        self, rpm_paths: list[Path], base_path: Optional[str] = None
    ) -> RemoteRepository:
        """Build a repo from pre-existing RPM files on disk.

        Unlike build(), this derives all metadata from the actual RPM headers.
        Use this when the RPMs have been modified after creation (e.g. signed).
        """
        base_path = base_path or str(uuid.uuid4())
        repo_dir = self._tmp_path / base_path
        repo_dir.mkdir(parents=True, exist_ok=True)

        with cr.RepositoryWriter(str(repo_dir), compression=cr.NO_COMPRESSION) as writer:
            writer.set_num_of_pkgs(len(rpm_paths))
            for rpm_path in rpm_paths:
                writer.add_pkg_from_file(str(rpm_path))

        return RemoteRepository(url=f"file://{repo_dir.absolute()}")
