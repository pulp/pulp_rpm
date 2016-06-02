import csv
import logging
import os
from gettext import gettext as _
from operator import itemgetter
from urlparse import urljoin

import errno
from django.template import Context, Template
import mongoengine
import pulp.common.error_codes as platform_error_codes
from pulp.server.db.model import ContentUnit, FileContentUnit
from pulp.server.exceptions import PulpCodedException
import pulp.server.util as server_util

from pulp_rpm.common import version_utils
from pulp_rpm.common import file_utils
from pulp_rpm.plugins import error_codes
from pulp_rpm.plugins import serializers
from pulp_rpm.plugins.db.fields import ChecksumTypeStringField
from pulp_rpm.plugins.importers.yum import utils
from pulp_rpm.yum_plugin import util


_LOGGER = logging.getLogger(__name__)


class UnitMixin(object):
    # TODO add docstring to this class

    SERIALIZER = None

    meta = {
        'abstract': True,
    }

    def __str__(self):
        return '%s: %s' % (self._content_type_id,
                           '-'.join(getattr(self, name) for name in self.unit_key_fields))

    def create_legacy_metadata_dict(self):
        """
        Pulp's legacy unit model had a "metadata" attribute, which the Incremental steps below used
        as the basis for the data that gets written to disk. This function re-creates that data
        structure and filters out fields whose name starts with a _.

        :return:    a dictionary with keys and values that are all of the fields on the unit model,
                    minus those in the unit key and those that start with an underscore.
        :rtype:     dict
        """
        field_names = filter(lambda k: not k.startswith('_'), self.__class__._fields.keys())
        metadata_dict = {}
        for name in field_names:
            metadata_dict[name] = getattr(self, name)
        return metadata_dict

    def clone(self):
        """
        Creates a new instance of an equivalent unit, with the unique ID missing. This is useful
        for the PackageGroup and similar units, where there is a regular need to create a copy of
        a unit, changing just one field in the unit key.

        This is a strange use case, so at this point it doesn't seem worth putting this method
        into the platform.

        deepcopy does not appear to work, presumably because of all the special handling that
        mongoengine does in the metaclass. Suggestions are welcome for a better way to clone.

        :return:    a new unit instance without a unique ID
        :rtype:     Package
        """
        son_data = self.to_mongo()
        son_data.pop('_id')
        return self.__class__(**son_data)

    def to_id_dict(self):
        """
        Overrides the platform method, whose purpose is to provide a minimal representation that
        can be returned in a view. For example, the repo associate action represents units this
        way.

        For models where members of the unit key had to be renamed and must be serialized with the
        original name for API compatibility, this method does that translation.

        :return:    dictionary with key "type_id" and the value corresponding to the unit type; and
                    key "unit_key" whose value is the unit's translated unit key.
        :rtype:     dict
        """
        ret = super(UnitMixin, self).to_id_dict()
        if self.SERIALIZER is not None:
            unit_key = ret['unit_key']
            for new, old in self.SERIALIZER.Meta.remapped_fields.items():
                if new in unit_key:
                    unit_key[old] = unit_key[new]
                    del unit_key[new]
        return ret


class NonMetadataPackage(UnitMixin, FileContentUnit):
    """
    An abstract model to be subclassed by packages which are not metadata

    It is tempting to have checksum auto-calculate as a pre_save_signal(), but with checksum being
    part of the unit_key it is needed when __init__() is called. The filename is not provided to
    __init__() which makes doing it then impossible. For now, the checksum field is the
    responsibility of the unit instantiator.

    :ivar version: The version field of the package
    :type version: mongoengine.Stringfield

    :ivar release: The release field of the package
    :type release: mongoengine.Stringfield

    :ivar checksumtype: The checksum type of the package.
    :type checksumtype: mongoengine.StringField

    :ivar checksum: The checksum of the package.
    :type checksum: mongoengine.StringField

    :ivar version_sort_index: ???
    :type version_sort_index: mongoengine.StringField

    :ivar release_sort_index: ???
    :type release_sort_index: mongoengine.StringField
    """

    version = mongoengine.StringField(required=True)
    release = mongoengine.StringField(required=True)
    checksum = mongoengine.StringField(required=True)
    checksumtype = ChecksumTypeStringField(required=True)
    checksums = mongoengine.DictField()

    # We generate these two
    version_sort_index = mongoengine.StringField()
    release_sort_index = mongoengine.StringField()

    meta = {
        'abstract': True,
    }

    def __init__(self, *args, **kwargs):
        if kwargs.get('checksumtype') is not None:
            kwargs['checksumtype'] = server_util.sanitize_checksum_type(kwargs['checksumtype'])
        super(NonMetadataPackage, self).__init__(*args, **kwargs)

    @classmethod
    def pre_save_signal(cls, sender, document, **kwargs):
        """
        Generate the version & Release sort index before saving

        :param sender: sender class
        :type sender: object
        :param document: Document that sent the signal
        :type document: pulp_rpm.plugins.db.models.NonMetadataPackage
        """
        super(NonMetadataPackage, cls).pre_save_signal(sender, document, **kwargs)
        document.version_sort_index = version_utils.encode(document.version)
        document.release_sort_index = version_utils.encode(document.release)

    # Used by RPM, SRPM, DRPM
    @property
    def key_string_without_version(self):
        keys = [getattr(self, key) for key in self.unit_key_fields if
                key not in ['epoch', 'version', 'release', 'checksum', 'checksumtype']]
        keys.append(self._content_type_id)
        return '-'.join(keys)

    @property
    def complete_version(self):
        values = []
        for name in ('epoch', 'version', 'release'):
            if name in self.unit_key_fields:
                values.append(getattr(self, name))
        return tuple(values)

    @property
    def complete_version_serialized(self):
        return tuple(version_utils.encode(field) for field in self.complete_version)

    def __cmp__(self, other):
        """
        Allows for comparison using the tuple from complete_version_serialized().

        Generally this compares using rank comparison on the fields: epoch, version, release.

        This needs to be replaced when adding Python 3 support.

        Python 3 removes __cmp__ in favor of rich comparison operators. When porting this to
        Python 3, replace __cmp__ with the __lt__, __le__, __gt__, __ge__ methods. The __eq__ or
        __neq__ should *not* be implemented because we could be affecting mongoengine internal
        behaviors by doing so.
        """
        return cmp(
            self.complete_version_serialized,
            other.complete_version_serialized
        )

    def get_or_calculate_and_save_checksum(self, checksumtype):
        """
        Tries to get the checksum value for the specified type from the "checksums" attribute.
        If it is not available, calculates the value and saves it in self.checksums before
        returning it.

        SIDE EFFECT: This method will save the model if the requested checksumtype is not populated
                     on the model in the "checksums" attribute.

        :param checksumtype:   any checksum type supported by the platform
        :type  checksumtype:   basestring

        :return:    checksum value of the requested type
        :rtype:     basestring

        :raises PulpCodedException: if the checksumtype is not available
        """
        if checksumtype not in server_util.CHECKSUM_FUNCTIONS:
            raise ValueError(_('Checksum type %(checksumtype)s is not supported') %
                             {'checksumtype': checksumtype})

        value = self.checksums.get(checksumtype)

        if not value:
            if self.checksumtype == checksumtype:
                value = self.checksum
            elif not self.downloaded:
                raise PulpCodedException(error_code=error_codes.RPM1008,
                                         checksumtype=checksumtype)
            else:
                _LOGGER.debug(_('calculating checksum of type %(ctype)s for unit %(unit)s') %
                              {'ctype': checksumtype, 'unit': self})
                try:
                    with open(self._storage_path) as f:
                        value = server_util.calculate_checksums(f, [checksumtype])[checksumtype]
                except IOError as e:
                    if e.errno == errno.ENOENT:
                        raise PulpCodedException(platform_error_codes.PLP0048, unit=str(self))
                    else:
                        raise
            self.checksums[checksumtype] = value
            self.save()

        return value


