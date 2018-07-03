import collections
import os
from os import path

from pulp.server import util

from pulp_integrity import validator


class MissingStoragePath(validator.ValidationError):
    """Missing storage path error."""


class InvalidStoragePathSize(validator.ValidationError):
    """Invalid storage path error."""


class InvalidStoragePathChecksum(validator.ValidationError):
    """Invalid storage path checksum."""


class DarkContentError(validator.ValidationError):
    """Dark content path error."""


MISSING_ERROR = MissingStoragePath('The path was not found on the filesystem.')
SIZE_ERROR = InvalidStoragePathSize('The path has an invalid size on the filesystem.')
CHECKSUM_ERROR = InvalidStoragePathChecksum('The path has an invalid checksum on the filesystem.')
DARK_CONTENT = DarkContentError('The path has no content unit in the database.')

UnitPathFailure = collections.namedtuple('UnitPathFailure',
                                         validator.ValidationFailure._fields + ('path',))
UnitPathFailure.__nonzero__ = staticmethod(lambda: False)


class DownloadedFileContentUnitValidator(validator.MultiValidator):
    def applicable(self, unit):
        """This validator is applicable to downloaded units only.

        :param unit: the unit being checked
        :type unit: dict
        :returns: True/False
        """
        downloaded = unit.get('downloaded')
        return (
            super(DownloadedFileContentUnitValidator, self).applicable(unit) and
            downloaded
        )

    @staticmethod
    def failure_factory(validator, unit, repository, error):
        """This validator failure objects factory.

        :param validator: the validator that checked the units
        :type validator: pulp_integrity.validation.Validator
        :param: unit: the unit that failed the validation
        :type unit: dict
        :param repository: repo_id to link this failure to
        :type repository: basestring
        :param error: the ValidationError that occurred during the validation
        :type error: a ValidationError object
        :returns: a UnitPathFailure object
        """
        _storage_path = validator.get_unit_attribute(unit, '_storage_path')
        return UnitPathFailure(validator, unit, repository, error, _storage_path)


class ExistenceValidator(DownloadedFileContentUnitValidator):
    """Check that the unit._storage_path exists on the disk."""

    @validator.MultiValidator.affects_repositories(
        failure_factory=DownloadedFileContentUnitValidator.failure_factory)
    def validate(self, unit, *args):
        """Check the unit.

        :param unit: the unit to check
        :type unit: dict
        :param args: unused
        :returns: None
        :raises: MISSING_ERROR
        """
        _storage_path = self.get_unit_attribute(unit, '_storage_path')
        if not path.exists(_storage_path):
            raise MISSING_ERROR


class SizeValidator(DownloadedFileContentUnitValidator):
    """Check that the unit._storage_path size matches the unit.size."""

    def applicable(self, unit):
        """Only applicable to units having the size key.

        :param unit: the unit applicability of which is being checked
        :type unit: dict
        :returns: True/False
        """
        return super(SizeValidator, self).applicable(unit) and 'size' in unit

    @validator.MultiValidator.affects_repositories(
        failure_factory=DownloadedFileContentUnitValidator.failure_factory)
    def validate(self, unit, *args):
        """Check the unit.

        :param unit: the unit to check
        :type unit: dict
        :param args: unused
        :returns: None
        :raises: MISSING_ERROR/SIZE_ERROR
        """
        _storage_path, unitsize = self.get_unit_attributes(
            unit, '_storage_path', 'size')
        try:
            storagesize = path.getsize(_storage_path)
        except (IOError, OSError):
            raise MISSING_ERROR

        if unitsize != storagesize:
            raise SIZE_ERROR


class ChecksumValidator(DownloadedFileContentUnitValidator):
    """Check that the unit._storage_path checksum matches the unit.checksum."""

    def applicable(self, unit):
        """Only applicable to units having the checksum and the checksumtype keys.

        :param unit: the unit applicability of which is being checked
        :type unit: dict
        :returns: True/False
        """
        return (super(ChecksumValidator, self).applicable(unit) and
                'checksum' in unit and 'checksumtype' in unit)

    @validator.MultiValidator.affects_repositories(
        failure_factory=DownloadedFileContentUnitValidator.failure_factory)
    def validate(self, unit, *args):
        """Check the unit.

        :param unit: the unit to check
        :type unit: dict
        :param args: unused
        :returns: None
        :raises: MISSING_ERROR/CHECKSUM_ERROR
        """
        checksumtype, expected_checksum, _storage_path = self.get_unit_attributes(
            unit, 'checksumtype', 'checksum', '_storage_path')
        try:
            with open(_storage_path, 'rb') as fd:
                checksums = util.calculate_checksums(fd, [checksumtype])
        except (IOError, OSError):
            raise MISSING_ERROR
        if checksums[checksumtype] != expected_checksum:
            raise CHECKSUM_ERROR


class DarkContentValidator(validator.MultiValidator):
    """Checks that every file under /var/lib/pulp/content/units relates to exactly one unit."""

    def applicable(self, unit):
        """This validator is applicable to downloaded units only.

        :param unit: the unit to check applicability of
        :type unit: dict
        :returns: True/False
        """
        downloaded = unit.get('downloaded')
        return (
            super(DarkContentValidator, self).applicable(unit) and
            downloaded
        )

    def __init__(self):
        super(DarkContentValidator, self).__init__()
        self.paths = set()

    def setup(self, parsed_args):
        """Set this validator up.

        Walks the filesystem tree under /var/lib/pulp/content/units and collects all
        filenames found. Setting this up is might take considerable resources;
        couple of dozens of megabytes of RAM and IO-latency induced delay.
        An instance should be used as a singleton.

        :param parsed_args: parsed CLI arguments
        :type parsed_arg: argparse.Namespace
        :returns: None
        """
        self.unit_types = parsed_args.models.keys()
        for unit_type in self.unit_types:
            for dirpath, dirnames, filenames in os.walk(
                    '/var/lib/pulp/content/units/%s' % unit_type):
                for filename in filenames:
                    self.paths.add(path.join(dirpath, filename))

    @validator.MultiValidator.affects_repositories(
        failure_factory=DownloadedFileContentUnitValidator.failure_factory)
    def validate(self, unit, *args):
        """Check the unit.

        Remove unit._storage_path from self.filenames to account for every filename under
        /var/lib/pulp/content/units/

        :param unit: the unit to check
        :type unit: dict
        :param args: unused
        :returns: None
        :raises: MISSING_ERROR
        """
        _storage_path = self.get_unit_attribute(unit, '_storage_path')
        # A FileContentUnit has exactly a single storage path
        try:
            self.paths.remove(_storage_path)
        except KeyError:
            # double remove should not happen
            raise MISSING_ERROR

    @property
    def results(self):
        """Report unpaired filenames as dark content.

        :returns: an iterable over DarkPath validation results
        """
        for storage_path in self.paths:
            yield validator.DarkPath(self, storage_path, DARK_CONTENT)
