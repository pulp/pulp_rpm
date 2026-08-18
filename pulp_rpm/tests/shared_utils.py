"""Shared utilities for both unit and functional tests."""

import dataclasses
import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import rpm_rs


@dataclass(frozen=True)
class Nevra:
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
    time_build: int = 0
    location: str = ""
    digest: Optional[str] = None
    content: Optional[bytes] = None

    def __post_init__(self):
        if self.location and self.digest is None and self.content is None:
            raise ValueError("Either digest or content must be provided")

    def ignore(self, *fields):
        return tuple(v for f, v in dataclasses.asdict(self).items() if f not in fields)

    def replace(self, **overrides):
        nevra_fields = {f.name for f in dataclasses.fields(Nevra)}
        nevra_overrides = {k: v for k, v in overrides.items() if k in nevra_fields}
        pkg_overrides = {k: v for k, v in overrides.items() if k not in nevra_fields}
        new_nevra = (
            dataclasses.replace(self.nevra, **nevra_overrides) if nevra_overrides else self.nevra
        )
        return dataclasses.replace(self, nevra=new_nevra, **pkg_overrides)

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


def build_rpm(nevra: Nevra, path: Path, *, file_contents: Optional[bytes] = None, signer: Optional[rpm_rs.Signer] = None) -> None:
    """Build a minimal RPM file at path using rpm_rs.

    If `signer` (an `rpm_rs.Signer`) is given, the package is signed.

    If `contents` (bytes) are provided, the RPM will incorporate them as payload.
    """
    builder = rpm_rs.PackageBuilder(nevra.name, nevra.version, "GPLv2", nevra.arch)
    builder.release(nevra.release)
    builder.epoch(nevra.epoch)
    if file_contents is not None:
        builder.with_file_contents(file_contents, rpm_rs.FileOptions.new("/usr/share/data"))
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


class PackageList(list[MetaPackage]):
    """Parsed package list from an RPM repository. Behaves as a list of MetaPackage."""

    def filter(self, name: str) -> "PackageList":
        return PackageList(p for p in self if p.nevra.name == name)