class Distribution(UnitMixin, FileContentUnit):
    """
    Model for an RPM distribution tree (also sometimes referenced as an installable tree).
    A distribution tree is described by a file in root of an RPM repository named either
    "treeinfo" or ".treeinfo". This INI file is used by system installers to boot from a URL.
    It describes the operating system or product contained in the distribution tree and
    where the bootable media is located for various platforms (where platform means
    'x86_64', 'xen', or similar).

    Note: This model should be rewritten. It fails to capture what a distribution tree
          is and what is required for one to be valid. It seems that distribution trees
          are produced by Anaconda tooling, namely the Lorax project. Red Hat's Release
          Engineering team maintains a library, productmd, which provides tools to work
          with product, compose, and installation media metadata. We should should use
          this tool to work with "treeinfo" files so we don't duplicate work other teams
          have done. The issue tracking this is https://pulp.plan.io/issues/1769

    The description of the "treeinfo" format is included below, originally take from
    https://release-engineering.github.io/productmd/treeinfo-1.0.html

    ```
    [header]
    version = 1.0                         ; metadata version; format: $major<int>.$minor<int>

    [release]
    name = <str>                          ; release name, for example: "Fedora",
                                          ; "Red Hat Enterprise Linux", "Spacewalk"
    short = <str>                         ; release short name, for example: "F", "RHEL",
                                          ; "Spacewalk"
    version = <str>                       ; release version, for example: "21", "7.0", "2.1"
    is_layered = <bool=False>             ; typically False for an operating system, True otherwise

    [base_product]
    name = <str>                          ; base product name, for example: "Fedora",
                                          ; "Red Hat Enterprise Linux"
    short = <str>                         ; base product short name, for example: "F", "RHEL"
    version = <str>                       ; base product *major* version, for example: "21", "7"

    [tree]
    arch = <str>                          ; tree architecture, for example x86_64
    build_timestamp = <int|float>         ; tree build time timestamp; format: unix time
    platforms = <str>[, <str> ...]        ; supported platforms; for example x86_64,xen
    variants = <str>[, <str> ...]         ; UIDs of available variants, for example
                                          ; "Server,Workstation"

    [checksums]
    ; checksums of selected files in a tree:
    ; * all repodata/repomd.xml
    ; * all images captured in [images-*] and [stage2] sections
    $path = $checksum_type<str>:checksum_value<str>

    [images-$platform<str>]
    ; images compatible with particular $platform
    $file_name = $relative_path<str>

    [stage2]
    ; optional section, available only on bootable media with Anaconda installer
    instimage = <str>                     ; relative path to Anaconda instimage (obsolete)
    mainimage = <str>                     ; relative path to Anaconda stage2 image

    [media]
    ; optional section, available only on media
    discnum = <int>                       ; disc number
    totaldiscs = <int>                    ; number of discs in media set

    [variant-$variant_uid]
    id = <str>                            ; variant ID
    uid = <str>                           ; variant UID ($parent_UID.$ID)
    name = <str>                          ; variant name
    type = <str>                          ; variant, optional
    variants = <str>[,<str>...]           ; UIDs of child variants
    addons = <str>[,<str>...]             ; UIDs of child addons

    ; variant paths
    ; all paths are relative to .treeinfo location
    packages = <str>                      ; directory with binary RPMs
    repository = <str>                    ; YUM repository with binary RPMs
    source_packages = <str>               ; directory with source RPMs
    source_repository = <str>             ; YUM repository with source RPMs
    debug_packages = <str>                ; directory with debug RPMs
    debug_repository = <str>              ; YUM repository with debug RPMs
    identity = <str>                      ; path to a pem file that identifies a product

    [addon-$addon_uid]
    id = <str>                            ; addon ID
    uid = <str>                           ; addon UID ($parent_UID.$ID)
    name = <str>                          ; addon name
    type = addon

    ; addon paths
    ; see variant paths

    [general]
    ; WARNING.0 = This section provides compatibility with pre-productmd treeinfos.
    ; WARNING.1 = Read productmd documentation for details about new format.
    family = <str>                        ; equal to [release]/name
    version = <str>                       ; equal to [release]/version
    name = <str>                          ; equal to "$family $version"
    arch = <str>                          ; equal to [tree]/arch
    platforms = <str>[,<str>...]          ; equal to [tree]/platforms
    packagedir = <str>                    ; equal to [variant-*]/packages
    repository = <str>                    ; equal to [variant-*]/repository
    timestamp = <int>                     ; equal to [tree]/build_timestamp
    variant = <str>                       ; variant UID of first variant (sorted alphabetically)
    ```

    Older "treeinfo" file formats exist. They vary from repository to repository, but look
    similar to the following:

    ```
    [general]
    name = Fedora-Server-21
    family = Fedora-Server
    timestamp = 1417653911.68
    variant = Server
    version = 21
    packagedir =
    arch = x86_64

    [stage2]
    mainimage = LiveOS/squashfs.img

    [images-x86_64]
    kernel = images/pxeboot/vmlinuz
    initrd = images/pxeboot/initrd.img
    upgrade = images/pxeboot/upgrade.img
    boot.iso = images/boot.iso

    [images-xen]
    kernel = images/pxeboot/vmlinuz
    initrd = images/pxeboot/initrd.img
    upgrade = images/pxeboot/upgrade.img

    [checksums]
    images/efiboot.img = sha256:de48c8b25f03861c00c355ccf78108159f1f2aa63d0d63f92815146c24f60164
    images/macboot.img = sha256:da76ff5490b4ae7e123f19b8f4b36efd6b7c435073551978d50c5181852a87f5
    images/product.img = sha256:ffce14a7a95be20b36f302cb0698be8c19fda798807d3d63a491d6f7c1b23b5b
    images/boot.iso = sha256:56af126a50c227d779a200b414f68ea7bcf58e21c8035500cd21ba164f85b9b4
    images/pxeboot/vmlinuz = sha256:81c28a439f1d23786057d3b57db66e00b2b1a39b64d54de1a90cf2617e53...
    images/pxeboot/initrd.img = sha256:aadebd07c4c0f19304f0df7535a8f4218e5141602f95adec08ad1e22f...
    images/pxeboot/upgrade.img = sha256:224d098fb3903583b491692c5e0e1d20ea840d51f4da671ced97d422...
    repodata/repomd.xml = sha256:3af1609aa27949bf1e02e9204a7d4da7efee470063dadbc3ea0be3ef7f1f4d14
    ```

    Note that not all fields may be present. For example, some RHEL 5 repositories do not
    contain the `variant` field in their "treeinfo" files.

    :ivar distribution_id: The concatenation of the values of `family`, `variant`, `version`,
                           and `arch`
    :ivar family:          Equivalent to the "treeinfo" [release] section's 'name' field. For
                           example, 'Fedora', 'Red Hat Enterprise Linux', or 'Spacewalk'.
    :ivar variant:         The variant contained in the repository. The current version of the
                           model is problematic since some old "treeinfo" files don't have
                           variants, and some new repositories have _several_ variants. Since
                           we currently use the [general] section of the "treeinfo" file, this
                           variant will be the first variant (alphabetically) in the distribution
                           tree.
    :ivar version:         Equivalent to the "treeinfo" [release] section's 'version' field.
                           For example, '21', '7.0', and '2.1'
    :ivar arch:            Equivalent to the "treeinfo" [tree] section's 'arch' field. The
                           architecture the tree was built for. For example, 'x86_64'.
    :ivar files:           A somewhat hodgepodge list of files in the distribution. It contains
                           some of the files described in the "treeinfo" files, and potentially
                           files described by an XML file called "PULP_DISTRIBUTION.xml".
    :ivar timestamp:       Equivalent to the "treeinfo" [tree] section's 'build_timestamp' field.
    :ivar packagedir:      Equivalent to the "treeinfo" [variant-*] section's 'packages' field.
                           It's possible in the future that distribution trees will have several
                           different packagedir fields, so we need to fix our model here.
    :ivar version_sort_index: ?
    """

    distribution_id = mongoengine.StringField(required=True)
    family = mongoengine.StringField(required=True)
    variant = mongoengine.StringField(default='')
    version = mongoengine.StringField(required=True)
    arch = mongoengine.StringField(required=True)

    files = mongoengine.ListField()
    timestamp = mongoengine.FloatField()
    packagedir = mongoengine.StringField()

    # Pretty sure the version_sort_index is never used for Distribution units
    version_sort_index = mongoengine.StringField()

    # For backward compatibility
    _ns = mongoengine.StringField(default='units_distribution')
    _content_type_id = mongoengine.StringField(required=True, default='distribution')

    unit_key_fields = ('distribution_id', 'family', 'variant', 'version', 'arch')
    unit_display_name = 'Distribution'
    unit_description = 'Kickstart trees and all accompanying files'

    meta = {'collection': 'units_distribution',
            'indexes': [
                'distribution_id', 'family', 'variant', 'version', 'arch'],
            'allow_inheritance': False}

    SERIALIZER = serializers.Distribution

    def __init__(self, *args, **kwargs):
        """
        Adds the distribution_id if not already defined, which is derived based on the other 4 unit
        key fields.
        """
        super(Distribution, self).__init__(*args, **kwargs)
        if not self.distribution_id:
            # the original importer leaves out any elements that are None, so
            # we will blindly trust that here.
            id_pieces = filter(lambda x: x is not None,
                               ('ks',
                                self.family,
                                self.variant,
                                self.version,
                                self.arch))
            self.distribution_id = '-'.join(id_pieces)

    def __str__(self):
        """
        Since `variant` might be None (itself a dirty work-around the model being wrong),
        this method must be overridden.
        :return:
        """
        return '%s: %s' % (self._content_type_id,
                           '-'.join(getattr(self, name) or 'None' for name in self.unit_key_fields))

    def list_files(self):
        """
        List absolute paths to files associated with this unit.

        :return: A list of absolute file paths.
        :rtype: list
        """
        _dir = self.storage_path
        return [os.path.join(_dir, f['relativepath']) for f in self.files]

    @property
    def relative_path(self):
        """
        For this model, the relative path will be a directory in which all
        related files get stored. For most unit types, this path is to one
        file.
        """
        return self.distribution_id

    @classmethod
    def pre_save_signal(cls, sender, document, **kwargs):
        """
        Generate the version & Release sort index before saving

        :param sender: sender class
        :type sender: object
        :param document: Document that sent the signal
        :type document: pulp_rpm.plugins.db.models.Distribution
        """
        document.version_sort_index = version_utils.encode(document.version)
        super(Distribution, cls).pre_save_signal(sender, document, **kwargs)


