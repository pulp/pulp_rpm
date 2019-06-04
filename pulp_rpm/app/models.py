import json
from logging import getLogger

import createrepo_c as cr

from django.db import models
from pulpcore.plugin.models import Content, Model, Remote, Publication, PublicationDistribution

from pulp_rpm.app.constants import (CHECKSUM_CHOICES, CREATEREPO_PACKAGE_ATTRS,
                                    CREATEREPO_UPDATE_COLLECTION_ATTRS,
                                    CREATEREPO_UPDATE_COLLECTION_PACKAGE_ATTRS,
                                    CREATEREPO_UPDATE_RECORD_ATTRS,
                                    CREATEREPO_UPDATE_REFERENCE_ATTRS)


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
    name = models.CharField(max_length=255)
    epoch = models.CharField(max_length=255)
    version = models.CharField(max_length=255)
    release = models.CharField(max_length=255)
    arch = models.CharField(max_length=255)

    pkgId = models.CharField(unique=True, max_length=255)  # formerly "checksum" in Pulp 2
    checksum_type = models.CharField(choices=CHECKSUM_CHOICES, max_length=255)

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
    changelogs = models.TextField(default='[]')

    # A string containing a JSON-encoded list of dictionaries, each of which represents a single
    # file. Each file dict contains the following fields:
    #
    #   type (str):     one of "" (regular file), "dir", "ghost"
    #   path (str):     path to file
    #   name (str):     filename
    files = models.TextField(default='[]')

    # Each of these is a string containing a JSON-encoded list of dictionaries, each of which
    # represents a dependency. Each dependency dict contains the following fields:
    #
    #   name (str):     name
    #   flags (str):    flags
    #   epoch (str):    epoch
    #   version (str):  version
    #   release (str):  release
    #   pre (bool):     preinstall
    requires = models.TextField(default='[]')
    provides = models.TextField(default='[]')
    conflicts = models.TextField(default='[]')
    obsoletes = models.TextField(default='[]')
    suggests = models.TextField(default='[]')
    enhances = models.TextField(default='[]')
    recommends = models.TextField(default='[]')
    supplements = models.TextField(default='[]')

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
            'arch': getattr(package, CREATEREPO_PACKAGE_ATTRS.ARCH),
            'changelogs': json.dumps(getattr(package, CREATEREPO_PACKAGE_ATTRS.CHANGELOGS) or []),
            'checksum_type': getattr(package, CREATEREPO_PACKAGE_ATTRS.CHECKSUM_TYPE),
            'conflicts': json.dumps(getattr(package, CREATEREPO_PACKAGE_ATTRS.CONFLICTS) or []),
            'description': getattr(package, CREATEREPO_PACKAGE_ATTRS.DESCRIPTION) or '',
            'enhances': json.dumps(getattr(package, CREATEREPO_PACKAGE_ATTRS.ENHANCES) or []),
            'epoch': getattr(package, CREATEREPO_PACKAGE_ATTRS.EPOCH) or '',
            'files': json.dumps(getattr(package, CREATEREPO_PACKAGE_ATTRS.FILES) or []),
            'location_base': getattr(package, CREATEREPO_PACKAGE_ATTRS.LOCATION_BASE) or '',
            'location_href': getattr(package, CREATEREPO_PACKAGE_ATTRS.LOCATION_HREF),
            'name': getattr(package, CREATEREPO_PACKAGE_ATTRS.NAME),
            'obsoletes': json.dumps(getattr(package, CREATEREPO_PACKAGE_ATTRS.OBSOLETES) or []),
            'pkgId': getattr(package, CREATEREPO_PACKAGE_ATTRS.PKGID),
            'provides': json.dumps(getattr(package, CREATEREPO_PACKAGE_ATTRS.PROVIDES) or []),
            'recommends': json.dumps(getattr(package, CREATEREPO_PACKAGE_ATTRS.RECOMMENDS) or []),
            'release': getattr(package, CREATEREPO_PACKAGE_ATTRS.RELEASE),
            'requires': json.dumps(getattr(package, CREATEREPO_PACKAGE_ATTRS.REQUIRES) or []),
            'rpm_buildhost': getattr(package, CREATEREPO_PACKAGE_ATTRS.RPM_BUILDHOST) or '',
            'rpm_group': getattr(package, CREATEREPO_PACKAGE_ATTRS.RPM_GROUP) or '',
            'rpm_header_end': getattr(package, CREATEREPO_PACKAGE_ATTRS.RPM_HEADER_END),
            'rpm_header_start': getattr(package, CREATEREPO_PACKAGE_ATTRS.RPM_HEADER_START),
            'rpm_license': getattr(package, CREATEREPO_PACKAGE_ATTRS.RPM_LICENSE) or '',
            'rpm_packager': getattr(package, CREATEREPO_PACKAGE_ATTRS.RPM_PACKAGER) or '',
            'rpm_sourcerpm': getattr(package, CREATEREPO_PACKAGE_ATTRS.RPM_SOURCERPM) or '',
            'rpm_vendor': getattr(package, CREATEREPO_PACKAGE_ATTRS.RPM_VENDOR) or '',
            'size_archive': getattr(package, CREATEREPO_PACKAGE_ATTRS.SIZE_ARCHIVE),
            'size_installed': getattr(package, CREATEREPO_PACKAGE_ATTRS.SIZE_INSTALLED),
            'size_package': getattr(package, CREATEREPO_PACKAGE_ATTRS.SIZE_PACKAGE),
            'suggests': json.dumps(getattr(package, CREATEREPO_PACKAGE_ATTRS.SUGGESTS) or []),
            'summary': getattr(package, CREATEREPO_PACKAGE_ATTRS.SUMMARY) or '',
            'supplements': json.dumps(getattr(package, CREATEREPO_PACKAGE_ATTRS.SUPPLEMENTS) or []),
            'time_build': getattr(package, CREATEREPO_PACKAGE_ATTRS.TIME_BUILD),
            'time_file': getattr(package, CREATEREPO_PACKAGE_ATTRS.TIME_FILE),
            'url': getattr(package, CREATEREPO_PACKAGE_ATTRS.URL) or '',
            'version': getattr(package, CREATEREPO_PACKAGE_ATTRS.VERSION)
        }

    def to_createrepo_c(self):
        """
        Convert Package object to a createrepo_c package object.

        Currently it works under assumption that Package attributes' names are exactly the same
        as createrepo_c ones.

        Returns:
            createrepo_c.Package: package itself in a format of a createrepo_c package object

        """
        def str_list_to_createrepo_c(s):
            """
            Convert string representation of list to createrepo_c format.

            Createrepo_c expects list of tuples, not list of lists.
            The assumption is that there are no nested lists, which is true for the data on the
            Package model at the moment.

            Args:
                s(str): string representation of a list

            Returns:
                list: list of strings and/or tuples

            """
            createrepo_c_list = []
            for item in json.loads(s):
                if isinstance(item, list):
                    createrepo_c_list.append(tuple(item))
                else:
                    createrepo_c_list.append(item)

            return createrepo_c_list

        package = cr.Package()
        package.arch = getattr(self, CREATEREPO_PACKAGE_ATTRS.ARCH)
        package.changelogs = str_list_to_createrepo_c(
            getattr(self, CREATEREPO_PACKAGE_ATTRS.CHANGELOGS))
        package.checksum_type = getattr(self, CREATEREPO_PACKAGE_ATTRS.CHECKSUM_TYPE)
        package.conflicts = str_list_to_createrepo_c(
            getattr(self, CREATEREPO_PACKAGE_ATTRS.CONFLICTS))
        package.description = getattr(self, CREATEREPO_PACKAGE_ATTRS.DESCRIPTION)
        package.enhances = str_list_to_createrepo_c(
            getattr(self, CREATEREPO_PACKAGE_ATTRS.ENHANCES))
        package.epoch = getattr(self, CREATEREPO_PACKAGE_ATTRS.EPOCH)
        package.files = str_list_to_createrepo_c(getattr(self, CREATEREPO_PACKAGE_ATTRS.FILES))
        package.location_base = getattr(self, CREATEREPO_PACKAGE_ATTRS.LOCATION_BASE)
        package.location_href = getattr(self, CREATEREPO_PACKAGE_ATTRS.LOCATION_HREF)
        package.name = getattr(self, CREATEREPO_PACKAGE_ATTRS.NAME)
        package.obsoletes = str_list_to_createrepo_c(
            getattr(self, CREATEREPO_PACKAGE_ATTRS.OBSOLETES))
        package.pkgId = getattr(self, CREATEREPO_PACKAGE_ATTRS.PKGID)
        package.provides = str_list_to_createrepo_c(
            getattr(self, CREATEREPO_PACKAGE_ATTRS.PROVIDES))
        package.recommends = str_list_to_createrepo_c(
            getattr(self, CREATEREPO_PACKAGE_ATTRS.RECOMMENDS))
        package.release = getattr(self, CREATEREPO_PACKAGE_ATTRS.RELEASE)
        package.requires = str_list_to_createrepo_c(
            getattr(self, CREATEREPO_PACKAGE_ATTRS.REQUIRES))
        package.rpm_buildhost = getattr(self, CREATEREPO_PACKAGE_ATTRS.RPM_BUILDHOST)
        package.rpm_group = getattr(self, CREATEREPO_PACKAGE_ATTRS.RPM_GROUP)
        package.rpm_header_end = getattr(self, CREATEREPO_PACKAGE_ATTRS.RPM_HEADER_END)
        package.rpm_header_start = getattr(self, CREATEREPO_PACKAGE_ATTRS.RPM_HEADER_START)
        package.rpm_license = getattr(self, CREATEREPO_PACKAGE_ATTRS.RPM_LICENSE)
        package.rpm_packager = getattr(self, CREATEREPO_PACKAGE_ATTRS.RPM_PACKAGER)
        package.rpm_sourcerpm = getattr(self, CREATEREPO_PACKAGE_ATTRS.RPM_SOURCERPM)
        package.rpm_vendor = getattr(self, CREATEREPO_PACKAGE_ATTRS.RPM_VENDOR)
        package.size_archive = getattr(self, CREATEREPO_PACKAGE_ATTRS.SIZE_ARCHIVE)
        package.size_installed = getattr(self, CREATEREPO_PACKAGE_ATTRS.SIZE_INSTALLED)
        package.size_package = getattr(self, CREATEREPO_PACKAGE_ATTRS.SIZE_PACKAGE)
        package.suggests = str_list_to_createrepo_c(
            getattr(self, CREATEREPO_PACKAGE_ATTRS.SUGGESTS))
        package.summary = getattr(self, CREATEREPO_PACKAGE_ATTRS.SUMMARY)
        package.supplements = str_list_to_createrepo_c(
            getattr(self, CREATEREPO_PACKAGE_ATTRS.SUPPLEMENTS))
        package.time_build = getattr(self, CREATEREPO_PACKAGE_ATTRS.TIME_BUILD)
        package.time_file = getattr(self, CREATEREPO_PACKAGE_ATTRS.TIME_FILE)
        package.url = getattr(self, CREATEREPO_PACKAGE_ATTRS.URL)
        package.version = getattr(self, CREATEREPO_PACKAGE_ATTRS.VERSION)

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
            'id': getattr(update, CREATEREPO_UPDATE_RECORD_ATTRS.ID),
            'updated_date': str(getattr(update, CREATEREPO_UPDATE_RECORD_ATTRS.UPDATED_DATE)),
            'description': getattr(update, CREATEREPO_UPDATE_RECORD_ATTRS.DESCRIPTION) or '',
            'issued_date': str(getattr(update, CREATEREPO_UPDATE_RECORD_ATTRS.ISSUED_DATE)) or '',
            'fromstr': getattr(update, CREATEREPO_UPDATE_RECORD_ATTRS.FROMSTR) or '',
            'status': getattr(update, CREATEREPO_UPDATE_RECORD_ATTRS.STATUS) or '',
            'title': getattr(update, CREATEREPO_UPDATE_RECORD_ATTRS.TITLE) or '',
            'summary': getattr(update, CREATEREPO_UPDATE_RECORD_ATTRS.SUMMARY) or '',
            'version': getattr(update, CREATEREPO_UPDATE_RECORD_ATTRS.VERSION) or '',
            'type': getattr(update, CREATEREPO_UPDATE_RECORD_ATTRS.TYPE) or '',
            'severity': getattr(update, CREATEREPO_UPDATE_RECORD_ATTRS.SEVERITY) or '',
            'solution': getattr(update, CREATEREPO_UPDATE_RECORD_ATTRS.SOLUTION) or '',
            'release': getattr(update, CREATEREPO_UPDATE_RECORD_ATTRS.RELEASE) or '',
            'rights': getattr(update, CREATEREPO_UPDATE_RECORD_ATTRS.RIGHTS) or '',
            'pushcount': getattr(update, CREATEREPO_UPDATE_RECORD_ATTRS.PUSHCOUNT) or ''
        }

    def __init__(self, *args, **kwargs):
        """
        Add attributes to the UpdateRecord instance to temporarily store some data in memory.
        """
        super().__init__(*args, **kwargs)
        self._collections = []
        self._references = []


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
        return {
            'name': getattr(collection, CREATEREPO_UPDATE_COLLECTION_ATTRS.NAME),
            'shortname': getattr(collection, CREATEREPO_UPDATE_COLLECTION_ATTRS.SHORTNAME)
        }

    def __init__(self, *args, **kwargs):
        """
        Add attributes to the UpdateCollection instance to temporarily store some data in memory.
        """
        super().__init__(*args, **kwargs)
        self._packages = []


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
            'arch': getattr(package, CREATEREPO_UPDATE_COLLECTION_PACKAGE_ATTRS.ARCH) or '',
            'epoch': getattr(package, CREATEREPO_UPDATE_COLLECTION_PACKAGE_ATTRS.EPOCH) or '0',
            'filename': getattr(package, CREATEREPO_UPDATE_COLLECTION_PACKAGE_ATTRS.FILENAME) or '',
            'name': getattr(package, CREATEREPO_UPDATE_COLLECTION_PACKAGE_ATTRS.NAME) or '',
            'reboot_suggested': getattr(package, CREATEREPO_UPDATE_COLLECTION_PACKAGE_ATTRS.REBOOT_SUGGESTED),  # noqa
            'release': getattr(package, CREATEREPO_UPDATE_COLLECTION_PACKAGE_ATTRS.RELEASE) or '',
            'src': getattr(package, CREATEREPO_UPDATE_COLLECTION_PACKAGE_ATTRS.SRC) or '',
            'sum': getattr(package, CREATEREPO_UPDATE_COLLECTION_PACKAGE_ATTRS.SUM) or '',
            'sum_type': getattr(package, CREATEREPO_UPDATE_COLLECTION_PACKAGE_ATTRS.SUM_TYPE) or '',
            'version': getattr(package, CREATEREPO_UPDATE_COLLECTION_PACKAGE_ATTRS.VERSION) or ''
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
            'href': getattr(reference, CREATEREPO_UPDATE_REFERENCE_ATTRS.HREF),
            'ref_id': getattr(reference, CREATEREPO_UPDATE_REFERENCE_ATTRS.ID),
            'title': getattr(reference, CREATEREPO_UPDATE_REFERENCE_ATTRS.TITLE),
            'ref_type': getattr(reference, CREATEREPO_UPDATE_REFERENCE_ATTRS.TYPE)
        }


class RpmRemote(Remote):
    """
    Remote for "rpm" content.
    """

    TYPE = 'rpm'


class RpmPublication(Publication):
    """
    Publication for "rpm" content.
    """

    TYPE = 'rpm'


class RpmDistribution(PublicationDistribution):
    """
    Distribution for "rpm" content.
    """

    TYPE = 'rpm'
