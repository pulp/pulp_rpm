# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the License
# (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied, including the
# implied warranties of MERCHANTABILITY, NON-INFRINGEMENT, or FITNESS FOR A
# PARTICULAR PURPOSE.
# You should have received a copy of GPLv2 along with this software; if not,
# see http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt

import logging

from pulp.server.db.model.criteria import UnitAssociationCriteria

from pulp_rpm.common import version_utils, models
from pulp_rpm.plugins.importers.yum.utils import paginate

_LOGGER = logging.getLogger(__name__)


class Requirement(object):
    """
    This class represents a dependency requirement for a package. A dependency requirement must have
    a name of a package that is depended upon, and can optionally include epoch, version, release,
    and flags. The flags indicate which type of comparison should be performed, such as equality or
    greater than.
    """
    # These are the values that can be passed to the flags parameter
    EQ = 'EQ' # Equal
    LT = 'LT' # Less Than
    LE = 'LE' # Less than or Equal
    GT = 'GT' # Greater Than
    GE = 'GE' # Greater than or Equal

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
        Return True if self effectively "equals" other, False otherwise. For the sake of comparison,
        equality means that self and other have the same name, and that the __cmp__() method (see
        above) returns 0 when comparing the two.

        :param other: Any object that has the following attributes: name, epoch, version, and
                      release. An RPM Unit is an example of such an object.
        :type  other: object
        :return:      True if self and other are equal, False otherwise
        :rtype:       bool
        """
        if self.name != other.name:
            return False
        return self.__cmp__(other) == 0

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

    def fills_requirement(self, package):
        """
        Returns True if the given package will meet the requirement, False otherwise.

        :param package: any object with attributes 'name', 'epoch', 'version',
                        and 'release'
        :type  package: object
        :return:        True if the package satisfies the Requirement, False otherwise
        :rtype:         bool
        """
        if self.name != package.name:
            return False

        if self.flags == self.EQ:
            if self.is_versioned:
                return self == package
            else:
                # If self doesn't have a version attribute, we can say that the package meets the
                # requirement since the package name is equal to the Requirement's name (we already
                # checked for that above).
                return True
        # yes, the operators might look backwards to you, but it's because
        # we have to put "self" on the left to get our own __cmp__ method.
        if self.flags == self.LT:
            return self > package
        if self.flags == self.LE:
            return self >= package
        if self.flags == self.GT:
            return self < package
        if self.flags == self.GE:
            return self <= package


def find_dependent_rpms(units, search_method):
    """
    Calls from outside this module probably want to call this method.

    Given an iterable of Units, return a set of RPMs as named tuples that satisfy
    the dependencies of those units. Dependencies are resolved only within the
    repository search by the "search_method".

    :param units:           iterable of pulp.plugins.model.Unit
    :param search_method:   method that takes a UnitAssociationCriteria and
                            performs a search within a repository. Usually this
                            will be a method on a conduit such as "conduit.get_units"
    :type  search_method:   function

    :return:        set of pulp_rpm.common.models.RPM.NAMEDTUPLE instances which
                    satisfy the passed-in requirements
    :rtype:         set
    """
    reqs = get_requirements(units, search_method)
    source_with_provides = _get_source_with_provides(search_method)
    return match(reqs, source_with_provides)


def _build_provides_tree(source_packages):
    """
    Creates a tree of "Provides" data so that for any given "Provides" name,
    the newest version of each package that provides that capability can be
    easily accessed.

    In the example below, "provide_nameA" is the value of a "Provides" statement
    such as "webserver". "package_name1" is the name of a package, such as "httpd".
    "package1_as_named_tuple" is an instance of pulp_rpm.common.models.RPM.NAMEDTUPLE
    for the newest version of that package which provides "provide_nameA".

    {
        'provide_nameA': {
            'package_name1': package1_as_named_tuple,
            'package_name2': package2_as_named_tuple,
        },

        'provide_nameB': {
            'package_name3': package3_as_named_tuple,
        },
    }

    :param source_packages: list of tuples (RPM namedtuple, "provides" list)
    :type  source_packages: list

    :return:    dictionary as defined above
    :rtype:     dict
    """
    tree = {}
    for package, provides in source_packages:
        my_model = models.RPM.from_package_info(package._asdict())
        for provide in provides:
            provide_name = provide['name']
            package_dict = tree.setdefault(provide_name, {})
            newest_version = package_dict.get(package.name, tuple())
            if newest_version:
                # turn it into an RPM instance to get the version comparison
                newest_model = models.RPM.from_package_info(newest_version._asdict())
                package_dict[package.name] = max(my_model, newest_model).as_named_tuple
            else:
                package_dict[package.name] = package
    return tree


def _build_packages_tree(source_packages):
    """
    Creates a tree of package names, where values are lists of each version of
    that package. This is useful for filling a dependency, where it is valuable
    to consider each available version of a package name.

    {
        'package_name_1': [
            package1v1_as_named_tuple,
            package1v2_as_named_tuple,
        ],
        'package_name_2': [
            package2v1_as_named_tuple,
        ],
    }

    :param source_packages: list of tuples (RPM namedtuple, "provides" list)
    :type  source_packages: list

    :return:    dictionary as defined above
    :rtype:     dict
    """
    tree = {}
    for package, provides in source_packages:
        version_list = tree.setdefault(package.name, [])
        version_list.append(package)

    return tree


def _get_source_with_provides(search_method):
    """
    Get a generator of all available packages with their "Provides" info.

    :param search_method:   method that takes a UnitAssociationCriteria and
                            performs a search within a repository. Usually this
                            will be a method on a conduit such as "conduit.get_source_units"
    :type  search_method:   function

    :return:    generator of (pulp_rpm.common.models.RPM.NAMEDTUPLE, list of provides)
    """
    fields = list(models.RPM.UNIT_KEY_NAMES)
    fields.extend(['provides', 'id'])
    criteria = UnitAssociationCriteria(type_ids=[models.RPM.TYPE], unit_fields=fields)
    for unit in search_method(criteria):
        rpm = models.RPM.from_package_info(unit.unit_key)
        namedtuple = rpm.as_named_tuple
        yield (namedtuple, unit.metadata.get('provides', []))


def match(reqs, source):
    """
    Given an iterable of Requires, return a set of those packages in the source
    iterable that satisfy the requirements.

    :param reqs:    list of requirements
    :type  reqs:    list of Require() instances
    :param source:  iterable of tuples (namedtuple, provides list)
    :type  source:  iterable
    :return:        set of pulp_rpm.common.models.RPM.NAMEDTUPLE instances which
                    satisfy the passed-in requirements
    :rtype:         set
    """
    # we may have gotten a generator
    source = list(source)
    provides_tree = _build_provides_tree(source)
    packages_tree = _build_packages_tree(source)
    # allow garbage collection
    source = None
    deps = set()

    for req in reqs:
        # in order for a Requires: line to match a Provides, the requirement must
        # not specify a version
        if not req.is_versioned:
            providing_packages = provides_tree.get(req.name, {})
            for name, package in providing_packages.iteritems():
                deps.add(package)

        # find in package names
        package_list = packages_tree.get(req.name, [])
        applicable_packages = filter(req.fills_requirement, package_list)
        rpms = [models.RPM.from_package_info(package._asdict()) for package in applicable_packages]
        if rpms:
            deps.add(max(rpms).as_named_tuple)

    return deps


def get_requirements(units, search_method):
    """
    For an iterable of RPMs, return a generator of Require() instances that
    represent the requirements for those RPMs.

    :param units:   iterable of RPMs for which a query should be performed to
                    retrieve their Requires entries.
    :type  units:   iterable of pulp_rpm.common.models.RPM.NAMEDTUPLE
    :param search_method:   method that takes a UnitAssociationCriteria and
                            performs a search within a repository. Usually this
                            will be a method on a conduit such as "conduit.get_units"
    :type  search_method:   function

    :return:    generator of Require() instances
    """
    for segment in paginate(units):
        search_dicts = [unit.unit_key for unit in segment]
        filters = {'$or': search_dicts}
        fields = list(models.RPM.UNIT_KEY_NAMES)
        fields.extend(['requires', 'id'])
        criteria = UnitAssociationCriteria(type_ids=[models.RPM.TYPE], unit_filters=filters, unit_fields=fields)
        for result in search_method(criteria):
            for require in result.metadata.get('requires', []):
                yield Requirement(**require)