class DRPM(NonMetadataPackage):
    # TODO add docstring to this class

    # Unit Key Fields
    epoch = mongoengine.StringField(required=True)
    filename = mongoengine.StringField(required=True)

    # Other Fields
    sequence = mongoengine.StringField()
    new_package = mongoengine.StringField()
    arch = mongoengine.StringField()
    size = mongoengine.IntField()
    oldepoch = mongoengine.StringField()
    oldversion = mongoengine.StringField()
    oldrelease = mongoengine.StringField()

    # For backward compatibility
    _ns = mongoengine.StringField(default='units_drpm')
    _content_type_id = mongoengine.StringField(required=True, default='drpm')

    unit_key_fields = ('epoch', 'version', 'release', 'filename', 'checksumtype', 'checksum')
    unit_display_name = 'DRPM'
    unit_description = 'DRPM'

    meta = {'collection': 'units_drpm',
            'indexes': [
                "epoch", "version", "release", "filename", "checksum"],
            'allow_inheritance': False}

    SERIALIZER = serializers.Drpm

    @property
    def relative_path(self):
        """
        This should only be used during the initial sync
        """
        return self.filename

    @property
    def download_path(self):
        """
        This should only be used during the initial sync
        """
        return self.filename


class RpmBase(NonMetadataPackage):
    """
    This class is designed to be sub-classed by both RPM and SRPM, as these two
    package types are similar. Most fields map to metadata fields in the RPM package
    format.

    :ivar arch: The target architecture for a package. For example, 'x86_64', 'i686',
                or 'noarch'.
    :type arch: mongoengine.StringField

    :ivar buildhost: Hostname of the system that built the package.
    :type buildhost: mongoengine.StringField

    :ivar changelog: A list of changelog entries for the package. The purpose of these
                     changelogs depend on the packager. Fedora uses to changelog
                     to document changes to the package's spec file. The format of each
                     entry is the time (in seconds since the epoch) of the changelog entry,
                     the author and release as a string, and the list of release notes as
                     a string.
    :type changelog: list of [int, basestring, basestring]

    :ivar checksum: The checksum of the package.
    :type checksum: mongoengine.StringField

    :ivar checksumtype: The checksum type used in the ``checksum`` field.
    :type checksumtype: mongoengine.StringField

    :ivar description: The human-readable description for a package.
    :type description: mongoengine.StringField

    :ivar epoch: The package's epoch.
    :type epoch: mongoengine.StringField

    :ivar files: All the files provided by this package. The dictionary has two keys: "file",
                 and "dir". "file" maps to a list of strings, which are paths to files the
                 package provides (for example, "/etc/pulp/server.conf". "dir" maps to a list
                 of directories the package owns (for example, "/etc/pulp").
    :type files: dict

    :ivar group: The RPM group this package is a part of. As of ``rpm-4.13.0``,
                 the following groups are documented in /usr/share/doc/rpm/GROUPS:
                    Amusements/Games
                    Amusements/Graphics
                    Applications/Archiving
                    Applications/Communications
                    Applications/Databases
                    Applications/Editors
                    Applications/Emulators
                    Applications/Engineering
                    Applications/File
                    Applications/Internet
                    Applications/Multimedia
                    Applications/Productivity
                    Applications/Publishing
                    Applications/System
                    Applications/Text
                    Development/Debuggers
                    Development/Languages
                    Development/Libraries
                    Development/System
                    Development/Tools
                    Documentation
                    System Environment/Base
                    System Environment/Daemons
                    System Environment/Kernel
                    System Environment/Libraries
                    System Environment/Shells
                    User Interface/Desktops
                    User Interface/X
                    User Interface/X Hardware Support
    :type group: mongoengine.StringField

    :ivar header_range: The byte range of the package; it contains the 'start' and 'end'
                        keys which have integer values representing a byte index.
    :type header_range: dict

    :ivar license: The license or licenses applicable to the package.
    :type license: mongoengine.StringField

    :ivar name: The package's name. For example, 'pulp-server' would be the
                name of a package with the NVRA 'pulp-server-2.8.0-1.el7.noarch.rpm'.
    :type name: mongoengine.StringField

    :ivar provides: List of packages/libraries this package provides. Each entry is a
                    dictionary with the "release", "epoch", "version", "flags", and "name"
                    field.
    :type provides: list of dict

    :ivar release: The release of a particular version of the package. Although this field
                   can technically be anything, packaging guidelines usually require it to
                   be an integer followed by the platform, e.g. '1.el7' or '3.f24'. This field
                   is incremented by the packager whenever a new release of the same version
                   is created.
    :type release: mongoengine.Stringfield

    :ivar requires: List of packages/libraries this package requires. Each entry is a dictionary
                    with the "release", "epoch", "version", "flags", and "name" field.
    :type requires: list of dict

    :ivar sourcerpm: Name of the source package (srpm) the package was built from.
    :type sourcerpm: mongoengine.StringField

    :ivar vendor: The name of the organization that produced the RPM.
    :type vendor: mongoengine.StringField

    :ivar size: size, in bytes, of this package. Note that the RPM has other size fields,
                namely the size of the archive portion of the package file and the size
                of the package when installed.
    :type size: mongoengine.IntField

    :ivar summary: Short description of the package.
    :type summary: mongoengine.StringField

    :ivar build_time: Time the package was built in seconds since the epoch.
    :type build_time: mongoengine.IntField

    :ivar time: The mtime of the package file in seconds since the epoch; this
                is the 'file' time attribute in the primary XML.
    :type time: mongoengine.IntField

    :ivar url: URL with more information about the packaged software. This could
               be the project's website or its code repository.
    :type url: mongoengine.StringField

    :ivar version: The version of the package. For example, '2.8.0'.
    :type version: mongoengine.Stringfield
    """

    # Unit Key Fields
    name = mongoengine.StringField(required=True)
    epoch = mongoengine.StringField(required=True)
    version = mongoengine.StringField(required=True)
    release = mongoengine.StringField(required=True)
    arch = mongoengine.StringField(required=True)

    # Other Fields
    build_time = mongoengine.IntField()
    buildhost = mongoengine.StringField()
    vendor = mongoengine.StringField()
    size = mongoengine.IntField()
    base_url = mongoengine.StringField()
    filename = mongoengine.StringField()
    relative_url_path = mongoengine.StringField()
    relativepath = mongoengine.StringField()
    group = mongoengine.StringField()

    provides = mongoengine.ListField()
    files = mongoengine.DictField()
    repodata = mongoengine.DictField(default={})
    description = mongoengine.StringField()
    header_range = mongoengine.DictField()
    sourcerpm = mongoengine.StringField()
    license = mongoengine.StringField()
    changelog = mongoengine.ListField()
    url = mongoengine.StringField()
    summary = mongoengine.StringField()
    time = mongoengine.IntField()
    requires = mongoengine.ListField()

    unit_key_fields = ('name', 'epoch', 'version', 'release', 'arch', 'checksumtype', 'checksum')

    meta = {'indexes': [
        "name", "epoch", "version", "release", "arch", "filename", "checksum",
        "checksumtype", "version_sort_index",
        ("version_sort_index", "release_sort_index")],
        'abstract': True}

    SERIALIZER = serializers.RpmBase

    CHECKSUM_TEMPLATE = '{{ checksum }}'
    CHECKSUMTYPE_TEMPLATE = '{{ checksumtype }}'
    PKGID_TEMPLATE = '{{ pkgid }}'
    DEFAULT_CHECKSUM_TYPES = (server_util.TYPE_MD5, server_util.TYPE_SHA1, server_util.TYPE_SHA256)

    def __init__(self, *args, **kwargs):
        super(RpmBase, self).__init__(*args, **kwargs)
        # raw_xml is only used during the initial sync
        self.raw_xml = ''

    @property
    def relative_path(self):  # TODO: what is this used for?
        """
        This should only be used during the initial sync
        """
        return os.path.join(
            self.name,
            self.version,
            self.release,
            self.arch,
            self.checksum,
            self.filename
        )

    @property
    def download_path(self):
        """
        This should only be used during the initial sync
        """
        return self.relativepath

    def render_primary(self, checksumtype):
        """
        Renders the primary XML with the requested checksum type

        :param checksumtype:   checksum type, such as sha1, sha256
        :type  checksumtype:   basestring

        :return:    primary XML for this unit
        :rtype:     basestring
        """
        metadata = self.repodata['primary']
        context = Context({'checksum': self.get_or_calculate_and_save_checksum(checksumtype),
                           'checksumtype': checksumtype})

        return self._render(metadata, context)

    def render_other(self, checksumtype):
        """
        Renders the other XML with the requested checksum type

        :param checksumtype:   checksum type, such as sha1, sha256
        :type  checksumtype:   basestring

        :return:    other XML for this unit
        :rtype:     basestring
        """
        metadata = self.repodata['other']
        context = Context({'pkgid': self.get_or_calculate_and_save_checksum(checksumtype)})
        return self._render(metadata, context)

    def render_filelists(self, checksumtype):
        """
        Renders the filelists XML with the requested checksum type

        :param checksumtype:   checksum type, such as sha1, sha256
        :type  checksumtype:   basestring

        :return:    filelists XML for this unit
        :rtype:     basestring
        """
        metadata = self.repodata['filelists']
        context = Context({'pkgid': self.get_or_calculate_and_save_checksum(checksumtype)})
        return self._render(metadata, context)

    @staticmethod
    def _render(template, context):
        """
        Given a template as a string and a Context object, returns the rendered result as a string.

        :param template:    a django template
        :type  template:    basestring
        :param context:     a django Context object with the required context for the template
        :type  context:     django.template.Context

        :return:    string that is the result of rendering the template with the context
        :rtype:     basestring
        """
        t = Template(template)
        rendered = t.render(context)
        if isinstance(rendered, unicode):
            rendered = rendered.encode('utf-8')

        return rendered

    def modify_xml(self):
        """
        Given a unit that has repodata XML snippets, modify them in several necessary ways. These
        include changing the location value and adding template strings to checksum elements.
        """
        faked_primary = utils.fake_xml_element(self.repodata['primary'])
        primary = faked_primary.find('package')

        faked_other = utils.fake_xml_element(self.repodata['other'])
        other = faked_other.find('package')

        faked_filelists = utils.fake_xml_element(self.repodata['filelists'])
        filelists = faked_filelists.find('package')

        self._update_location(primary, self.filename)
        self._templatize_checksum(primary)
        self._templatize_pkgid(other)
        self._templatize_pkgid(filelists)

        self.repodata['primary'] = utils.remove_fake_element(utils.element_to_text(faked_primary))
        self.repodata['other'] = utils.remove_fake_element(utils.element_to_text(other))
        self.repodata['filelists'] = utils.remove_fake_element(utils.element_to_text(filelists))

    @classmethod
    def _templatize_pkgid(cls, element):
        """
        Modify the passed-in element so that its "pkgid" element contains a template string

        :param element: XML element that has a "pkgid" attribute
        :type  element: xml.etree.ElementTree.Element
        """
        element.attrib['pkgid'] = cls.PKGID_TEMPLATE

    @classmethod
    def _templatize_checksum(cls, package_element):
        """
        Modify the checksum element to contain template strings as the text, and as the "type"
        attribute.

        :param package_element: XML element with name "package" from primary.xml
        :type  package_element: xml.etree.ElementTree.Element
        """
        c_elem = package_element.find('checksum')
        c_elem.text = cls.CHECKSUM_TEMPLATE
        c_elem.attrib['type'] = cls.CHECKSUMTYPE_TEMPLATE

    @staticmethod
    def _update_location(package_element, filename):
        """
        When uploading a unit, the href in the generated xml's location tag is
        based on the content unit file path, which is an autogenerated unique
        value. This sets the href back to the unit filename, which matches the
        published repo layout and allows uploaded units to again be downloaded
        from the published repo.

        :param package_element: XML element with name "package" from primary.xml
        :type  package_element: xml.etree.ElementTree.Element
        :param filename:        the name of the RPM's file
        :type  filename:        basestring
        """
        location_element = package_element.find('location')
        location_element.set('href', filename)


