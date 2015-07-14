import csv
import logging
import os
from gettext import gettext as _
from urlparse import urljoin

import mongoengine
from pulp.plugins.util import verification
from pulp.server.db.model import ContentUnit

from pulp_rpm.common import version_utils
from pulp_rpm.common import file_utils
from pulp_rpm.plugins import serializers

_LOGGER = logging.getLogger(__name__)


class Package(ContentUnit):

    meta = {
        'abstract': True,
    }

    def __str__(self):
        return '%s: %s' % (self.unit_type_id,
                           '-'.join(getattr(self, name) for name in self.unit_key_fields))


class VersionedPackage(Package):

    # All subclasses use both a version and a release
    version = mongoengine.StringField(required=True)
    release = mongoengine.StringField(required=True)

    # We generate these two
    version_sort_index = mongoengine.StringField()
    release_sort_index = mongoengine.StringField()

    meta = {
        'abstract': True,
    }

    @classmethod
    def pre_save_signal(cls, sender, document, **kwargs):
        """
        Generate the version & Release sort index before saving

        :param sender: sender class
        :type sender: object
        :param document: Document that sent the signal
        :type document: pulp_rpm.plugins.db.models.VersionedPackage
        """
        super(VersionedPackage, cls).pre_save_signal(sender, document, **kwargs)
        document.version_sort_index = version_utils.encode(document.version)
        document.release_sort_index = version_utils.encode(document.release)

    # Used by RPM, SRPM, DRPM
    @property
    def key_string_without_version(self):
        keys = [getattr(self, key) for key in self.unit_key_fields if
                key not in ['epoch', 'version', 'release', 'checksum', 'checksum_type']]
        keys.append(self.unit_type_id)
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

    # TODO DANGER DANGER, WHAT HAPPENS WITH MongoEngine BaseDocument
    def __cmp__(self, other):
        return cmp(
            self.complete_version_serialized,
            other.complete_version_serialized
        )


class Distribution(Package):

    distribution_id = mongoengine.StringField(required=True)
    family = mongoengine.StringField(required=True)
    variant = mongoengine.StringField(required=True)
    version = mongoengine.StringField(required=True)
    arch = mongoengine.StringField(required=True)

    files = mongoengine.ListField()
    timestamp = mongoengine.FloatField()
    packagedir = mongoengine.StringField()

    # Pretty sure the version_sort_index is never used for Distribution units
    version_sort_index = mongoengine.StringField()

    # For backward compatibility
    _ns = mongoengine.StringField(default='units_distribution')
    unit_type_id = mongoengine.StringField(db_field='_content_type_id', required=True,
                                           default='distribution')

    unit_key_fields = ('distribution_id', 'family', 'variant', 'version', 'arch')

    meta = {'collection': 'units_distribution',
            'indexes': [
                'distribution_id', 'family', 'variant', 'version', 'arch',
                # Unit key Index
                {
                    'fields': ['distribution_id', 'family', 'variant', 'version', 'arch'],
                    'unique': True
                }],
            'allow_inheritance': False}

    SERIALIZER = serializers.Distribution

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
        if not document.distribution_id:
            # the original importer leaves out any elements that are None, so
            # we will blindly trust that here.
            id_pieces = filter(lambda x: x is not None,
                               ('ks',
                                document.family,
                                document.variant,
                                document.version,
                                document.arch))
            document.distribution_id = '-'.join(id_pieces)
        super(Package, cls).pre_save_signal(sender, document, **kwargs)

    def process_download_reports(self, reports):
        """
        Once downloading is complete, add information about each file to this
        model instance. This is required before saving the new unit.

        :param reports: list of successful download reports
        :type  reports: list(pulp.common.download.report.DownloadReport)
        """
        if not isinstance(self.files, list):
            self.files = []

        for report in reports:
            # the following data model is mostly intended to match what the
            # previous importer generated.
            self.files.append({
                'checksum': report.data['checksum'],
                'checksumtype': verification.sanitize_checksum_type(report.data['checksumtype']),
                'downloadurl': report.url,
                'filename': os.path.basename(report.data['relativepath']),
                'fileName': os.path.basename(report.data['relativepath']),
                'item_type': "distribution",
                'pkgpath': os.path.join(
                    self.storage_path, os.path.dirname(report.data['relativepath']),
                ),
                'relativepath': report.data['relativepath'],
                'savepath': report.destination,
                'size': report.total_bytes,
            })


