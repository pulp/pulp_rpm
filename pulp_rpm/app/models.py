import json
from logging import getLogger

import createrepo_c as cr

from django.contrib.postgres.fields import JSONField
from django.db import models
from pulpcore.plugin.models import (
    Content,
    ContentArtifact,
    Model,
    Remote,
    Repository,
    Publication,
    PublicationDistribution
)

from pulp_rpm.app.constants import (CHECKSUM_CHOICES, CR_PACKAGE_ATTRS,
                                    CR_UPDATE_COLLECTION_ATTRS,
                                    CR_UPDATE_COLLECTION_PACKAGE_ATTRS,
                                    CR_UPDATE_RECORD_ATTRS,
                                    CR_UPDATE_COLLECTION_ATTRS_MODULE,
                                    CR_UPDATE_REFERENCE_ATTRS,
                                    LIBCOMPS_CATEGORY_ATTRS,
                                    LIBCOMPS_ENVIRONMENT_ATTRS,
                                    LIBCOMPS_GROUP_ATTRS,
                                    PULP_CATEGORY_ATTRS,
                                    PULP_ENVIRONMENT_ATTRS,
                                    PULP_GROUP_ATTRS,
                                    PULP_LANGPACKS_ATTRS,
                                    PULP_PACKAGE_ATTRS,
                                    PULP_UPDATE_COLLECTION_ATTRS,
                                    PULP_UPDATE_COLLECTION_ATTRS_MODULE,
                                    PULP_UPDATE_COLLECTION_PACKAGE_ATTRS,
                                    PULP_UPDATE_RECORD_ATTRS,
                                    PULP_UPDATE_REFERENCE_ATTRS
                                    )

