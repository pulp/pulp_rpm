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


class Require(object):
    EQ = 'EQ'
    LT = 'LT'
    LE = 'LE'
    GT = 'GT'
    GE = 'GE'

    def __init__(self, name, epoch=None, version=None, release=None, flags=None):
        self.name = name
        self.epoch = epoch
        self.version = version
        self.release = release
        # no idea why this is plural, but that's how it looks in primary.xml
        self.flags = flags or self.EQ

    def __cmp__(self, other):
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
        return (self.name, self.epoch, self.version, self.release) == \
               (other.name, other.epoch, other.version, other.release)

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        return 'Require(name=%s, epoch=%s, version=%s, release=%s, flags=%s)' % (
            self.name, self.epoch, self.version, self.release, self.flags
        )

    @property
    def is_versioned(self):
        # don't need to check epoch or release, because if either of those are
        # present, "version" must be present also
        return self.version not in (None, '')

    def fills_requirement(self, package):
        """
        Determines if the given package will meet the requirement.

        :param package: any object with attributes 'name', 'epoch', 'version',
                        and 'release'
        :type  package: object
        """

        if self.flags == self.EQ:
            if self.is_versioned:
                return self == package
            else:
                return self.name == package.name
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


def _build_provides_tree(source_packages):
    """

    :param source_packages: list of tuples (RPM namedtuple, "provides" list)
    :type  source_packages: list
    :return:
    """
    tree = {}
    for package, provides in source_packages:
        my_model = models.RPM.from_package_info(package._asdict())
        for provide in provides:
            provide_name = provide['name']
            package_dict = tree.setdefault(provide_name, {})
            newest_version = package_dict.get(package.name, tuple())
            if newest_version:
                newest_model = models.RPM.from_package_info(newest_version._asdict())
                package_dict[package.name] = max(my_model, newest_model).as_named_tuple
            else:
                package_dict[package.name] = package
    return tree


def _build_packages_tree(source_packages):
    tree = {}
    for package, provides in source_packages:
        version_list = tree.setdefault(package.name, [])
        version_list.append(package)

    return tree


def _get_source_with_provides(search_method):
    """

    :param search_method:   method that takes a UnitAssociationCriteria and
                            performs a search within a repository. Usually this
                            will be a method on a conduit such as "conduit.get_units"
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

    :param reqs:    list of requirements
    :type  reqs:    list
    :param source:  iterable of tuples (namedtuple, provides list)
    :type  source:  iterable
    :return:
    :rtype:         set
    """
    # we may have gotten a generator
    source = list(source)
    provides_tree = _build_provides_tree(source)
    packages_tree = _build_packages_tree(source)
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

    :param units:
    :type  units:    RPM.NAMEDTUPLE
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
                yield Require(**require)


def find_dependent_rpms(units, search_method):
    """

    :param units:           iterable of pulp.plugins.model.Unit
    :param search_method:   method that takes a UnitAssociationCriteria and
                            performs a search within a repository. Usually this
                            will be a method on a conduit such as "conduit.get_units"
    :type  search_method:   function
    :return:
    """
    reqs = get_requirements(units, search_method)
    source_with_provides = _get_source_with_provides(search_method)
    return match(reqs, source_with_provides)