class DRPM(VersionedPackage):

    # Unit Key Fields
    epoch = mongoengine.StringField(required=True)
    file_name = mongoengine.StringField(db_field='filename', required=True)
    checksum_type = mongoengine.StringField(db_field='checksumtype', required=True)
    checksum = mongoengine.StringField(required=True)

    # Other Fields
    sequence = mongoengine.StringField()
    new_package = mongoengine.StringField()
    arch = mongoengine.StringField()
    size = mongoengine.IntField()
    old_epoch = mongoengine.StringField(db_field='oldepoch')
    old_version = mongoengine.StringField(db_field='oldversion')
    old_release = mongoengine.StringField(db_field='oldrelease')

    # For backward compatibility
    _ns = mongoengine.StringField(default='units_drpm')
    unit_type_id = mongoengine.StringField(db_field='_content_type_id', required=True,
                                           default='drpm')

    unit_key_fields = ('epoch', 'version', 'release', 'file_name', 'checksum_type', 'checksum')

    meta = {'collection': 'units_drpm',
            'indexes': [
                "epoch", "version", "release", "file_name", "checksum",
                # Unit key Index
                {
                    'fields': ["epoch", "version", "release", 'file_name', "checksum_type", "checksum"],
                    'unique': True
                }],
            'allow_inheritance': False}

    SERIALIZER = serializers.Drpm

    def __init__(self, *args, **kwargs):
        if 'checksum_type' in kwargs:
            kwargs['checksum_type'] = verification.sanitize_checksum_type(kwargs['checksum_type'])
        super(DRPM, self).__init__(*args, **kwargs)

    @property
    def relative_path(self):
        """
        This should only be used during the initial sync
        """
        return self.file_name

    @property
    def download_path(self):
        """
        This should only be used during the initial sync
        """
        return self.file_name


class RpmBase(VersionedPackage):

    # Unit Key Fields
    name = mongoengine.StringField(required=True)
    epoch = mongoengine.StringField(required=True)
    version = mongoengine.StringField(required=True)
    release = mongoengine.StringField(required=True)
    arch = mongoengine.StringField(required=True)
    checksum_type = mongoengine.StringField(db_field='checksumtype', required=True)
    checksum = mongoengine.StringField(required=True)

    # Other Fields
    build_time = mongoengine.IntField()
    buildhost = mongoengine.StringField()
    vendor = mongoengine.StringField()
    size = mongoengine.IntField()
    base_url = mongoengine.StringField()
    file_name = mongoengine.StringField(db_field='filename')
    relative_url_path = mongoengine.StringField()
    relative_path = mongoengine.StringField(db_field='relativepath')
    group = mongoengine.StringField()

    provides = mongoengine.ListField()
    files = mongoengine.DictField()
    repodata = mongoengine.DictField(default={})
    description = mongoengine.StringField()
    header_range = mongoengine.DictField()
    source_rpm = mongoengine.StringField(db_field='sourcerpm')
    license = mongoengine.StringField()
    changelog = mongoengine.ListField()
    url = mongoengine.StringField()
    summary = mongoengine.StringField()
    time = mongoengine.IntField()
    requires = mongoengine.ListField()

    # For backward compatibility
    _ns = mongoengine.StringField(default='units_rpm')
    unit_type_id = mongoengine.StringField(db_field='_content_type_id', required=True,
                                           default='rpm')

    unit_key_fields = ('name', 'epoch', 'version', 'release', 'arch', 'checksum_type', 'checksum')

    meta = {'indexes': [
                "name", "epoch", "version", "release", "arch", "file_name", "checksum",
                "checksum_type", "version_sort_index",
                ("version_sort_index", "release_sort_index"),
                # Unit key Index
                {
                    'fields': ["name", "epoch", "version", "release", "arch",
                               "checksum_type", "checksum"],
                    'unique': True
                }],
            'abstract': True}

    SERIALIZER = serializers.RpmBase

    def __init__(self, *args, **kwargs):
        if 'checksum_type' in kwargs:
            kwargs['checksum_type'] = verification.sanitize_checksum_type(kwargs['checksum_type'])
        super(RpmBase, self).__init__(*args, **kwargs)
        # raw_xml is only used during the initial sync
        self.raw_xml = ''

    @property
    def download_path(self):
        """
        This should only be used during the initial sync
        """
        return os.path.join(self.checksum, self.file_name)


