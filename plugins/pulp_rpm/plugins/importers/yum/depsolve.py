import logging

import mongoengine
from pulp.plugins.util.misc import paginate
from pulp.server.controllers import repository as repo_controller

from pulp_rpm.common import version_utils
from pulp_rpm.common import ids
from pulp_rpm.plugins.db import models


_LOGGER = logging.getLogger(__name__)


class Requirement(object):
    """
    This class represents a dependency requirement for a package. A dependency requirement must have
    a name of a package that is depended upon, and can optionally include epoch, version, release,
    and flags. The flags indicate which type of comparison should be performed, such as equality or
    greater than.
    """
    # These are the values that can be passed to the flags parameter
    EQ = 'EQ'  # Equal
    LT = 'LT'  # Less Than
    LE = 'LE'  # Less than or Equal
    GT = 'GT'  # Greater Than
    GE = 'GE'  # Greater than or Equal

    def __init__(self, name, epoch=None, version=None, release=None, flags=None):
        """
        Initialize the Requirement with the given parameters. If flags is not provided, it will be
        set to EQ by default.

        :param name:    The name of the package required by the Requirement
        :type  name:    basestring
        :param epoch:   The epoch that the requirement uses in comparison, if any
        :type  epoch:   basestring or int
        :param version: The version the requirement uses in comparison, if any
        :type  version: basestring
        :param release: The release the requirement uses in comparison, if any
        :type  release: basestring
        :param flags:   The type of comparison that should be performed by the Requirement. Valid
                        values for flags are represented by the classlevel attributes EQ, LT, LE,
                        GT, and GE. By default, EQ is used.
        :type  flags:   basestring
        """
        self.name = name
        self.epoch = epoch
        self.version = version
        self.release = release
        # no idea why this is plural, but that's how it looks in primary.xml
        self.flags = flags or self.EQ

    def __cmp__(self, other):
        """
        Compare a Requirement to any other object that has at least these attributes: name, epoch,
        version, and release. This method will return a negative value if self is "less than" other,
        0 if they are equal, and a positive value if self is "greater than" other. For example,
        a Requirement that references Firefox-23.0 compared to a Unit that references Firefox-23.1
        would return a negative value.

        The other object must have the same name as the Requirement, as it
        doesn't make sense to ask whether an object is greater or less than a Requirement when it
        has a different name. For example, a Requirement might reference Firefox-23.0, and other
        might be the package openssh-server-6.2. If this Requirement is asked to compare itself with
        openssh-server, it will raise ValueError.

        :param other: Any object that has the following attributes: name, epoch, version, and
                      release. An RPM Unit is an example of such an object.
        :type  other: object
        :return:      A negative value if self is less than other, 0 if self is equal to other, and
                      a positive value if self is greater than other.
        :rtype:       int
        """
        if self.name != other.name:
            raise ValueError('Comparison of objects with different names is not supported.')

        mine = [self.epoch, self.version, self.release]
        theirs = [other.epoch, other.version, other.release]
        # the encode function is rather picky about the type and length of its
        # argument, so we only call it for values that we know it will accept
        for i, value in enumerate(mine):
            if value:
                mine[i] = version_utils.encode(str(value))
        for i, value in enumerate(theirs):
            if value:
                theirs[i] = version_utils.encode(str(value))

        return cmp(mine, theirs)

    def __eq__(self, other):
        """
        Return True if self effectively "equals" other, False otherwise. This equality
        check will take into account name, epoch, version, and release, allowing the
        release to be omitted from either object.

        :param other: Any object that has the following attributes: name, epoch, version, and
                      release. An RPM Unit is an example of such an object.
        :type  other: object
        :return:      True if self and other are equal, False otherwise
        :rtype:       bool
        """

        # Simple case, they are entirely different
        if self.name != other.name:
            return False

        # Attempt to compare the version information
        mine_version = version_utils.encode(self.version)
        mine_release = version_utils.encode(self.release) if self.release else None
        mine = [self.epoch, mine_version, mine_release]

        theirs_version = version_utils.encode(other.version)
        theirs_release = version_utils.encode(other.release) if other.release else None
        theirs = [other.epoch, theirs_version, theirs_release]

        # Release is optional, so if it's omitted in either case, remove it entirely
        # from the check.
        if mine[2] is None or theirs[2] is None:
            mine = mine[:2]
            theirs = theirs[:2]

        return mine == theirs

    def __ne__(self, other):
        """
        Return True if self and other are unequal, False otherwise. This is the inverse of the
        __eq__() method, so please see the docblock for that method for further information.

        :param other: Any object that has the following attributes: name, epoch, version, and
                      release. An RPM Unit is an example of such an object.
        :type  other: object
        :return:      True if self and other are unequal, False otherwise
        :rtype:       bool
        """
        return not self == other

    def __repr__(self):
        return 'Require(name=%s, epoch=%s, version=%s, release=%s, flags=%s)' % (
            self.name, self.epoch, self.version, self.release, self.flags
        )

    @property
    def is_versioned(self):
        """
        Return True if the Requirement has a version attribute that is not None or empty string,
        False otherwise.

        :return: Whether the Requrement has a version
        :rtype:  bool
        """
        # don't need to check epoch or release, because if either of those are
        # present, "version" must be present also
        return self.version not in (None, '')

    def fills_requirement(self, unit):
        """
        Returns True if the given package will meet the requirement, False otherwise.

        :param unit:    a Unit object that will be examined to determine if it
                        fills this requirement
        :type unit:     pulp_rpm.plugins.db.models.RPM
        :return:        True if the unit satisfies the Requirement, False otherwise
        :rtype:         bool
        """
        if self.name != unit.name:
            return False

        # this is easier to use in the comparison than a full Unit object
        unit_as_namedtuple = unit.unit_key_as_named_tuple

        if self.flags == self.EQ:
            if self.is_versioned:
                return self == unit_as_namedtuple
            else:
                # If self doesn't have a version attribute, we can say that the package meets the
                # requirement since the package name is equal to the Requirement's name (we already
                # checked for that above).
                return True

        # yes, the operators might look backwards to you, but it's because
        # we have to put "self" on the left to get our own __cmp__ method.
        if self.flags == self.LT:
            return self > unit_as_namedtuple
        if self.flags == self.LE:
            return self >= unit_as_namedtuple
        if self.flags == self.GT:
            return self < unit_as_namedtuple
        if self.flags == self.GE:
            return self <= unit_as_namedtuple