class RPM(RpmBase):
    # TODO add docstring to this class

    # For backward compatibility
    _ns = mongoengine.StringField(default='units_rpm')
    _content_type_id = mongoengine.StringField(required=True, default='rpm')

    unit_display_name = 'RPM'
    unit_description = 'RPM'
    unit_referenced_types = ['erratum']

    meta = {'collection': 'units_rpm',
            'allow_inheritance': False}


class SRPM(RpmBase):
    # TODO add docstring to this class

    # For backward compatibility
    _ns = mongoengine.StringField(default='units_srpm')
    _content_type_id = mongoengine.StringField(required=True, default='srpm')

    unit_display_name = 'SRPM'
    unit_description = 'SRPM'

    meta = {
        'collection': 'units_srpm',
        'allow_inheritance': False}


class Errata(UnitMixin, ContentUnit):
    # TODO add docstring to this class
    errata_id = mongoengine.StringField(required=True)
    status = mongoengine.StringField()
    updated = mongoengine.StringField(required=True, default='')
    description = mongoengine.StringField()
    issued = mongoengine.StringField()
    pushcount = mongoengine.StringField()
    references = mongoengine.ListField()
    reboot_suggested = mongoengine.BooleanField()
    errata_from = mongoengine.StringField(db_field='from')
    severity = mongoengine.StringField()
    rights = mongoengine.StringField()
    version = mongoengine.StringField()
    release = mongoengine.StringField()
    type = mongoengine.StringField()
    pkglist = mongoengine.ListField()
    title = mongoengine.StringField()
    solution = mongoengine.StringField()
    summary = mongoengine.StringField()

    # For backward compatibility
    _ns = mongoengine.StringField(default='units_erratum')
    _content_type_id = mongoengine.StringField(required=True, default='erratum')

    unit_key_fields = ('errata_id',)
    unit_display_name = 'Erratum'
    unit_description = 'Erratum advisory information'
    unit_referenced_types = ['rpm']

    meta = {'indexes': [
        "version", "release", "type", "status", "updated",
        "issued", "severity", "references"],
        'collection': 'units_erratum',
        'allow_inheritance': False}

    SERIALIZER = serializers.Errata

    mutable_erratum_fields = ('status', 'updated', 'description', 'pushcount', 'references',
                              'reboot_suggested', 'errata_from', 'severity', 'rights', 'version',
                              'release', 'type', 'title', 'solution', 'summary')

    @property
    def rpm_search_dicts(self):
        ret = []
        for collection in self.pkglist:
            for package in collection.get('packages', []):
                if len(package.get('sum') or []) == 2:
                    checksum = package['sum'][1]
                    checksumtype = server_util.sanitize_checksum_type(package['sum'][0])
                elif 'sums' in package and 'type' in package:
                    # these are the field names we get from an erratum upload.
                    # I have no idea why they are different.
                    checksum = package['sums']
                    checksumtype = server_util.sanitize_checksum_type(package['type'])
                else:
                    checksum = None
                    checksumtype = None
                rpm = RPM(name=package['name'], epoch=package['epoch'],
                          version=package['version'], release=package['release'],
                          arch=package['arch'], checksum=checksum,
                          checksumtype=checksumtype)
                unit_key = rpm.unit_key
                for key in ['checksum', 'checksumtype']:
                    if unit_key[key] is None:
                        del unit_key[key]
                ret.append(unit_key)
        return ret

    @staticmethod
    def _check_packages(existing_packages, new_packages):
        """
        Check if the new packages are the same as the existing ones.

        :param existing_packages: list of packages presented in the existing erratum
        :type  existing_packages: list of dicts

        :param new_packages: list of packages presented in the new erratum
        :type  new_packages: list of dicts

        :return: True, if the lists of packages are equal
        :rtype: bool
        """
        if len(existing_packages) == len(new_packages):
            existing_packages.sort(key=itemgetter('filename'))
            new_packages.sort(key=itemgetter('filename'))
            return existing_packages == new_packages
        return False

    def merge_errata(self, other):
        """
        Merge two errata with the same errata_id.

        There are two parts:
        - merging of the pkglists in case of the erratum with the same id in different repositories
        - overwriting the erratum metadata based on the `updated` field

        NOTE: The first part should be eliminated after we change the way erratum is stored in the
        MongoDB.

        :param other: The erratum we are combining with this one
        :type  other: pulp_rpm.plugins.db.models.Errata
        """
        self.merge_pkglists_and_save(other)
        if self.update_needed(other):
            for field_name in self.mutable_erratum_fields:
                setattr(self, field_name, getattr(other, field_name))

    def update_needed(self, other):
        """
        Decide based on the `updated` field if the update of the existing erratum is needed.

        The `updated` field is just a string in the MongoDB, so there is no strict format for this
        date-time field. If we are not able to parse the `updated` field either in existing
        erratum or in the new erratum, the metadata of existing erratum won't be updated.

        :param other: potentially a newer version of the erratum
        :type  other: pulp_rpm.plugins.db.models.Errata

        :return: True if the other erratum is newer than the existing one
        :rtype:  bool
        """
        err_msg = _('Fail to update the %(which)s erratum %(id)s.')
        existing_err_msg = err_msg % {'which': 'existing', 'id': self.errata_id}
        other_err_msg = err_msg % {'which': 'uploaded', 'id': self.errata_id}
        existing_updated_dt = util.errata_format_to_datetime(self.updated, msg=existing_err_msg)
        new_updated_dt = util.errata_format_to_datetime(other.updated, msg=other_err_msg)
        return new_updated_dt > existing_updated_dt

    def merge_pkglists_and_save(self, other):
        """
        Merge pkglists of the two errata and save the result to the database.

         - add _pulp_repo_id to old collection if packages are the same
         - update existing collection if the other collection is newer and from the same
           repository
         - otherwise add a new collection

        :param other: The erratum we are combining with the existing one
        :type  other: pulp_rpm.plugins.db.models.Errata

        """
        existing_pkglist_map = {}
        for idx, p in enumerate(self.pkglist):
            package_name = p['name']
            package_repo_id = p.get('_pulp_repo_id')
            pkglist_key = (package_name, package_repo_id)
            existing_pkglist_map[pkglist_key] = idx

        collections_to_add = []
        for new_collection in other.pkglist:
            coll_name = new_collection['name']

            # collection with such name does not contain _pulp_repo_id
            if (coll_name, None) in existing_pkglist_map:
                coll_idx = existing_pkglist_map[(coll_name, None)]
                existing_collection = self.pkglist[coll_idx]
                if self._check_packages(existing_collection['packages'],
                                        new_collection['packages']):
                    existing_collection['_pulp_repo_id'] = new_collection['_pulp_repo_id']
                else:
                    collections_to_add.append(new_collection)

            # collection with such name and _pulp_repo_id already exists
            elif (coll_name, new_collection['_pulp_repo_id']) in existing_pkglist_map:
                if self.update_needed(other):
                    coll_idx = existing_pkglist_map[
                        (coll_name, new_collection['_pulp_repo_id'])]
                    self.pkglist[coll_idx]['packages'] = new_collection['packages']

            # no collection with such name or no collection with such name and _pulp_repo_id
            else:
                collections_to_add.append(new_collection)

        # It is very important to call save() here to save recent modifications to the existing
        # collections in the pkglist in the database before new collections will be added to
        # the pkglist, because mongoengine does not allow to modify existing items in the list
        # and add new items to the list at the same time.
        self.save()
        self.pkglist += collections_to_add
        self.save()


