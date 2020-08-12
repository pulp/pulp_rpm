from logging import getLogger

import createrepo_c as cr

from django.contrib.postgres.fields import JSONField
from django.db import models
from django.utils.dateparse import parse_datetime

from pulpcore.plugin.models import (
    BaseModel,
    Content,
)

from pulp_rpm.app.constants import (
    CR_UPDATE_COLLECTION_ATTRS,
    CR_UPDATE_COLLECTION_PACKAGE_ATTRS,
    CR_UPDATE_RECORD_ATTRS,
    CR_UPDATE_COLLECTION_ATTRS_MODULE,
    CR_UPDATE_REFERENCE_ATTRS,
    PULP_UPDATE_COLLECTION_ATTRS,
    PULP_UPDATE_COLLECTION_ATTRS_MODULE,
    PULP_UPDATE_COLLECTION_PACKAGE_ATTRS,
    PULP_UPDATE_RECORD_ATTRS,
    PULP_UPDATE_REFERENCE_ATTRS,
    ADVISORY_SUM_TYPE_TO_NAME
)

log = getLogger(__name__)


class UpdateRecord(Content):
    """
    The "UpdateRecord" content type, formerly "Errata" model in Pulp 2 now "Advisory".

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

    reboot_suggested = models.BooleanField(default=False)

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
                update, CR_UPDATE_RECORD_ATTRS.PUSHCOUNT) or '',
            PULP_UPDATE_RECORD_ATTRS.REBOOT_SUGGESTED: getattr(
                update, CR_UPDATE_RECORD_ATTRS.REBOOT_SUGGESTED) or False
        }

    def to_createrepo_c(self, collections=[]):
        """
        Convert to a createrepo_c UpdateRecord object.

        Args:
            collections(): Collections to add to use for createrepo_c object

        Returns:
            rec(cr.UpdateRecord): createrepo_c representation of an advisory

        """
        rec = cr.UpdateRecord()
        rec.id = self.id
        rec.updated_date = parse_datetime(self.updated_date)

        rec.description = self.description
        rec.issued_date = parse_datetime(self.issued_date)
        rec.fromstr = self.fromstr
        rec.status = self.status
        rec.title = self.title
        rec.summary = self.summary
        rec.version = self.version

        rec.type = self.type
        rec.severity = self.severity
        rec.solution = self.solution
        rec.release = self.release
        rec.rights = self.rights

        rec.reboot_suggested = self.reboot_suggested

        rec.pushcount = self.pushcount

        if not collections:
            collections = self.collections.all()

        for collection in collections:
            rec.append_collection(collection.to_createrepo_c())

        for reference in self.references.all():
            rec.append_reference(reference.to_createrepo_c())

        return rec

    def get_pkglist(self):
        """
        Return NEVRAs of all packages from advisory collections.

        Returns:
            pkglist(list): list of tuples with NEVRA info

        """
        pkglist = []
        for collection in self.collections.all():
            for pkg in collection.packages.all():
                nevra = (pkg.name, pkg.epoch, pkg.version, pkg.release, pkg.arch)
                pkglist.append(nevra)
        return pkglist

    def get_module_list(self):
        """
        Return NSVCAs of all modules from advisory collections.

        Returns:
            modlist (list): list of tuples with NSVCA info

        """
        modlist = []
        for collection in self.collections.all():
            mod = collection.module
            if mod:
                nsvca = (mod['name'], mod['stream'], mod['version'], mod['context'], mod['arch'])
                modlist.append(nsvca)
        return modlist

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"


class UpdateCollection(BaseModel):
    """
    A collection of UpdateCollectionPackages with an associated nametag.

    Maps directly to the fields provided by createrepo_c.
    https://github.com/rpm-software-management/createrepo_c/

    Fields:

        name (Text):
            Name of the collection e.g. RHN Tools for RHEL AUS (v. 6.5 for 64-bit x86_64)
        shortname (Text):
            Short name e.g. rhn-tools-rhel-x86_64-server-6.5.aus
        module (JSON):
            Modular NSVCA connected to advisory collection.

    Relations:

        update_record (models.ForeignKey): The associated UpdateRecord
    """

    name = models.TextField(null=True)
    shortname = models.TextField(null=True)
    module = JSONField(null=True)

    update_record = models.ForeignKey(UpdateRecord, related_name="collections",
                                      on_delete=models.deletion.CASCADE)

    class Meta:
        unique_together = ['name', 'update_record']

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
            ret[PULP_UPDATE_COLLECTION_ATTRS.MODULE] = {
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

        return ret

    def to_createrepo_c(self):
        """
        Convert to a createrepo_c UpdateCollection object.

        Returns:
            col(cr.UpdateCollection): createrepo_c representation of a collection

        """
        col = cr.UpdateCollection()
        col.shortname = self.shortname
        col.name = self.name
        if self.module:
            module = cr.UpdateCollectionModule()
            module.name = self.module['name']
            module.stream = self.module['stream']
            module.version = self.module['version']
            module.context = self.module['context']
            module.arch = self.module['arch']
            col.module = module

        for package in self.packages.all():
            col.append(package.to_createrepo_c())

        return col


class UpdateCollectionPackage(BaseModel):
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
        relogin_suggested (Boolean):
            Whether a relogin is suggested (SuSe specific)
        restart_suggested (Boolean):
            Whether a restart is suggested (SuSe specific)
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
    relogin_suggested = models.BooleanField(default=False)
    restart_suggested = models.BooleanField(default=False)
    release = models.TextField()
    src = models.TextField()
    sum = models.TextField()
    sum_type = models.PositiveIntegerField(
        null=True,
        default=None,
        choices=[
            (sum_type, sum_type) for sum_type in ADVISORY_SUM_TYPE_TO_NAME.keys()
        ]
    )
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
            PULP_UPDATE_COLLECTION_PACKAGE_ATTRS.RELOGIN_SUGGESTED: getattr(
                package, CR_UPDATE_COLLECTION_PACKAGE_ATTRS.RELOGIN_SUGGESTED, False),
            PULP_UPDATE_COLLECTION_PACKAGE_ATTRS.RESTART_SUGGESTED: getattr(
                package, CR_UPDATE_COLLECTION_PACKAGE_ATTRS.RESTART_SUGGESTED, False),
            PULP_UPDATE_COLLECTION_PACKAGE_ATTRS.RELEASE: getattr(
                package, CR_UPDATE_COLLECTION_PACKAGE_ATTRS.RELEASE) or '',
            PULP_UPDATE_COLLECTION_PACKAGE_ATTRS.SRC: getattr(
                package, CR_UPDATE_COLLECTION_PACKAGE_ATTRS.SRC) or '',
            PULP_UPDATE_COLLECTION_PACKAGE_ATTRS.SUM: getattr(
                package, CR_UPDATE_COLLECTION_PACKAGE_ATTRS.SUM) or '',
            PULP_UPDATE_COLLECTION_PACKAGE_ATTRS.SUM_TYPE: getattr(
                package, CR_UPDATE_COLLECTION_PACKAGE_ATTRS.SUM_TYPE) or None,
            PULP_UPDATE_COLLECTION_PACKAGE_ATTRS.VERSION: getattr(
                package, CR_UPDATE_COLLECTION_PACKAGE_ATTRS.VERSION) or ''
        }

    def to_createrepo_c(self):
        """
        Convert to a createrepo_c UpdateCollectionPackage object.

        Returns:
            pkg(cr.UpdateCollectionPackage): createrepo_c representation of a collection package

        """
        pkg = cr.UpdateCollectionPackage()
        pkg.name = self.name
        pkg.version = self.version
        pkg.release = self.release
        pkg.epoch = self.epoch
        pkg.arch = self.arch
        pkg.src = self.src
        pkg.filename = self.filename
        pkg.reboot_suggested = self.reboot_suggested
        # relogin and restart suggested are suse specific
        if self.relogin_suggested:
            pkg.relogin_suggested = self.relogin_suggested
        if self.restart_suggested:
            pkg.restart_suggested = self.restart_suggested
        if self.sum:
            pkg.sum = self.sum
            pkg.sum_type = self.sum_type

        return pkg


class UpdateReference(BaseModel):
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
    ref_id = models.TextField(null=True)
    title = models.TextField(null=True)
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

    def to_createrepo_c(self):
        """
        Convert to a createrepo_c UpdateReference object.

        Returns:
            ref(cr.UpdateReference): createrepo_c representation of a reference

        """
        ref = cr.UpdateReference()
        ref.href = self.href
        ref.id = self.ref_id
        ref.type = self.ref_type
        ref.title = self.title
        return ref