class RPM(RpmBase):

    # For backward compatibility
    _ns = mongoengine.StringField(default='units_rpm')
    unit_type_id = mongoengine.StringField(db_field='_content_type_id', required=True,
                                           default='rpm')
    meta = {'collection': 'units_rpm',
            'allow_inheritance': False}


class SRPM(RpmBase):

    # For backward compatibility
    _ns = mongoengine.StringField(default='units_srpm')
    unit_type_id = mongoengine.StringField(db_field='_content_type_id', required=True,
                                           default='srpm')
    meta = {
        'collection': 'units_srpm',
        'allow_inheritance': False}


class Errata(Package):

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
    unit_type_id = mongoengine.StringField(db_field='_content_type_id', required=True,
                                           default='erratum')

    unit_key_fields = ('errata_id',)

    meta = {'indexes': [
        "errata_id", "version", "release", "type", "status", "updated",
        "issued", "severity", "references",
        # Unit key Index
        {
            'fields': unit_key_fields,
            'unique': True
        }],
        'collection': 'units_erratum',
        'allow_inheritance': False}

    SERIALIZER = serializers.Errata

    @property
    def rpm_search_dicts(self):
        ret = []
        for collection in self.pkglist:
            for package in collection.get('packages', []):
                if len(package.get('sum') or []) == 2:
                    checksum = package['sum'][1]
                    checksumtype = verification.sanitize_checksum_type(package['sum'][0])
                elif 'sums' in package and 'type' in package:
                    # these are the field names we get from an erratum upload.
                    # I have no idea why they are different.
                    checksum = package['sums']
                    checksumtype = verification.sanitize_checksum_type(package['type'])
                else:
                    checksum = None
                    checksumtype = None
                rpm = RPM(name=package['name'], epoch=package['epoch'],
                          version=package['version'], release=package['release'],
                          arch=package['arch'], checksum=checksum,
                          checksum_type=checksumtype)
                unit_key = rpm.unit_key
                for key in ['checksum', 'checksum_type']:
                    if unit_key[key] is None:
                        del unit_key[key]
                ret.append(unit_key)
        return ret


class PackageGroup(Package):

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
    unit_type_id = mongoengine.StringField(db_field='_content_type_id', required=True,
                                           default='package_group')

    unit_key_fields = ('package_group_id', 'repo_id')

    meta = {
        'indexes': [
            'package_group_id', 'repo_id', 'name', 'mandatory_package_names',
            'conditional_package_names',
            'optional_package_names', 'default_package_names',
                # Unit key Index
                {
                    'fields': ('package_group_id', 'repo_id'),
                    'unique': True
                }],
            'collection': 'units_package_group',
            'allow_inheritance': False}

    SERIALIZER = serializers.PackageGroup
    #
    # UNIT_KEY_NAMES = ('id', 'repo_id')
    # TYPE = ids.TYPE_ID_PKG_GROUP

    @property
    def all_package_names(self):
        names = []
        names.extend(self.mandatory_package_names)
        names.extend(self.default_package_names)
        names.extend(self.optional_package_names)
        # TODO: conditional package names
        return names


