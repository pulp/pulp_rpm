from logging import getLogger

import createrepo_c as cr

from django.contrib.postgres.fields import JSONField
from django.db import models

from pulpcore.plugin.models import Content

from pulp_rpm.app.constants import (
    CHECKSUM_CHOICES,
    CR_PACKAGE_ATTRS,
    PULP_PACKAGE_ATTRS,
)

log = getLogger(__name__)


class Package(Content):
    """
    The "Package" content type. Formerly "rpm" in Pulp 2.

    Maps directly to the fields provided by createrepo_c.
    https://github.com/rpm-software-management/createrepo_c/

    Fields:
        name (Text):
            Name of the package
        epoch (Text):
            The package's epoch
        version (Text):
            The version of the package. For example, '2.8.0'
        release (Text):
            The release of a particular version of the package. Although this field
            can technically be anything, packaging guidelines usually require it to
            be an integer followed by the platform, e.g. '1.el7' or '3.f24'. This field
            is incremented by the packager whenever a new release of the same version
            is created.
        arch (Text):
            The target architecture for a package. For example, 'x86_64', 'i686', or 'noarch'.

        pkgId (Text):
            Checksum of the package file
        checksum_type (Text):
            Type of checksum, e.g. 'sha256', 'md5'

        summary (Text):
            Short description of the packaged software
        description (Text):
            In-depth description of the packaged software
        url (Text):
            URL with more information about the packaged software. This could be the project's
            website or its code repository.

        changelogs (Text):
            Changelogs that package contains - see comments below
        files (Text):
            Files that package contains - see comments below

        requires (Text):
            Capabilities the package requires - see comments below
        provides (Text):
            Capabilities the package provides - see comments below
        conflicts (Text):
            Capabilities the package conflicts with - see comments below
        obsoletes (Text):
            Capabilities the package obsoletes - see comments below
        suggests (Text):
            Capabilities the package suggests - see comments below
        enhances (Text):
            Capabilities the package enhances - see comments below
        recommends (Text):
            Capabilities the package recommends - see comments below
        supplements (Text):
            Capabilities the package supplements - see comments below

        location_base (Text):
            Base location of this package
        location_href (Text):
            Relative location of package to the repodata

        rpm_buildhost (Text):
            Hostname of the system that built the package
        rpm_group (Text):
            RPM group (See: http://fedoraproject.org/wiki/RPMGroups)
        rpm_license (Text):
            License term applicable to the package software (GPLv2, etc.)
        rpm_packager (Text):
            Person or persons responsible for creating the package
        rpm_sourcerpm (Text):
            Name of the source package (srpm) the package was built from
        rpm_vendor (Text):
            Name of the organization that produced the package
        rpm_header_start (BigInteger):
            First byte of the header
        rpm_header_end (BigInteger):
            Last byte of the header
        is_modular (Bool):
            Flag to identify if the package is modular

        size_archive (BigInteger):
            Size, in bytes, of the archive portion of the original package file
        size_installed (BigInteger):
            Total size, in bytes, of every file installed by this package
        size_package (BigInteger):
            Size, in bytes, of the package

        time_build (BigInteger):
             Time the package was built in seconds since the epoch.
        time_file (BigInteger):
            The mtime of the package file in seconds since the epoch; this is the 'file' time
            attribute in the primary XML.
    """

    TYPE = 'package'

    # Required metadata
    name = models.CharField(max_length=255)
    epoch = models.CharField(max_length=10)
    version = models.CharField(max_length=255)
    release = models.CharField(max_length=255)
    arch = models.CharField(max_length=20)

    pkgId = models.CharField(unique=True, max_length=128)  # formerly "checksum" in Pulp 2
    checksum_type = models.CharField(choices=CHECKSUM_CHOICES, max_length=10)

    # Optional metadata
    summary = models.TextField()
    description = models.TextField()
    url = models.TextField()

    # A string containing a JSON-encoded list of dictionaries, each of which represents a single
    # changelog. Each changelog dict contains the following fields:
    #
    #   date (int):     date of changelog - seconds since epoch
    #   author (str):   author of the changelog
    #   changelog (str: changelog text
    changelogs = JSONField(default=list)

    # A string containing a JSON-encoded list of dictionaries, each of which represents a single
    # file. Each file dict contains the following fields:
    #
    #   type (str):     one of "" (regular file), "dir", "ghost"
    #   path (str):     path to file
    #   name (str):     filename
    files = JSONField(default=list)

    # Each of these is a string containing a JSON-encoded list of dictionaries, each of which
    # represents a dependency. Each dependency dict contains the following fields:
    #
    #   name (str):     name
    #   flags (str):    flags
    #   epoch (str):    epoch
    #   version (str):  version
    #   release (str):  release
    #   pre (bool):     preinstall
    requires = JSONField(default=list)
    provides = JSONField(default=list)
    conflicts = JSONField(default=list)
    obsoletes = JSONField(default=list)
    suggests = JSONField(default=list)
    enhances = JSONField(default=list)
    recommends = JSONField(default=list)
    supplements = JSONField(default=list)

    location_base = models.TextField()
    location_href = models.TextField()

    rpm_buildhost = models.TextField()
    rpm_group = models.TextField()
    rpm_license = models.TextField()
    rpm_packager = models.TextField()
    rpm_sourcerpm = models.TextField()
    rpm_vendor = models.TextField()
    rpm_header_start = models.BigIntegerField(null=True)
    rpm_header_end = models.BigIntegerField(null=True)

    size_archive = models.BigIntegerField(null=True)
    size_installed = models.BigIntegerField(null=True)
    size_package = models.BigIntegerField(null=True)

    time_build = models.BigIntegerField(null=True)
    time_file = models.BigIntegerField(null=True)

    # not part of createrepo_c metadata
    is_modular = models.BooleanField(default=False)

    # createrepo_c treats 'nosrc' arch (opensuse specific use) as 'src' so it can seem that two
    # packages are the same when they are not. By adding 'location_href' here we can recognize this.
    # E.g. glibc-2.26.11.3.2.nosrc.rpm vs glibc-2.26.11.3.2.src.rpm
    repo_key_fields = ('name', 'epoch', 'version', 'release', 'arch', 'location_href')

    @property
    def filename(self):
        """
        Create a filename for an RPM based upon its NEVRA information.
        """
        return self.nvra + ".rpm"

    @property
    def nevra(self):
        """
        Package NEVRA string (Name-Epoch-Version-Release-Architecture).
        """
        return "{n}-{e}:{v}-{r}.{a}".format(
            n=self.name, e=self.epoch, v=self.version, r=self.release, a=self.arch)

    @property
    def nvra(self):
        """
        Package NVRA string (Name-Version-Release-Architecture).
        """
        return "{n}-{v}-{r}.{a}".format(
            n=self.name, v=self.version, r=self.release, a=self.arch)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = (
            'name', 'epoch', 'version', 'release', 'arch', 'checksum_type', 'pkgId'
        )

    @classmethod
    def createrepo_to_dict(cls, package):
        """
        Convert createrepo_c package object to dict for instantiating Package object.

        Args:
            package(createrepo_c.Package): a RPM/SRPM package to convert

        Returns:
            dict: all data for RPM/SRPM content creation

        """
        return {
            PULP_PACKAGE_ATTRS.ARCH: getattr(package, CR_PACKAGE_ATTRS.ARCH),
            PULP_PACKAGE_ATTRS.CHANGELOGS: getattr(package, CR_PACKAGE_ATTRS.CHANGELOGS, []),
            PULP_PACKAGE_ATTRS.CHECKSUM_TYPE: getattr(package, CR_PACKAGE_ATTRS.CHECKSUM_TYPE),
            PULP_PACKAGE_ATTRS.CONFLICTS: getattr(package, CR_PACKAGE_ATTRS.CONFLICTS, []),
            PULP_PACKAGE_ATTRS.DESCRIPTION: getattr(package, CR_PACKAGE_ATTRS.DESCRIPTION) or '',
            PULP_PACKAGE_ATTRS.ENHANCES: getattr(package, CR_PACKAGE_ATTRS.ENHANCES, []),
            PULP_PACKAGE_ATTRS.EPOCH: getattr(package, CR_PACKAGE_ATTRS.EPOCH) or '',
            PULP_PACKAGE_ATTRS.FILES: getattr(package, CR_PACKAGE_ATTRS.FILES, []),
            PULP_PACKAGE_ATTRS.LOCATION_BASE: getattr(
                package, CR_PACKAGE_ATTRS.LOCATION_BASE) or '',
            PULP_PACKAGE_ATTRS.LOCATION_HREF: getattr(package, CR_PACKAGE_ATTRS.LOCATION_HREF),
            PULP_PACKAGE_ATTRS.NAME: getattr(package, CR_PACKAGE_ATTRS.NAME),
            PULP_PACKAGE_ATTRS.OBSOLETES: getattr(package, CR_PACKAGE_ATTRS.OBSOLETES, []),
            PULP_PACKAGE_ATTRS.PKGID: getattr(package, CR_PACKAGE_ATTRS.PKGID),
            PULP_PACKAGE_ATTRS.PROVIDES: getattr(package, CR_PACKAGE_ATTRS.PROVIDES, []),
            PULP_PACKAGE_ATTRS.RECOMMENDS: getattr(package, CR_PACKAGE_ATTRS.RECOMMENDS, []),
            PULP_PACKAGE_ATTRS.RELEASE: getattr(package, CR_PACKAGE_ATTRS.RELEASE),
            PULP_PACKAGE_ATTRS.REQUIRES: getattr(package, CR_PACKAGE_ATTRS.REQUIRES, []),
            PULP_PACKAGE_ATTRS.RPM_BUILDHOST: getattr(
                package, CR_PACKAGE_ATTRS.RPM_BUILDHOST) or '',
            PULP_PACKAGE_ATTRS.RPM_GROUP: getattr(package, CR_PACKAGE_ATTRS.RPM_GROUP) or '',
            PULP_PACKAGE_ATTRS.RPM_HEADER_END: getattr(package, CR_PACKAGE_ATTRS.RPM_HEADER_END),
            PULP_PACKAGE_ATTRS.RPM_HEADER_START: getattr(
                package, CR_PACKAGE_ATTRS.RPM_HEADER_START),
            PULP_PACKAGE_ATTRS.RPM_LICENSE: getattr(package, CR_PACKAGE_ATTRS.RPM_LICENSE) or '',
            PULP_PACKAGE_ATTRS.RPM_PACKAGER: getattr(package, CR_PACKAGE_ATTRS.RPM_PACKAGER) or '',
            PULP_PACKAGE_ATTRS.RPM_SOURCERPM: getattr(
                package, CR_PACKAGE_ATTRS.RPM_SOURCERPM) or '',
            PULP_PACKAGE_ATTRS.RPM_VENDOR: getattr(package, CR_PACKAGE_ATTRS.RPM_VENDOR) or '',
            PULP_PACKAGE_ATTRS.SIZE_ARCHIVE: getattr(package, CR_PACKAGE_ATTRS.SIZE_ARCHIVE),
            PULP_PACKAGE_ATTRS.SIZE_INSTALLED: getattr(package, CR_PACKAGE_ATTRS.SIZE_INSTALLED),
            PULP_PACKAGE_ATTRS.SIZE_PACKAGE: getattr(package, CR_PACKAGE_ATTRS.SIZE_PACKAGE),
            PULP_PACKAGE_ATTRS.SUGGESTS: getattr(package, CR_PACKAGE_ATTRS.SUGGESTS, []),
            PULP_PACKAGE_ATTRS.SUMMARY: getattr(package, CR_PACKAGE_ATTRS.SUMMARY) or '',
            PULP_PACKAGE_ATTRS.SUPPLEMENTS: getattr(package, CR_PACKAGE_ATTRS.SUPPLEMENTS, []),
            PULP_PACKAGE_ATTRS.TIME_BUILD: getattr(package, CR_PACKAGE_ATTRS.TIME_BUILD),
            PULP_PACKAGE_ATTRS.TIME_FILE: getattr(package, CR_PACKAGE_ATTRS.TIME_FILE),
            PULP_PACKAGE_ATTRS.URL: getattr(package, CR_PACKAGE_ATTRS.URL) or '',
            PULP_PACKAGE_ATTRS.VERSION: getattr(package, CR_PACKAGE_ATTRS.VERSION)
        }

    def to_createrepo_c(self, checksum_type=None):
        """
        Convert Package object to a createrepo_c package object.

        Currently it works under assumption that Package attributes' names are exactly the same
        as createrepo_c ones.

        Returns:
            createrepo_c.Package: package itself in a format of a createrepo_c package object

        """
        def list_to_createrepo_c(lst):
            """
            Convert list to createrepo_c format.

            Createrepo_c expects list of tuples, not list of lists.
            The assumption is that there are no nested lists, which is true for the data on the
            Package model at the moment.

            Args:
                lst(list): a list

            Returns:
                list: list of strings and/or tuples

            """
            createrepo_c_list = []
            for item in lst:
                if isinstance(item, list):
                    createrepo_c_list.append(tuple(item))
                else:
                    createrepo_c_list.append(item)

            return createrepo_c_list

        package = cr.Package()
        package.arch = getattr(self, PULP_PACKAGE_ATTRS.ARCH)
        package.changelogs = list_to_createrepo_c(
            getattr(self, PULP_PACKAGE_ATTRS.CHANGELOGS))
        package.checksum_type = getattr(self, PULP_PACKAGE_ATTRS.CHECKSUM_TYPE)
        package.conflicts = list_to_createrepo_c(
            getattr(self, PULP_PACKAGE_ATTRS.CONFLICTS))
        package.description = getattr(self, PULP_PACKAGE_ATTRS.DESCRIPTION)
        package.enhances = list_to_createrepo_c(
            getattr(self, PULP_PACKAGE_ATTRS.ENHANCES))
        package.epoch = getattr(self, PULP_PACKAGE_ATTRS.EPOCH)
        package.files = list_to_createrepo_c(getattr(self, PULP_PACKAGE_ATTRS.FILES))
        package.location_base = getattr(self, PULP_PACKAGE_ATTRS.LOCATION_BASE)
        package.location_href = getattr(self, PULP_PACKAGE_ATTRS.LOCATION_HREF)
        package.name = getattr(self, PULP_PACKAGE_ATTRS.NAME)
        package.obsoletes = list_to_createrepo_c(
            getattr(self, PULP_PACKAGE_ATTRS.OBSOLETES))
        package.pkgId = getattr(self, PULP_PACKAGE_ATTRS.PKGID)
        package.provides = list_to_createrepo_c(
            getattr(self, PULP_PACKAGE_ATTRS.PROVIDES))
        package.recommends = list_to_createrepo_c(
            getattr(self, PULP_PACKAGE_ATTRS.RECOMMENDS))
        package.release = getattr(self, PULP_PACKAGE_ATTRS.RELEASE)
        package.requires = list_to_createrepo_c(
            getattr(self, PULP_PACKAGE_ATTRS.REQUIRES))
        package.rpm_buildhost = getattr(self, PULP_PACKAGE_ATTRS.RPM_BUILDHOST)
        package.rpm_group = getattr(self, PULP_PACKAGE_ATTRS.RPM_GROUP)
        package.rpm_header_end = getattr(self, PULP_PACKAGE_ATTRS.RPM_HEADER_END)
        package.rpm_header_start = getattr(self, PULP_PACKAGE_ATTRS.RPM_HEADER_START)
        package.rpm_license = getattr(self, PULP_PACKAGE_ATTRS.RPM_LICENSE)
        package.rpm_packager = getattr(self, PULP_PACKAGE_ATTRS.RPM_PACKAGER)
        package.rpm_sourcerpm = getattr(self, PULP_PACKAGE_ATTRS.RPM_SOURCERPM)
        package.rpm_vendor = getattr(self, PULP_PACKAGE_ATTRS.RPM_VENDOR)
        package.size_archive = getattr(self, PULP_PACKAGE_ATTRS.SIZE_ARCHIVE)
        package.size_installed = getattr(self, PULP_PACKAGE_ATTRS.SIZE_INSTALLED)
        package.size_package = getattr(self, PULP_PACKAGE_ATTRS.SIZE_PACKAGE)
        package.suggests = list_to_createrepo_c(
            getattr(self, PULP_PACKAGE_ATTRS.SUGGESTS))
        package.summary = getattr(self, PULP_PACKAGE_ATTRS.SUMMARY)
        package.supplements = list_to_createrepo_c(
            getattr(self, PULP_PACKAGE_ATTRS.SUPPLEMENTS))
        package.time_build = getattr(self, PULP_PACKAGE_ATTRS.TIME_BUILD)
        package.time_file = getattr(self, PULP_PACKAGE_ATTRS.TIME_FILE)
        package.url = getattr(self, PULP_PACKAGE_ATTRS.URL)
        package.version = getattr(self, PULP_PACKAGE_ATTRS.VERSION)

        if checksum_type:
            pkgId = getattr(self._artifacts.first(), checksum_type.lower(), None)
            if pkgId:
                package.checksum_type = checksum_type
                package.pkgId = pkgId

        return package