from pulp_rpm.app.comps import strdict_to_dict

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

    is_modular = models.BooleanField(default=False)

    size_archive = models.BigIntegerField(null=True)
    size_installed = models.BigIntegerField(null=True)
    size_package = models.BigIntegerField(null=True)

    time_build = models.BigIntegerField(null=True)
    time_file = models.BigIntegerField(null=True)

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

    def to_createrepo_c(self):
        """
        Convert Package object to a createrepo_c package object.

        Currently it works under assumption that Package attributes' names are exactly the same
        as createrepo_c ones.

        Returns:
            createrepo_c.Package: package itself in a format of a createrepo_c package object

        """
        def list_to_createrepo_c(l):
            """
            Convert list to createrepo_c format.

            Createrepo_c expects list of tuples, not list of lists.
            The assumption is that there are no nested lists, which is true for the data on the
            Package model at the moment.

            Args:
                l(list): a list

            Returns:
                list: list of strings and/or tuples

            """
            createrepo_c_list = []
            for item in l:
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

        return package


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

    """

    TYPE = 'advisory'

    # Required metadata
    id = models.CharField(max_length=255, db_index=True)
    updated_date = models.TextField()

    # Optional metadata
    description = models.TextField()
    issued_date = models.TextField()
    fromstr = models.TextField()  # formerly "errata_from"
    status = models.TextField()
    title = models.TextField()
    summary = models.TextField()
    version = models.TextField()

    type = models.TextField()
    severity = models.TextField()
    solution = models.TextField()
    release = models.TextField()
    rights = models.TextField()

    pushcount = models.TextField(blank=True)

    # A field that represents the hash digest of the update record. Used to track differences
    # between two UpdateRecord objects without having to examine the associations like
    # UpdateCollection or UpdateCollectionPackage.
    digest = models.CharField(unique=True, max_length=64)

    @classmethod
    def natural_key_fields(cls):
        """
        Digest is used as a natural key for UpdateRecords.
        """
        return ('digest',)

    @classmethod
    def createrepo_to_dict(cls, update):
        """
        Convert createrepo_c update record object to dict for instantiating UpdateRecord.

        Args:
            update(createrepo_c.UpdateRecord): a UpdateRecord to convert

        Returns:
            dict: data for UpdateRecord content creation

        """
        return {
            PULP_UPDATE_RECORD_ATTRS.ID: getattr(update, CR_UPDATE_RECORD_ATTRS.ID),
            PULP_UPDATE_RECORD_ATTRS.UPDATED_DATE: str(
                getattr(update, CR_UPDATE_RECORD_ATTRS.UPDATED_DATE)),
            PULP_UPDATE_RECORD_ATTRS.DESCRIPTION: getattr(
                update, CR_UPDATE_RECORD_ATTRS.DESCRIPTION) or '',
            PULP_UPDATE_RECORD_ATTRS.ISSUED_DATE: str(
                getattr(update, CR_UPDATE_RECORD_ATTRS.ISSUED_DATE)) or '',
            PULP_UPDATE_RECORD_ATTRS.FROMSTR: getattr(update, CR_UPDATE_RECORD_ATTRS.FROMSTR) or '',
            PULP_UPDATE_RECORD_ATTRS.STATUS: getattr(update, CR_UPDATE_RECORD_ATTRS.STATUS) or '',
            PULP_UPDATE_RECORD_ATTRS.TITLE: getattr(update, CR_UPDATE_RECORD_ATTRS.TITLE) or '',
            PULP_UPDATE_RECORD_ATTRS.SUMMARY: getattr(update, CR_UPDATE_RECORD_ATTRS.SUMMARY) or '',
            PULP_UPDATE_RECORD_ATTRS.VERSION: getattr(update, CR_UPDATE_RECORD_ATTRS.VERSION) or '',
            PULP_UPDATE_RECORD_ATTRS.TYPE: getattr(update, CR_UPDATE_RECORD_ATTRS.TYPE) or '',
            PULP_UPDATE_RECORD_ATTRS.SEVERITY: getattr(
                update, CR_UPDATE_RECORD_ATTRS.SEVERITY) or '',
            PULP_UPDATE_RECORD_ATTRS.SOLUTION: getattr(
                update, CR_UPDATE_RECORD_ATTRS.SOLUTION) or '',
            PULP_UPDATE_RECORD_ATTRS.RELEASE: getattr(update, CR_UPDATE_RECORD_ATTRS.RELEASE) or '',
            PULP_UPDATE_RECORD_ATTRS.RIGHTS: getattr(update, CR_UPDATE_RECORD_ATTRS.RIGHTS) or '',
            PULP_UPDATE_RECORD_ATTRS.PUSHCOUNT: getattr(
                update, CR_UPDATE_RECORD_ATTRS.PUSHCOUNT) or ''
        }

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"


class UpdateCollection(Model):
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

    name = models.TextField()
    shortname = models.TextField()
    module = models.TextField(default='')

    update_record = models.ForeignKey(UpdateRecord, related_name="collections",
                                      on_delete=models.CASCADE)

    @classmethod
    def createrepo_to_dict(cls, collection):
        """
        Convert createrepo_c update collection object to dict for instantiating UpdateCollection.

        Args:
            collection(createrepo_c.UpdateCollection): a UpdateCollection to convert

        Returns:
            dict: data for UpdateCollection content creation

        """
        ret = {
            PULP_UPDATE_COLLECTION_ATTRS.NAME: getattr(collection, CR_UPDATE_COLLECTION_ATTRS.NAME),
            PULP_UPDATE_COLLECTION_ATTRS.SHORTNAME: getattr(
                collection, CR_UPDATE_COLLECTION_ATTRS.SHORTNAME)
        }
        if collection.module:
            ret[PULP_UPDATE_COLLECTION_ATTRS.MODULE] = json.dumps(
                {
                    PULP_UPDATE_COLLECTION_ATTRS_MODULE.NAME: getattr(
                        collection.module, CR_UPDATE_COLLECTION_ATTRS_MODULE.NAME),
                    PULP_UPDATE_COLLECTION_ATTRS_MODULE.STREAM: getattr(
                        collection.module, CR_UPDATE_COLLECTION_ATTRS_MODULE.STREAM),
                    PULP_UPDATE_COLLECTION_ATTRS_MODULE.VERSION: getattr(
                        collection.module, CR_UPDATE_COLLECTION_ATTRS_MODULE.VERSION),
                    PULP_UPDATE_COLLECTION_ATTRS_MODULE.CONTEXT: getattr(
                        collection.module, CR_UPDATE_COLLECTION_ATTRS_MODULE.CONTEXT),
                    PULP_UPDATE_COLLECTION_ATTRS_MODULE.ARCH: getattr(
                        collection.module, CR_UPDATE_COLLECTION_ATTRS_MODULE.ARCH)
                }
            )
        return ret


class UpdateCollectionPackage(Model):
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

    arch = models.TextField()
    epoch = models.TextField()
    filename = models.TextField()
    name = models.TextField()
    reboot_suggested = models.BooleanField(default=False)
    release = models.TextField()
    src = models.TextField()
    sum = models.TextField()
    sum_type = models.TextField()
    version = models.TextField()

    update_collection = models.ForeignKey(UpdateCollection, related_name='packages',
                                          on_delete=models.CASCADE)

    @classmethod
    def createrepo_to_dict(cls, package):
        """
        Convert update collection package to dict for instantiating UpdateCollectionPackage.

        Args:
            package(createrepo_c.UpdateCollectionPackage): a UpdateCollectionPackage to convert

        Returns:
            dict: data for UpdateCollectionPackage content creation

        """
        return {
            PULP_UPDATE_COLLECTION_PACKAGE_ATTRS.ARCH: getattr(
                package, CR_UPDATE_COLLECTION_PACKAGE_ATTRS.ARCH) or '',
            PULP_UPDATE_COLLECTION_PACKAGE_ATTRS.EPOCH: getattr(
                package, CR_UPDATE_COLLECTION_PACKAGE_ATTRS.EPOCH) or '0',
            PULP_UPDATE_COLLECTION_PACKAGE_ATTRS.FILENAME: getattr(
                package, CR_UPDATE_COLLECTION_PACKAGE_ATTRS.FILENAME) or '',
            PULP_UPDATE_COLLECTION_PACKAGE_ATTRS.NAME: getattr(
                package, CR_UPDATE_COLLECTION_PACKAGE_ATTRS.NAME) or '',
            PULP_UPDATE_COLLECTION_PACKAGE_ATTRS.REBOOT_SUGGESTED: getattr(
                package, CR_UPDATE_COLLECTION_PACKAGE_ATTRS.REBOOT_SUGGESTED),  # noqa
            PULP_UPDATE_COLLECTION_PACKAGE_ATTRS.RELEASE: getattr(
                package, CR_UPDATE_COLLECTION_PACKAGE_ATTRS.RELEASE) or '',
            PULP_UPDATE_COLLECTION_PACKAGE_ATTRS.SRC: getattr(
                package, CR_UPDATE_COLLECTION_PACKAGE_ATTRS.SRC) or '',
            PULP_UPDATE_COLLECTION_PACKAGE_ATTRS.SUM: getattr(
                package, CR_UPDATE_COLLECTION_PACKAGE_ATTRS.SUM) or '',
            PULP_UPDATE_COLLECTION_PACKAGE_ATTRS.SUM_TYPE: getattr(
                package, CR_UPDATE_COLLECTION_PACKAGE_ATTRS.SUM_TYPE) or '',
            PULP_UPDATE_COLLECTION_PACKAGE_ATTRS.VERSION: getattr(
                package, CR_UPDATE_COLLECTION_PACKAGE_ATTRS.VERSION) or ''
        }


class UpdateReference(Model):
    """
    A reference to the additional information about the problem solved by an update.

    To the extent possible, maps directly to the fields provided by createrepo_c.
    https://github.com/rpm-software-management/createrepo_c/

    Fields:

        href (Text):
            Reference URL, e.g. https://bugzilla.redhat.com/show_bug.cgi?id=1226339
        ref_id (Text):
            ID of the reference, e.g. 1226339
        title (Text):
            Title of the reference, e.g. php-Faker-v1.5.0 is available
        ref_type (Text):
            Type of the reference, e.g. bugzilla

    Relations:

        update_record (models.ForeignKey): The associated UpdateRecord
    """

    href = models.TextField()
    ref_id = models.TextField()
    title = models.TextField()
    ref_type = models.TextField()

    update_record = models.ForeignKey(UpdateRecord, related_name="references",
                                      on_delete=models.CASCADE)

    @classmethod
    def createrepo_to_dict(cls, reference):
        """
        Convert createrepo_c update reference object to dict for instantiating UpdateReference.

        Args:
            reference(createrepo_c.UpdateReference): a UpdateReference to convert

        Returns:
            dict: data for UpdateReference content creation

        """
        return {
            PULP_UPDATE_REFERENCE_ATTRS.HREF: getattr(reference, CR_UPDATE_REFERENCE_ATTRS.HREF),
            PULP_UPDATE_REFERENCE_ATTRS.ID: getattr(reference, CR_UPDATE_REFERENCE_ATTRS.ID),
            PULP_UPDATE_REFERENCE_ATTRS.TITLE: getattr(reference, CR_UPDATE_REFERENCE_ATTRS.TITLE),
            PULP_UPDATE_REFERENCE_ATTRS.TYPE: getattr(reference, CR_UPDATE_REFERENCE_ATTRS.TYPE)
        }


class PackageGroup(Content):
    """
    The "PackageGroup" content type.

    Maps directly to the fields provided by libcomps.
    https://github.com/rpm-software-management/libcomps

    Fields:

        id (Text):
            ID of the group
        default (Bool):
            Flag to identify whether the group is a default
        user_visible (Bool):
            Flag to identify if the group is visible to the user

        display_order (Int):
            Number representing the order of display
        name (Text):
            Name of the group
        description (Text):
            Description of the group
        packages (Text):
            The list of packages in this group
        biarch_only (Bool):
            Flag to identify whether the group is biarch
        desc_by_lang (Text):
            A dictionary of descriptions by language
        name_by_lang (Text):
            A dictionary of names by language
        digest (Text):
            A checksum for the group
        related_packages (ManyToMany):
            Packages related to this PackageGroup
    """

    TYPE = 'packagegroup'

    # Required metadata
    id = models.CharField(max_length=255)

    default = models.BooleanField(default=False)
    user_visible = models.BooleanField(default=False)

    display_order = models.IntegerField(null=True)
    name = models.CharField(max_length=255)
    description = models.TextField(default='')
    packages = JSONField(default=list)

    biarch_only = models.BooleanField(default=False)

    desc_by_lang = JSONField(default=dict)
    name_by_lang = JSONField(default=dict)

    digest = models.CharField(unique=True, max_length=64)

    related_packages = models.ManyToManyField(Package)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"

    @classmethod
    def natural_key_fields(cls):
        """
        Digest is used as a natural key for PackageGroups.
        """
        return ('digest',)

    @classmethod
    def pkglist_to_lst(cls, value):
        """
        Convert libcomps PkgList to list.

        Args:
            value: a libcomps PkgList

        Returns:
            A list

        """
        package_list = []
        for i in value:
            package_list.append({'name': i.name,
                                 'type': i.type,
                                 'basearchonly': i.basearchonly,
                                 'requires': i.requires})
        return package_list

    @classmethod
    def libcomps_to_dict(cls, group):
        """
        Convert libcomps group object to dict for instantiating PackageGroup object.

        Args:
            group(libcomps.group): a RPM/SRPM group to convert

        Returns:
            dict: all data for RPM/SRPM group content creation

        """
        return {
            PULP_GROUP_ATTRS.ID: getattr(group, LIBCOMPS_GROUP_ATTRS.ID),
            PULP_GROUP_ATTRS.DEFAULT: getattr(group, LIBCOMPS_GROUP_ATTRS.DEFAULT),
            PULP_GROUP_ATTRS.USER_VISIBLE: getattr(group, LIBCOMPS_GROUP_ATTRS.USER_VISIBLE),
            PULP_GROUP_ATTRS.DISPLAY_ORDER: getattr(group, LIBCOMPS_GROUP_ATTRS.DISPLAY_ORDER),
            PULP_GROUP_ATTRS.NAME: getattr(group, LIBCOMPS_GROUP_ATTRS.NAME),
            PULP_GROUP_ATTRS.DESCRIPTION: getattr(group, LIBCOMPS_GROUP_ATTRS.DESCRIPTION) or '',
            PULP_GROUP_ATTRS.PACKAGES: cls.pkglist_to_lst(getattr(group,
                                                                  LIBCOMPS_GROUP_ATTRS.PACKAGES)),
            PULP_GROUP_ATTRS.BIARCH_ONLY: getattr(group, LIBCOMPS_GROUP_ATTRS.BIARCH_ONLY),
            PULP_GROUP_ATTRS.DESC_BY_LANG: strdict_to_dict(
                getattr(group, LIBCOMPS_GROUP_ATTRS.DESC_BY_LANG)
            ),
            PULP_GROUP_ATTRS.NAME_BY_LANG: strdict_to_dict(
                getattr(group, LIBCOMPS_GROUP_ATTRS.NAME_BY_LANG)
            ),
        }


class PackageCategory(Content):
    """
    The "Category" content type. Formerly "PackageCategory" in Pulp 2.

    Maps directly to the fields provided by libcomps.
    https://github.com/rpm-software-management/libcomps

    Fields:

        id (Text):
            ID of the category
        name (Text):
            The name of the category
        description (Text):
            The description of the category
        display_order (Int):
            Number representing the order of display
        group_ids (Text):
            A list of group ids
        desc_by_lang (Text):
            A dictionary of descriptions by language
        name_by_lang (Text):
            A dictionary of names by language
        digest (Text):
            A checksum for the category
        packagegroups (ManyToMany):
            PackageGroups related to this category
    """

    TYPE = 'packagecategory'

    # Required metadata
    id = models.CharField(max_length=255)

    name = models.CharField(max_length=255)
    description = models.TextField(default='')
    display_order = models.IntegerField(null=True)

    group_ids = JSONField(default=list)

    desc_by_lang = JSONField(default=dict)
    name_by_lang = JSONField(default=dict)

    digest = models.CharField(unique=True, max_length=64)

    packagegroups = models.ManyToManyField(PackageGroup)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"

    @classmethod
    def natural_key_fields(cls):
        """
        Digest is used as a natural key for PackageCategory.
        """
        return ('digest',)

    @classmethod
    def grplist_to_lst(cls, value):
        """
        Convert libcomps GrpList to list.

        Args:
            value: a libcomps GrpList

        Returns:
            A list

        """
        grp_list = []
        for i in value:
            grp_list.append({'name': i.name,
                             'default': i.default})
        return grp_list

    @classmethod
    def libcomps_to_dict(cls, category):
        """
        Convert libcomps category object to dict for instantiating PackageCategory object.

        Args:
            category(libcomps.category): a RPM/SRPM category to convert

        Returns:
            dict: all data for RPM/SRPM category content creation

        """
        return {
            PULP_CATEGORY_ATTRS.ID: getattr(category, LIBCOMPS_CATEGORY_ATTRS.ID),
            PULP_CATEGORY_ATTRS.NAME: getattr(category, LIBCOMPS_CATEGORY_ATTRS.NAME),
            PULP_CATEGORY_ATTRS.DESCRIPTION: getattr(category,
                                                     LIBCOMPS_CATEGORY_ATTRS.DESCRIPTION) or '',
            PULP_CATEGORY_ATTRS.DISPLAY_ORDER: getattr(category,
                                                       LIBCOMPS_CATEGORY_ATTRS.DISPLAY_ORDER),
            PULP_CATEGORY_ATTRS.GROUP_IDS: cls.grplist_to_lst(
                getattr(category, LIBCOMPS_CATEGORY_ATTRS.GROUP_IDS)
            ),
            PULP_CATEGORY_ATTRS.DESC_BY_LANG: strdict_to_dict(
                getattr(category, LIBCOMPS_CATEGORY_ATTRS.DESC_BY_LANG)
            ),
            PULP_CATEGORY_ATTRS.NAME_BY_LANG: strdict_to_dict(
                getattr(category, LIBCOMPS_CATEGORY_ATTRS.NAME_BY_LANG)
            ),
        }


class PackageEnvironment(Content):
    """
    The "Environment" content type. Formerly "PackageEnvironment" in Pulp 2.

    Maps directly to the fields provided by libcomps.
    https://github.com/rpm-software-management/libcomps

    Fields:

        id (Text):
            ID of the environment
        name (Text):
            The name of the environment
        description (Text):
            The description of the environment
        display_order (Int):
            Number representing the order of display
        group_ids (Text):
            A list of group ids
        option_ids (Text):
            A list of option ids
        desc_by_lang (Text):
            A dictionary of descriptions by language
        name_by_lang (Text):
            A dictionary of names by language
        digest (Text):
            A checksum for the environment
        packagegroups (ManyToMany):
            PackageGroups related to this environment
        optionalgroups (ManyToMany):
            PackageGroups optionally related to this environment
    """

    TYPE = 'packageenvironment'

    # Required metadata
    id = models.CharField(max_length=255)

    name = models.CharField(max_length=255)
    description = models.TextField(default='')
    display_order = models.IntegerField(null=True)

    group_ids = JSONField(default=list)
    option_ids = JSONField(default=list)

    desc_by_lang = JSONField(default=dict)
    name_by_lang = JSONField(default=dict)

    digest = models.CharField(unique=True, max_length=64)

    packagegroups = models.ManyToManyField(PackageGroup, related_name='packagegroups_to_env')
    optionalgroups = models.ManyToManyField(PackageGroup, related_name='optionalgroups_to_env')

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"

    @classmethod
    def natural_key_fields(cls):
        """
        Digest is used as a natural key for PackageEnvironment.
        """
        return ('digest',)

    @classmethod
    def grplist_to_lst(cls, value):
        """
        Convert libcomps GrpList to list.

        Args:
            value: a libcomps GrpList

        Returns:
            A list

        """
        grp_list = []
        for i in value:
            grp_list.append({'name': i.name,
                             'default': i.default})
        return grp_list

    @classmethod
    def libcomps_to_dict(cls, environment):
        """
        Convert libcomps environment object to dict for instantiating PackageEnvironment object.

        Args:
            environment(libcomps.environment): a RPM/SRPM environment to convert

        Returns:
            dict: all data for RPM/SRPM environment content creation

        """
        return {
            PULP_ENVIRONMENT_ATTRS.ID: getattr(environment, LIBCOMPS_ENVIRONMENT_ATTRS.ID),
            PULP_ENVIRONMENT_ATTRS.NAME: getattr(environment, LIBCOMPS_ENVIRONMENT_ATTRS.NAME),
            PULP_ENVIRONMENT_ATTRS.DESCRIPTION: getattr(
                environment, LIBCOMPS_ENVIRONMENT_ATTRS.DESCRIPTION
            ) or '',
            PULP_ENVIRONMENT_ATTRS.DISPLAY_ORDER: getattr(environment,
                                                          LIBCOMPS_ENVIRONMENT_ATTRS.DISPLAY_ORDER),
            PULP_ENVIRONMENT_ATTRS.GROUP_IDS: cls.grplist_to_lst(
                getattr(environment, LIBCOMPS_ENVIRONMENT_ATTRS.GROUP_IDS)
            ),
            PULP_ENVIRONMENT_ATTRS.OPTION_IDS: cls.grplist_to_lst(
                getattr(environment, LIBCOMPS_ENVIRONMENT_ATTRS.OPTION_IDS)
            ),
            PULP_ENVIRONMENT_ATTRS.DESC_BY_LANG: strdict_to_dict(
                getattr(environment, LIBCOMPS_ENVIRONMENT_ATTRS.DESC_BY_LANG)
            ),
            PULP_ENVIRONMENT_ATTRS.NAME_BY_LANG: strdict_to_dict(
                getattr(environment, LIBCOMPS_ENVIRONMENT_ATTRS.NAME_BY_LANG)
            ),
        }


class PackageLangpacks(Content):
    """
    The "Langpacks" content type. Formerly "PackageLangpacks" in Pulp 2.

    Maps directly to the fields provided by libcomps.
    https://github.com/rpm-software-management/libcomps

    Fields:

        matches (Dict):
            The langpacks dictionary
    """

    TYPE = 'packagelangpacks'

    matches = JSONField(default=dict)

    digest = models.CharField(unique=True, max_length=64)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"

    @classmethod
    def natural_key_fields(cls):
        """
        Digest is used as a natural key for PackageLangpacks.
        """
        return ('digest',)

    @classmethod
    def libcomps_to_dict(cls, langpacks):
        """
        Convert libcomps langpacks object to dict for instantiating PackageLangpacks object.

        Args:
            langpacks(libcomps.langpacks): a RPM/SRPM langpacks to convert

        Returns:
            dict: all data for RPM/SRPM langpacks content creation

        """
        return {
            PULP_LANGPACKS_ATTRS.MATCHES: strdict_to_dict(langpacks)
        }


class RpmRepository(Repository):
    """
    Repository for "rpm" content.
    """

    TYPE = "rpm"

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"


class RpmRemote(Remote):
    """
    Remote for "rpm" content.
    """

    TYPE = 'rpm'

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"


class RpmPublication(Publication):
    """
    Publication for "rpm" content.
    """

    TYPE = 'rpm'

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"


class RpmDistribution(PublicationDistribution):
    """
    Distribution for "rpm" content.
    """

    TYPE = 'rpm'

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"


class Modulemd(Content):
    """
    The "Modulemd" content type. Modularity support.

    Fields:
        name (Text):
            Name of the modulemd
        stream (Text):
            The modulemd's stream
        version (Text):
            The version of the modulemd.
        context (Text):
            The context flag serves to distinguish module builds with the
            same name, stream and version and plays an important role in
            future automatic module stream name expansion.
        arch (Text):
            Module artifact architecture.
        dependencies (Text):
            Module dependencies, if any.
        artifacts (Text):
            Artifacts shipped with this module.
        packages (Text):
            List of Packages connected to this modulemd.
    """

    TYPE = "modulemd"

    # required metadata
    name = models.CharField(max_length=255)
    stream = models.CharField(max_length=255)
    version = models.CharField(max_length=255)
    context = models.CharField(max_length=255)
    arch = models.CharField(max_length=255)

    dependencies = JSONField(default=list)
    artifacts = JSONField(default=list)
    packages = models.ManyToManyField(Package)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = (
            'name', 'stream', 'version', 'context', 'arch'
        )


class ModulemdDefaults(Content):
    """
    The "Modulemd Defaults" content type. Modularity support.

    Fields:
        module (Text):
            Modulemd name.
        stream (Text):
            Modulemd default stream.
        profiles (Text):
            Default profiles for modulemd streams.
        digest (Text):
            Modulemd digest
    """

    TYPE = "modulemd-defaults"

    module = models.CharField(max_length=255)
    stream = models.CharField(max_length=255)
    profiles = JSONField(default=list)

    digest = models.CharField(unique=True, max_length=64)

    @classmethod
    def natural_key_fields(cls):
        """
        Digest is used as a natural key for ModulemdDefaults.
        """
        return ('digest',)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"


class DistributionTree(Content):
    """
    Model for an RPM distribution tree (also sometimes referenced as an installable tree).

    A distribution tree is described by a file in root of an RPM repository named either
    "treeinfo" or ".treeinfo". This INI file is used by system installers to boot from a URL.
    It describes the operating system or product contained in the distribution tree and
    where the bootable media is located for various platforms (where platform means
    'x86_64', 'xen', or similar).

    The description of the "treeinfo" format is included below, originally take from
    https://release-engineering.github.io/productmd/treeinfo-1.0.html

    Fields:
        header_version (Text):
            Metadata version
        release_name (Text):
            Release name
        release_short (Text):
            Release short name
        release_version (Text):
            Release version
        release_type (Text):
            Release type
        release_is_layered (Bool):
            Typically False for an operating system, True otherwise
        base_product_name (Text):
            Base product name
        base_product_short (Text):
            Base product short name
        base_product_version (Text):
            Base product *major* version
        base_product_type (Text):
            Base product release type
        arch (Text):
            Tree architecture
        build_timestamp (Float):
            Tree build time timestamp
        instimage (Text):
            Relative path to Anaconda instimage
        mainimage (Text):
            Relative path to Anaconda stage2 image
        discnum (Integer):
            Disc number
        totaldiscs (Integer):
            Number of discs in media set

    """

    TYPE = 'distribution_tree'

    header_version = models.CharField(max_length=10)

    release_name = models.CharField(max_length=50)
    release_short = models.CharField(max_length=20)
    release_version = models.CharField(max_length=10)
    release_is_layered = models.BooleanField(default=False)

    base_product_name = models.CharField(max_length=50, null=True)
    base_product_short = models.CharField(max_length=20, null=True)
    base_product_version = models.CharField(max_length=10, null=True)

    # tree
    arch = models.CharField(max_length=30)
    build_timestamp = models.FloatField()

    # stage2
    instimage = models.CharField(max_length=50, null=True)
    mainimage = models.CharField(max_length=50, null=True)

    # media
    discnum = models.IntegerField(null=True)
    totaldiscs = models.IntegerField(null=True)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = (
            "header_version",
            "release_name",
            "release_short",
            "release_version",
            "arch",
            "build_timestamp",
        )


class Checksum(Model):
    """
    Distribution Tree Checksum.

    Checksums of selected files in a tree.

    Fields:
        path (Text):
            File path
        checksum (Text):
            Checksum value for the file

    Relations:

        distribution_tree (models.ForeignKey): The associated DistributionTree

    """

    path = models.CharField(max_length=128)
    checksum = models.CharField(max_length=128, null=True)
    distribution_tree = models.ForeignKey(
        DistributionTree, on_delete=models.CASCADE, related_name='checksums'
    )

    class Meta:
        unique_together = (
            "path",
            "checksum",
            "distribution_tree",
        )


class Image(Model):
    """
    Distribution Tree Image.

    Images compatible with particular platform.

    Fields:
        name (Text):
            File name
        path (Text):
            File path
        platforms (Text):
            Compatible platforms

    Relations:

        distribution_tree (models.ForeignKey): The associated DistributionTree

    """

    name = models.CharField(max_length=20)
    path = models.CharField(max_length=128)
    platforms = models.CharField(max_length=20)
    distribution_tree = models.ForeignKey(
        DistributionTree, on_delete=models.CASCADE, related_name='images'
    )

    @property
    def artifact(self):
        """
        Returns artifact object.
        """
        content_artifact = ContentArtifact.objects.filter(
            content=self.distribution_tree,
            relative_path=self.path,
        ).first()

        artifact = content_artifact.artifact if content_artifact else None

        return artifact

    class Meta:
        unique_together = (
            "name",
            "path",
            "platforms",
            "distribution_tree",
        )


class Addon(Model):
    """
    Distribution Tree Addon.

    Kickstart functionality expansion.

    Fields:
        addon_id (Text):
            Addon id
        uid (Text):
            Addon uid
        name (Text):
            Addon name
        type (Text):
            Addon type
        packages (Text):
            Relative path to directory with binary RPMs

    Relations:

        distribution_tree (models.ForeignKey): The associated DistributionTree
        repository (models.ForeignKey): The associated Repository

    """

    addon_id = models.CharField(max_length=50)
    uid = models.CharField(max_length=50)
    name = models.CharField(max_length=50)
    type = models.CharField(max_length=20)
    packages = models.CharField(max_length=50)
    distribution_tree = models.ForeignKey(
        DistributionTree, on_delete=models.CASCADE, related_name='addons'
    )
    repository = models.ForeignKey(
        Repository, on_delete=models.PROTECT, related_name='addons'
    )

    class Meta:
        unique_together = (
            "addon_id",
            "uid",
            "name",
            "type",
            "packages",
            "distribution_tree",
        )


class Variant(Model):
    """
    Distribution Tree Variant.

    Fields:
        variant_id (Text):
            Variant id
        uid (Text):
            Variant uid
        name (Text):
            Variant name
        type (Text):
            Variant type
        packages (Text):
            Relative path to directory with binary RPMs
        source_packages (Text):
            Relative path to directory with source RPMs
        source_repository (Text):
            Relative path to YUM repository with source RPMs
        debug_packages (Text):
            Relative path to directory with debug RPMs
        debug_repository (Text):
            Relative path to YUM repository with debug RPMs
        identity (Text):
            Relative path to a pem file that identifies a product

    Relations:

        distribution_tree (models.ForeignKey): The associated DistributionTree
        repository (models.ForeignKey): The associated Repository

    """

    variant_id = models.CharField(max_length=50)
    uid = models.CharField(max_length=50)
    name = models.CharField(max_length=50)
    type = models.CharField(max_length=20)
    packages = models.CharField(max_length=50)
    source_packages = models.CharField(max_length=50, null=True)
    source_repository = models.CharField(max_length=50, null=True)
    debug_packages = models.CharField(max_length=50, null=True)
    debug_repository = models.CharField(max_length=50, null=True)
    identity = models.CharField(max_length=50, null=True)
    distribution_tree = models.ForeignKey(
        DistributionTree, on_delete=models.CASCADE, related_name='variants'
    )
    repository = models.ForeignKey(
        Repository, on_delete=models.PROTECT, related_name='+'
    )

    class Meta:
        unique_together = (
            "variant_id",
            "uid",
            "name",
            "type",
            "packages",
            "distribution_tree",
        )


class RepoMetadataFile(Content):
    """
    Model for custom/unknown repository metadata.

    Fields:
        data_type (Text):
            Metadata type
        checksum_type (Text):
            Checksum type for the file
        checksum (Text):
            Checksum value for the file

    """

    TYPE = 'repo_metadata_file'

    data_type = models.CharField(max_length=20)
    checksum_type = models.CharField(max_length=6)
    checksum = models.CharField(max_length=128)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = ("data_type", "checksum")