class PackageCategory(Package):

    package_category_id = mongoengine.StringField(required=True)
    repo_id = mongoengine.StringField(required=True)

    description = mongoengine.StringField()
    group_ids = mongoengine.ListField(db_field='packagegroupids')
    translated_description = mongoengine.DictField()
    translated_name = mongoengine.DictField()
    display_order = mongoengine.IntField()
    name = mongoengine.StringField()

    # For backward compatibility
    _ns = mongoengine.StringField(default='units_package_category')
    unit_type_id = mongoengine.StringField(db_field='_content_type_id', required=True,
                                           default='package_category')

    unit_key_fields = ('package_category_id', 'repo_id')

    meta = {
        'indexes': [
            'package_category_id', 'repo_id', 'name', 'group_ids',
            # Unit key Index
            {
                'fields': ('package_category_id', 'repo_id'),
                'unique': True
            }],
            'collection': 'units_package_category',
            'allow_inheritance': False}

    SERIALIZER = serializers.PackageCategory
    # UNIT_KEY_NAMES = ('id', 'repo_id')
    # TYPE = ids.TYPE_ID_PKG_CATEGORY
    #
    # def __init__(self, id, repo_id, metadata):
    #     Package.__init__(self, locals())
    #
    # @property
    # def group_names(self):
    #     return self.metadata.get('packagegroupids', [])


class PackageEnvironment(Package):
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
    unit_type_id = mongoengine.StringField(db_field='_content_type_id', required=True,
                                           default='package_environment')

    unit_key_fields = ('package_environment_id', 'repo_id')

    meta = {
        'indexes': [
            'package_environment_id', 'repo_id', 'name', 'group_ids',
            # Unit key Index
            {
                'fields': ('package_environment_id', 'repo_id'),
                'unique': True
            }],
        'collection': 'units_package_environment',
        'allow_inheritance': False}

    SERIALIZER = serializers.PackageEnvironment

    # UNIT_KEY_NAMES = ('id', 'repo_id')
    # TYPE = ids.TYPE_ID_PKG_ENVIRONMENT

    # def __init__(self, id, repo_id, metadata):
    #     Package.__init__(self, locals())

    # @property
    # def group_ids(self):
    #     return self.metadata.get('group_ids', [])

    # @property
    # def options(self):
    #     return self.metadata.get('options', [])

    @property
    def optional_group_ids(self):
        return [d.get('group') for d in self.options]


class YumMetadataFile(Package):
    data_type = mongoengine.StringField(required=True)
    repo_id = mongoengine.StringField(required=True)

    checksum = mongoengine.StringField()
    checksum_type = mongoengine.StringField()

    # For backward compatibility
    _ns = mongoengine.StringField(default='units_yum_repo_metadata_file')
    unit_type_id = mongoengine.StringField(db_field='_content_type_id', required=True,
                                           default='yum_repo_metadata_file')

    unit_key_fields = ('data_type', 'repo_id')

    meta = {
        'indexes': [
            'data_type',
            # Unit key Index
            {
                'fields': ('data_type', 'repo_id'),
                'unique': True
            }],
        'collection': 'units_yum_repo_metadata_file',
        'allow_inheritance': False}

    SERIALIZER = serializers.YumMetadataFile

    # UNIT_KEY_NAMES = ('data_type', 'repo_id')
    # TYPE = ids.TYPE_ID_YUM_REPO_METADATA_FILE

    # def __init__(self, data_type, repo_id, metadata):
    #     Package.__init__(self, locals())
    #
    # @property
    # def relative_dir(self):
    #     """
    #     returns the relative path to the directory where the file should be
    #     stored. Since we don't have the filename in the metadata, we can't
    #     derive the full path here.
    #     """
    #     return self.repo_id

#
# TYPE_MAP = {
#     Distribution.TYPE: Distribution,
#     DRPM.TYPE: DRPM,
#     Errata.TYPE: Errata,
#     PackageCategory.TYPE: PackageCategory,
#     PackageGroup.TYPE: PackageGroup,
#     PackageEnvironment.TYPE: PackageEnvironment,
#     RPM.TYPE: RPM,
#     SRPM.TYPE: SRPM,
#     YumMetadataFile.TYPE: YumMetadataFile,
# }
#
# # put the NAMEDTUPLE attribute on each model class
# for model_class in TYPE_MAP.values():
#     model_class.NAMEDTUPLE = namedtuple(model_class.TYPE, model_class.UNIT_KEY_NAMES)


