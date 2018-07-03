import collections
import os

from pulp.server.db import model
from pulp_rpm.plugins.distributors.yum import configuration as yum_config

from pulp_integrity import validator


class BrokenSymlinkError(validator.ValidationError):
    """A broken symlink error."""


class MissingSymlinkError(validator.ValidationError):
    """A missing symlink error."""


# the link can be None
SymlinkFailure = collections.namedtuple('SymlinkFailure',
                                        validator.ValidationFailure._fields + ('link',))
SymlinkFailure.__nonzero__ = staticmethod(lambda: False)


class YumDistributorValidatorMixin(object):
    applicable_types = set(['rpm', 'srpm', 'drpm'])

    def __init__(self):
        # the count of repositories&distributors is small compared to the count of units
        # therefore the cost of caching the repositories is amortized in a singleton validator
        self.repo_cache = {}

    def applicable(self, unit):
        """Check applicability of this validator.

        Only the self.applicable_types are relevant.

        :param unit: the content unit to check applicability of
        :type unit: dict
        :return: True/False
        """
        _content_type_id = unit.get('_content_type_id')
        return _content_type_id in self.applicable_types

    def setup(self, *args):
        """Cache unit_id -> [repo_id, ...] mappings to save some bandwitdht."""
        self.unit_id_repos = {}
        for mapping in model.RepositoryContentUnit.objects.aggregate(
                {'$match': {'unit_type_id': {'$in': list(self.applicable_types)}}},
                {'$group': {'_id': '$unit_id', 'repo_ids': {'$push': '$repo_id'}}},
                allowDiskUse=True
        ):
            self.unit_id_repos.setdefault(mapping['_id'], mapping['repo_ids'])

        # This cache size is 6M for 160k records on my test system
        # and takes approx 5s to set up
        # import sys
        # print('Caching {} relations'.format(len(self.unit_id_repos)))
        # print('Size {} MiB'.format(sys.getsizeof(self.unit_id_repos) // 1024**2))

    def get_distributors(self, validation, unit):
        """Get a (cached) unit/repo distributor.

        Only the yum_distributor type distributors are concerned.

        :param validation: currently ongoing validation
        :type validation: pulp_integrity.validation.Validation
        :param unit: the content unit being checked
        :type unit: dict
        :return: pulp.server.db.model.Distributor object
        """
        unit_id = self.get_unit_attribute(unit, '_id')
        repo_ids = self.unit_id_repos.get(unit_id, [])

        for repo_id in repo_ids:
            try:
                distributor = self.repo_cache[repo_id]
            except KeyError:
                self.repo_cache[repo_id] = distributor = model.Distributor.objects.get(
                    repo_id=repo_id,
                    distributor_type_id='yum_distributor'
                )
            yield distributor, repo_id


class BrokenSymlinksValidator(validator.MultiValidator, YumDistributorValidatorMixin):
    """Validates pulp_rpm-specific unit types: rpm, drpm, srpm.

    This validator detects whether a unit in a published repo has a symlink pointing to its
    _storage_path. There are two cases of expected, published symlink locations,
    if the yum_distributor is used:
      - repository/<unit.filename>; the old-style
      - repository/packages/<unit.filename[0].to_lower()>/unit.filename; the new-style
    Both are examined for presence of the symlink and for the symlink target status.
    """
    def __init__(self):
        validator.MultiValidator.__init__(self)
        YumDistributorValidatorMixin.__init__(self)
        self.http_publish_dir = yum_config.get_http_publish_dir()
        self.https_publish_dir = yum_config.get_https_publish_dir()
        self.broken_error = BrokenSymlinkError('The unit has a broken symlink.')
        self.missing_error = MissingSymlinkError('The unit has a missing symlink.')

    applicable = YumDistributorValidatorMixin.applicable
    setup = YumDistributorValidatorMixin.setup

    @staticmethod
    def old_symlink_name(filename):
        """Just the basename of unit.filename.

        :param filename: filename of a unit being checked
        :type unit: basestring
        :return: the path
        """
        return os.path.basename(filename)

    @staticmethod
    def new_symlink_name(filename):
        """The Packages/p/parrot.rpm style path.

        :param filename: the filename of a unit being checked
        :type filename: basestring
        :return: the path
        """
        filename = os.path.basename(filename)
        return os.path.join('Packages', filename[0].lower(), filename)

    def check_link(self, check_func, unit, repository, link):
        """Execute the unit--symlink check function.

        Converts the check_func result into a validator result.

        :param check_func: a function that implements the link checking
        :type check_func: callable(path)
        :param unit: the unit being checked
        :type unit: dict
        :param repository: the repo_id of the repo where the unit symlink is expected to be found
        :type repository: basestring
        :param link: the unit symlink being checked
        :return: validator.ValidationSuccess/SymlinkFailure
        """
        return (check_func(link) and validator.ValidationSuccess(self, unit) or
                SymlinkFailure(self, unit, repository, self.broken_error, link))

    def check_unit(self, check_func, unit, repository, publish_dir, relative_url):
        """Detects a missing, broken or stray unit symlink.

        Check that the unit has a symlink in the repo in either the old or the new path.

        :param check_func: a function that implements the link checking
        :type func: callable(path)
        :param unit: the unit being checked
        :type unit: dict
        :param repository: the repo_id of the repo where the unit symlink is expected to be found
        :type repository: basestring
        :param publish_dir: a directory where the symlink is  expected to be found
        :type publish_dir: basestring(path)
        :param relative_url: where the distributor stores the published repository
        :type relative_url: basestring(path)
        :return: validator.ValidationSuccess/SymlinkFailure
        """
        filename = self.get_unit_attribute(unit, 'filename')
        old_link = os.path.join(publish_dir, relative_url, self.old_symlink_name(filename))
        new_link = os.path.join(publish_dir, relative_url, self.new_symlink_name(filename))

        try:
            return self.check_link(check_func, unit, repository, new_link)
        except (IOError, OSError):
            # the link is missing on the filesystem; try the old-style link
            try:
                return self.check_link(check_func, unit, repository, old_link)
            except (IOError, OSError):
                return SymlinkFailure(self, unit, repository, self.missing_error, None)

    def validate(self, unit, validation):
        """Validate the unit symlinks in all relevant repositories.

        A not-yet-downloaded (lazy sync-ed) unit is checked for an expected symlink presence,
        a downloaded unit is checked both for the symlink presence as well as for the symlink
        target. Only published repository yum_distributors are considered.

        :param unit: the unit being checked
        :type unit: dict
        :param validation: the currently ongoing unit validation
        :type validation: pulp_integrity.validation.Validation
        :return: [pulp_integrity.validation.ValidationSuccess/SymlinkFailure, ...]
        """
        # select a checking function based on whether the unit is downloaded or not
        downloaded, _storage_path = self.get_unit_attributes(
            unit, 'downloaded', '_storage_path')
        check_func = (
            downloaded and
            (lambda link: os.path.exists(os.readlink(link)) and
             os.path.samefile(link, _storage_path)) or
            # just raise OSError in case the link is missing
            os.lstat
        )

        for distributor, repo_id in self.get_distributors(validation, unit):
            if not distributor.last_publish:
                continue
            relative_url = distributor.config['relative_url']
            if distributor.config.get('http', False):
                yield self.check_unit(check_func, unit, repo_id, self.http_publish_dir,
                                      relative_url)
            if distributor.config.get('https', False):
                yield self.check_unit(check_func, unit, repo_id, self.https_publish_dir,
                                      relative_url)