class PackageGroup(UnitMixin, ContentUnit):
    # TODO add docstring to this class
    package_group_id = mongoengine.StringField(required=True)
    repo_id = mongoengine.StringField(required=True)

    description = mongoengine.StringField()
    default_package_names = mongoengine.ListField()
    optional_package_names = mongoengine.ListField()
    mandatory_package_names = mongoengine.ListField()
    name = mongoengine.StringField()
    default = mongoengine.BooleanField(default=False)
    display_order = mongoengine.IntField()
    user_visible = mongoengine.BooleanField(default=False)
    translated_name = mongoengine.DictField()
    translated_description = mongoengine.DictField()
    langonly = mongoengine.StringField()
    conditional_package_names = mongoengine.ListField()

    # For backward compatibility
    _ns = mongoengine.StringField(default='units_package_group')
    _content_type_id = mongoengine.StringField(required=True, default='package_group')

    unit_key_fields = ('package_group_id', 'repo_id')
    unit_display_name = 'Package Group'
    unit_description = 'Yum Package group information'

    meta = {
        'indexes': [
            'package_group_id', 'repo_id', 'name', 'mandatory_package_names',
            'conditional_package_names', 'optional_package_names', 'default_package_names'
        ],
        'collection': 'units_package_group',
        'allow_inheritance': False}

    SERIALIZER = serializers.PackageGroup

    @property
    def all_package_names(self):
        names = []
        names.extend(self.mandatory_package_names)
        names.extend(self.default_package_names)
        names.extend(self.optional_package_names)
        # TODO: conditional package names
        return names