# def from_typed_unit_key_tuple(typed_tuple):
#     """
#     This assumes that the __init__ method takes unit key arguments in order
#     followed by a dictionary for other metadata.
#
#     :param typed_tuple:
#     :return:
#     """
#     package_class = TYPE_MAP[typed_tuple[0]]
#     args = typed_tuple[1:]
#     foo = {'metadata': {}}
#     return package_class.from_package_info(*args, **foo)


# ------------ ISO Models --------------- #

# How many bytes we want to read into RAM at a time when calculating an ISO checksum
CHECKSUM_CHUNK_SIZE = 32 * 1024 * 1024


class ISO(ContentUnit):
    """
    This is a handy way to model an ISO unit, with some related utilities.
    """
    name = mongoengine.StringField(required=True)
    checksum = mongoengine.StringField(required=True)
    size = mongoengine.IntField(required=True)

    # For backward compatibility
    _ns = mongoengine.StringField(default='units_iso')
    unit_type_id = mongoengine.StringField(db_field='_content_type_id', required=True,
                                           default='iso')

    unit_key_fields = ('name', 'checksum', 'size')

    meta = {
        'indexes': [
            # Unit key Index
            {
                'fields': ('name', 'checksum', 'size'),
                'unique': True
            }],
        'collection': 'units_iso',
        'allow_inheritance': False}

    SERIALIZER = serializers.ISO

    # TYPE = ids.TYPE_ID_ISO
    # UNIT_KEY_ISO = ('name', 'size', 'checksum')

    # def __init__(self, name, size, checksum, unit=None):
    #     """
    #     Initialize an ISO, with its name, size, and checksum.
    #
    #     :param name:     The name of the ISO
    #     :type  name:     basestring
    #     :param size:     The size of the ISO, in bytes
    #     :type  size:     int
    #     :param checksum: The SHA-256 checksum of the ISO
    #     :type  checksum: basestring
    #     """
    #     self.name = name
    #     self.size = size
    #     self.checksum = checksum
    #
    #     # This is the Unit that the ISO represents. An ISO doesn't always have a Unit backing it,
    #     # particularly during repository synchronization or ISO uploads when the ISOs are being
    #     # initialized.
    #     self._unit = unit

    # @classmethod
    # def from_unit(cls, unit):
    #     """
    #     Construct an ISO out of a Unit.
    #     """
    #     return cls(unit.unit_key['name'], unit.unit_key['size'], unit.unit_key['checksum'], unit)
    #
    # def init_unit(self, conduit):
    #     """
    #     Use the given conduit's init_unit() call to initialize a unit, and store the unit as
    #     self._unit.
    #
    #     :param conduit: The conduit to call init_unit() to get a Unit.
    #     :type  conduit: pulp.plugins.conduits.mixins.AddUnitMixin
    #     """
    #     relative_path = os.path.join(self.name, self.checksum, str(self.size), self.name)
    #     unit_key = {'name': self.name, 'size': self.size, 'checksum': self.checksum}
    #     metadata = {}
    #     self._unit = conduit.init_unit(self.TYPE, unit_key, metadata, relative_path)

    # def save_unit(self, conduit):
    #     """
    #     Use the given conduit's save_unit() call to save self._unit.
    #
    #     :param conduit: The conduit to call save_unit() with.
    #     :type  conduit: pulp.plugins.conduits.mixins.AddUnitMixin
    #     """
    #     conduit.save_unit(self._unit)
    #
    # @property
    # def storage_path(self):
    #     """
    #     Return the storage path of the Unit that underlies this ISO.
    #     """
    #     return self._unit.storage_path

    def validate_iso(self, storage_path, full_validation=True):
        """
        Validate that the name of the ISO is not the same as the manifest's name. Also, if
        full_validation is True, validate that the file found at self.storage_path matches the size
        and checksum of self. A ValueError will be raised if the validation fails.

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