class Solver(object):
    """
    Resolves RPM dependencies within a pulp repository
    """

    def __init__(self, source_repo):
        """
        :param source_repo: The source repository that is being searched
        :type  source_repo: pulp.server.db.model.Repository
        """
        super(Solver, self).__init__()
        self.source_repo = source_repo
        self._cached_source_with_provides = None
        self._cached_provides_tree = None
        self._cached_packages_tree = None

    def find_dependent_rpms(self, units):
        """
        Calls from outside this module probably want to call this method.

        Given an iterable of Units, return a set of units that satisfy
        the dependencies of those units. Dependencies are resolved only within the
        repository search by "self.search_method".

        :param units:   iterable of pulp_rpm.plugins.models.RPM
        :type  units:   iterable

        :return:        set of pulp_rpm.plugins.db.models.RPM instances which
                        satisfy the passed-in requirements. Please see match()
                        for details about the Units.

        :rtype:         set
        """
        reqs = self.get_requirements(units)
        return self.match(reqs)

    @property
    def _source_with_provides(self):
        """
        Returns a list of available packages with Provides info, and caches
        the result so it won't have to be re-generated.

        :return:    list of pulp_rpm.plugins.db.models.RPM
        :rtype      list
        """
        if self._cached_source_with_provides is None:
            self._cached_source_with_provides = self._build_source_with_provides()
        return self._cached_source_with_provides

    def _build_source_with_provides(self):
        """
        Get a list of all available packages with their "Provides" info.

        Note that the 'provides' metadata will be flattened via _trim_provides().

        :return:    list of pulp_rpm.plugins.db.models.RPM
        :rtype:     list
        """
        fields = list(models.RPM.unit_key_fields)
        fields.extend(['provides', 'version_sort_index', 'release_sort_index'])
        units = repo_controller.find_repo_content_units(
            repository=self.source_repo,
            repo_content_unit_q=mongoengine.Q(unit_type_id=ids.TYPE_ID_RPM),
            unit_fields=fields, yield_content_unit=True
        )
        return [self._trim_provides(unit) for unit in units]

    def _trim_provides(self, unit):
        """
        A method to flatten/strip the "provides" metadata to just the name when
        building the list of packages. See RHBZ #1185868.

        :param unit: unit to trim
        :type unit: pulp_rpm.plugins.db.models.RPM
        """
        new_provides = []
        for provide in unit.provides:
            new_provides.append(provide['name'])
        unit.provides = new_provides
        return unit

    @property
    def _provides_tree(self):
        """
        Returns a tree of "Provides" data and handles caching of that data once
        it's been created. See below for details on the data structure.

        :return:    dictionary as defined below in _build_provides_tree
        :rtype:     dict
        """
        if self._cached_provides_tree is None:
            self._cached_provides_tree = self._build_provides_tree()
            # if both trees have been created, remove the cached source list
            # so it can be garbage-collected
            if self._cached_packages_tree is not None:
                self._cached_source_with_provides = None
        return self._cached_provides_tree

    def _build_provides_tree(self):
        """
        Creates a tree of "Provides" data so that for any given "Provides" name,
        the newest version of each package that provides that capability can be
        easily accessed.

        In the example below, "provide_nameA" is the value of a "Provides" statement
        such as "webserver". "package_name1" is the name of a package, such as "httpd".
        "package1_as_unit" is an instance of pulp.plugins.model.Unit
        for the newest version of that package which provides "provide_nameA".

        {
            'provide_nameA': {
                'package_name1': package1_as_unit,
                'package_name2': package2_as_unit,
            },

            'provide_nameB': {
                'package_name3': package3_as_unit,
            },
        }

        :return:    dictionary as defined above
        :rtype:     dict
        """
        source_units = self._source_with_provides
        tree = {}
        for unit in source_units:
            my_cmp_tuple = (unit.epoch, unit.version_sort_index,
                            unit.release_sort_index)
            for provide in unit.provides:
                unit_dict = tree.setdefault(provide, {})
                newest_version = unit_dict.get(unit.name, None)
                if newest_version:
                    newest_cmp_tuple = (newest_version.epoch,
                                        newest_version.version_sort_index,
                                        newest_version.release_sort_index)
                    if cmp(my_cmp_tuple, newest_cmp_tuple) == 1:
                        unit_dict[unit.name] = unit
                else:
                    unit_dict[unit.name] = unit
        return tree

    @property
    def _packages_tree(self):
        """
        Returns a tree of package data and handles caching of that data once
        it's been created. See below for details on the data structure.

        :return:    dictionary as defined below in _build_packages_tree
        :rtype:     dict
        """
        if self._cached_packages_tree is None:
            self._cached_packages_tree = self._build_packages_tree()
            # if both trees have been created, remove the cached source list
            # so it can be garbage-collected
            if self._cached_provides_tree is not None:
                self._cached_source_with_provides = None
        return self._cached_packages_tree

    def _build_packages_tree(self):
        """
        Creates a tree of package names, where values are lists of each version of
        that package. This is useful for filling a dependency, where it is valuable
        to consider each available version of a package name.

        {
            'package_name_1': [
                package1v1_as_unit,
                package1v2_as_unit,
            ],
            'package_name_2': [
                package2v1_as_unit,
            ],
        }

        :return:    dictionary as defined above
        :rtype:     dict
        """
        tree = {}
        for unit in self._source_with_provides:
            version_list = tree.setdefault(unit.name, [])
            version_list.append(unit)

        return tree

    def match(self, reqs):
        """
        Given an iterable of Requires, return a set of those units in the source
        iterable that satisfy the requirements.

        :param reqs:    list of requirements
        :type  reqs:    list of Require() instances
        :return:        set of pulp_rpm.plugins.db.models.RPM instances which
                        satisfy the passed-in requirements. These units will
                        be flattened of their "provides" info to save memory.
        :rtype:         set
        """

        provides_tree = self._provides_tree
        packages_tree = self._packages_tree
        deps = set()

        for req in reqs:
            # in order for a Requires: line to match a Provides, the requirement must
            # not specify a version
            if not req.is_versioned:
                providing_units = provides_tree.get(req.name, {})
                for unit in providing_units.itervalues():
                    deps.add(unit)

            # find in package names
            unit_list = packages_tree.get(req.name, [])
            applicable_units = filter(req.fills_requirement, unit_list)
            if applicable_units:
                newest = max(applicable_units)
                deps.add(newest)

        return deps

    def get_requirements(self, units):
        """
        For an iterable of RPM Units, return a generator of Require() instances that
        represent the requirements for those RPMs.

        :param units:   iterable of RPMs for which a query should be performed to
                        retrieve their Requires entries.
        :type  units:   iterable of pulp.plugins.model.Unit

        :return:    generator of Require() instances
        :rtype:     generator
        """
        for segment in paginate(units):
            unit_ids = [unit.id for unit in segment]
            fields = ['requires', 'id']
            for result in models.RPM.objects.filter(id__in=unit_ids).only(*fields):
                for require in result.requires or []:
                    yield Requirement(**require)