class PackageCategory(UnitMixin, ContentUnit):
    # TODO add docstring to this class
    package_category_id = mongoengine.StringField(required=True)
    repo_id = mongoengine.StringField(required=True)

    description = mongoengine.StringField()
    packagegroupids = mongoengine.ListField()
    translated_description = mongoengine.DictField()
    translated_name = mongoengine.DictField()
    display_order = mongoengine.IntField()
    name = mongoengine.StringField()

    # For backward compatibility
    _ns = mongoengine.StringField(default='units_package_category')
    _content_type_id = mongoengine.StringField(required=True, default='package_category')

    unit_key_fields = ('package_category_id', 'repo_id')
    unit_display_name = 'Package Category'
    unit_description = 'Yum Package category information'

    meta = {
        'indexes': [
            'package_category_id', 'repo_id', 'name', 'packagegroupids'
        ],
        'collection': 'units_package_category',
        'allow_inheritance': False}

    SERIALIZER = serializers.PackageCategory


class PackageEnvironment(UnitMixin, ContentUnit):
    # TODO add docstring to this class
    package_environment_id = mongoengine.StringField(required=True)
    repo_id = mongoengine.StringField(required=True)

    group_ids = mongoengine.ListField()
    description = mongoengine.StringField()
    translated_name = mongoengine.DictField()
    translated_description = mongoengine.DictField()
    options = mongoengine.ListField()
    display_order = mongoengine.IntField()
    name = mongoengine.StringField()

    # For backward compatibility
    _ns = mongoengine.StringField(default='units_package_environment')
    _content_type_id = mongoengine.StringField(required=True, default='package_environment')

    unit_key_fields = ('package_environment_id', 'repo_id')
    unit_display_name = 'Package Environment'
    unit_description = 'Yum Package environment information'

    meta = {
        'indexes': ['package_environment_id', 'repo_id', 'name', 'group_ids'],
        'collection': 'units_package_environment',
        'allow_inheritance': False}

    SERIALIZER = serializers.PackageEnvironment

    @property
    def optional_group_ids(self):
        return [d.get('group') for d in self.options]


