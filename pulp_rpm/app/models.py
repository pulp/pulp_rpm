from logging import getLogger

from django.db import models
from pulpcore.plugin.models import Content, Remote, Publisher

from pulp_rpm.app.constants import CHECKSUM_CHOICES


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
    name = models.TextField()
    epoch = models.TextField()
    version = models.TextField()
    release = models.TextField()
    arch = models.TextField()

    pkgId = models.TextField(unique=True)  # formerly "checksum" in Pulp 2
    checksum_type = models.TextField(choices=CHECKSUM_CHOICES)

    # Optional metadata
    summary = models.TextField(blank=True)
    description = models.TextField(blank=True)
    url = models.TextField(blank=True)

    # A string containing a JSON-encoded list of dictionaries, each of which represents a single
    # changelog. Each changelog dict contains the following fields:
    #
    #   date (int):     date of changelog - seconds since epoch
    #   author (str):   author of the changelog
    #   changelog (str: changelog text
    changelogs = models.TextField(default='[]', blank=True)

    # A string containing a JSON-encoded list of dictionaries, each of which represents a single
    # file. Each file dict contains the following fields:
    #
    #   type (str):     one of "" (regular file), "dir", "ghost"
    #   path (str):     path to file
    #   name (str):     filename
    files = models.TextField(default='[]', blank=True)

    # Each of these is a string containing a JSON-encoded list of dictionaries, each of which
    # represents a dependency. Each dependency dict contains the following fields:
    #
    #   name (str):     name
    #   flags (str):    flags
    #   epoch (str):    epoch
    #   version (str):  version
    #   release (str):  release
    #   pre (bool):     preinstall
    requires = models.TextField(default='[]', blank=True)
    provides = models.TextField(default='[]', blank=True)
    conflicts = models.TextField(default='[]', blank=True)
    obsoletes = models.TextField(default='[]', blank=True)
    suggests = models.TextField(default='[]', blank=True)
    enhances = models.TextField(default='[]', blank=True)
    recommends = models.TextField(default='[]', blank=True)
    supplements = models.TextField(default='[]', blank=True)

    location_base = models.TextField(blank=True)
    location_href = models.TextField(blank=True)

    rpm_buildhost = models.TextField(blank=True)
    rpm_group = models.TextField(blank=True)
    rpm_license = models.TextField(blank=True)
    rpm_packager = models.TextField(blank=True)
    rpm_sourcerpm = models.TextField(blank=True)
    rpm_vendor = models.TextField(blank=True)
    rpm_header_start = models.BigIntegerField(null=True, blank=True)
    rpm_header_end = models.BigIntegerField(null=True, blank=True)

    size_archive = models.BigIntegerField(null=True, blank=True)
    size_installed = models.BigIntegerField(null=True, blank=True)
    size_package = models.BigIntegerField(null=True, blank=True)

    time_build = models.BigIntegerField(null=True, blank=True)
    time_file = models.BigIntegerField(null=True, blank=True)

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
        unique_together = (
            'name', 'epoch', 'version', 'release', 'arch', 'checksum_type', 'pkgId'
        )