class PackageLangpacks(UnitMixin, ContentUnit):
    # TODO add docstring to this class
    repo_id = mongoengine.StringField(required=True)
    matches = mongoengine.ListField()

    # For backward compatibility
    _ns = mongoengine.StringField(default='units_package_langpacks')
    _content_type_id = mongoengine.StringField(required=True, default='package_langpacks')

    unit_key_fields = ('repo_id',)

    meta = {
        'collection': 'units_package_langpacks',
        'allow_inheritance': False}

    SERIALIZER = serializers.PackageLangpacks


class YumMetadataFile(UnitMixin, FileContentUnit):
    # TODO add docstring to this class
    data_type = mongoengine.StringField(required=True)
    repo_id = mongoengine.StringField(required=True)

    checksum = mongoengine.StringField()
    checksum_type = mongoengine.StringField()

    # For backward compatibility
    _ns = mongoengine.StringField(default='units_yum_repo_metadata_file')
    _content_type_id = mongoengine.StringField(required=True, default='yum_repo_metadata_file')

    unit_key_fields = ('data_type', 'repo_id')
    unit_display_name = 'YUM Repository Metadata File'
    unit_description = 'YUM Repository Metadata File'

    meta = {
        'indexes': ['data_type'],
        'collection': 'units_yum_repo_metadata_file',
        'allow_inheritance': False}

    SERIALIZER = serializers.YumMetadataFile


# How many bytes we want to read into RAM at a time when calculating an ISO checksum
CHECKSUM_CHUNK_SIZE = 32 * 1024 * 1024


class ISO(FileContentUnit):
    """
    This is a handy way to model an ISO unit, with some related utilities.
    """
    name = mongoengine.StringField(required=True)
    checksum = mongoengine.StringField(required=True)
    size = mongoengine.IntField(required=True)

    # For backward compatibility
    _ns = mongoengine.StringField(default='units_iso')
    _content_type_id = mongoengine.StringField(required=True, default='iso')

    unit_key_fields = ('name', 'checksum', 'size')
    unit_display_name = 'ISO'
    unit_description = 'ISO'

    meta = {'collection': 'units_iso', 'allow_inheritance': False}

    SERIALIZER = serializers.ISO

    def validate_iso(self, storage_path, full_validation=True):
        """
        Validate that the name of the ISO is not the same as the manifest's name. Also, if
        full_validation is True, validate that the file found at self.storage_path matches the size
        and checksum of self. A ValueError will be raised if the validation fails.

        :param storage_path   : The path to the file to perform validation on
        :type  storage_path   : basestring

        :param full_validation: Whether or not to perform validation on the size and checksum of the
                                ISO. Name validation is always performed.
        :type  full_validation: bool
        """
        # Don't allow PULP_MANIFEST to be the name
        if self.name == ISOManifest.FILENAME:
            msg = _('An ISO may not be named %(name)s, as it conflicts with the name of the '
                    'manifest during publishing.')
            msg = msg % {'name': ISOManifest.FILENAME}
            raise ValueError(msg)

        if full_validation:
            with open(storage_path) as destination_file:
                # Validate the size
                actual_size = self.calculate_size(destination_file)
                if actual_size != self.size:
                    raise ValueError(_('Downloading <%(name)s> failed validation. '
                                       'The manifest specified that the file should be %('
                                       'expected)s bytes, but '
                                       'the downloaded file is %(found)s bytes.') % {
                                     'name': self.name,
                                     'expected': self.size,
                                     'found': actual_size})

                # Validate the checksum
                actual_checksum = self.calculate_checksum(destination_file)
                if actual_checksum != self.checksum:
                    raise ValueError(
                        _('Downloading <%(name)s> failed checksum validation. The manifest '
                          'specified the checksum to be %(c)s, but it was %(f)s.') % {
                            'name': self.name, 'c': self.checksum,
                            'f': actual_checksum})

    @staticmethod
    def calculate_checksum(file_handle):
        """
        Return the sha256 checksum of the given file-like object.

        :param file_handle: A handle to an open file-like object
        :type  file_handle: file-like object
        :return:            The file's checksum
        :rtype:             string
        """
        return file_utils.calculate_checksum(file_handle)

    @staticmethod
    def calculate_size(file_handle):
        """
        Return the size of the given file-like object in Bytes.

        :param file_handle: A handle to an open file-like object
        :type  file_handle: file-like object
        :return:            The file's size, in Bytes
        :rtype:             int
        """
        # Calculate the size by seeking to the end to find the file size with tell()
        return file_utils.calculate_size(file_handle)


class ISOManifest(object):
    """
    This class provides an API that is a handy way to interact with a PULP_MANIFEST file. It
    automatically
    instantiates ISOs out of the items found in the manifest.
    """
    # This is the filename that the manifest is published to
    FILENAME = 'PULP_MANIFEST'

    def __init__(self, manifest_file, repo_url):
        """
        Instantiate a new ISOManifest from the open manifest_file.

        :param manifest_file: An open file-like handle to a PULP_MANIFEST file
        :type  manifest_file: An open file-like object
        :param repo_url:      The URL to the repository that this manifest came from. This is used
                              to determine a url attribute for each ISO in the manifest.
        :type  repo_url:      str
        """
        # Make sure we are reading from the beginning of the file
        manifest_file.seek(0)
        # Now let's process the manifest and return a list of resources that we'd like to download
        manifest_csv = csv.reader(manifest_file)
        self._isos = []
        for unit in manifest_csv:
            name, checksum, size = unit
            iso = ISO(name=name, size=int(size), checksum=checksum)
            # Take a URL onto the ISO so we know where we can get it
            iso.url = urljoin(repo_url, name)
            self._isos.append(iso)

    def __iter__(self):
        """
        Return an iterator for the ISOs in the manifest.
        """
        return iter(self._isos)

    def __len__(self):
        """
        Return the number of ISOs in the manifest.
        """
        return len(self._isos)