class UpdateRecord(Content):
    """
    The "UpdateRecord" content type, formerly "Errata" model in Pulp 2.

    Maps directly to the fields provided by createrepo_c.
    https://github.com/rpm-software-management/createrepo_c/

    Fields:
        id (Text):
            Update id (short update name, e.g. RHEA-2013:1777)
        updated_date (Text):
            Date when the update was updated (e.g. "2013-12-02 00:00:00")

        description (Text):
            Update description
        issued_date (Text):
            Date when the update was issued (e.g. "2013-12-02 00:00:00")
        fromstr (Text):
            Source of the update (e.g. security@redhat.com)
        status (Text):
            Update status ("final", ...)
        title (Text):
            Update name
        summary (Text):
            Short summary
        version (Text):
            Update version (probably always an integer number)

        type (Text):
            Update type ("enhancement", "bugfix", ...)
        severity (Text):
            Severity
        solution (Text):
            Solution
        release (Text):
            Update release
        rights (Text):
            Copyrights

        pushcount (Text):
            Push count

        references (Text):
            List of UpdateReferences - see comments below

    """

    # Required metadata
    errata_id = models.TextField()  # TODO: change field name?
    updated_date = models.TextField()

    # Optional metadata
    description = models.TextField(blank=True)
    issued_date = models.TextField(blank=True)
    fromstr = models.TextField(blank=True)  # formerly "errata_from"
    status = models.TextField(blank=True)
    title = models.TextField(blank=True)
    summary = models.TextField(blank=True)
    version = models.TextField(blank=True)

    update_type = models.TextField(blank=True)  # TODO: change field name?
    severity = models.TextField(blank=True)
    solution = models.TextField(blank=True)
    release = models.TextField(blank=True)
    rights = models.TextField(blank=True)

    pushcount = models.TextField(blank=True)

    # A string containing a JSON-encoded list of dictionaries, each of which represents an
    # UpdateReference. Each UpdateReference dict contains the following fields:
    #
    #   href (str):         URL (e.g. to related bugzilla, errata, ...)
    #   id (str):           Id (e.g. 1035288, NULL for errata, ...)
    #   title (str):        Name of errata, name of bug, etc.
    #   type (str):         Reference type ("self" for errata, "bugzilla", ...)
    references = models.TextField(default='[]', blank=True)

    class Meta:
        unique_together = ()
        # TODO: Find some way to enforce uniqueness per-repository
        # make a hash of the natural key, store the hash?


class UpdateCollection(models.Model):
    """
    A collection of UpdateCollectionPackages with an associated nametag.

    Maps directly to the fields provided by createrepo_c.
    https://github.com/rpm-software-management/createrepo_c/

    Fields:

        name (Text):
            Name of the collection e.g. RHN Tools for RHEL AUS (v. 6.5 for 64-bit x86_64)
        shortname (Text):
            Short name e.g. rhn-tools-rhel-x86_64-server-6.5.aus

    Relations:

        update_record (models.ForeignKey): The associated UpdateRecord
    """

    name = models.TextField(blank=True)
    shortname = models.TextField(blank=True)

    update_record = models.ForeignKey(UpdateRecord, related_name="collections",
                                      on_delete=models.CASCADE)


class UpdateCollectionPackage(models.Model):
    """
    Part of an UpdateCollection, representing a package.

    Maps directly to the fields provided by createrepo_c.
    https://github.com/rpm-software-management/createrepo_c/

    Fields:

        arch (Text):
            Arch
        epoch (Text):
            Epoch
        filename (Text):
            Filename
        name (Text):
            Name
        reboot_suggested (Boolean):
            Whether a reboot is suggested after package installation
        release (Text):
            Release
        src (Text):
            Source filename
        sum (Text):
            Checksum
        sum_type (Text):
            Checksum type
        version (Text):
            Version

    Relations:

        update_collection (models.ForeignKey): The associated UpdateCollection
    """

    arch = models.TextField(blank=True)
    epoch = models.TextField(blank=True)
    filename = models.TextField(blank=True)
    name = models.TextField(blank=True)
    reboot_suggested = models.BooleanField(blank=True)
    release = models.TextField(blank=True)
    src = models.TextField(blank=True)
    sum = models.TextField(blank=True)
    sum_type = models.TextField(blank=True)
    version = models.TextField(blank=True)

    update_collection = models.ForeignKey(UpdateCollection, related_name='packages',
                                          on_delete=models.CASCADE)


class RpmRemote(Remote):
    """
    Remote for "rpm" content.
    """

    TYPE = 'rpm'


class RpmPublisher(Publisher):
    """
    Publisher for "rpm" content.
    """

    TYPE = 'rpm'
