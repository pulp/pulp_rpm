import logging
import os

import solv

from pulp.plugins.util import misc as misc_utils
from pulp.server.db import model as server_model

from pulp_rpm.common import ids
from pulp_rpm.plugins.db import models


_LOGGER = logging.getLogger(__name__)


def setattr_conversion(attr_name, set_none=False):
    def outer(conversion):
        def inner(solvable, unit):
            ret = conversion(solvable, unit)
            if not set_none and ret is None:
                return
            setattr(solvable, attr_name, ret)
        return inner
    return outer


def attr_conversion(attr_name, default=None):
    def outer(conversion=lambda sovlable, unit: unit):
        def inner(solvable, unit):
            return conversion(solvable, unit.get(attr_name, default))
        return inner
    return outer


def multiattr_conversion(*attribute_conversions):
    def outer(conversion):
        def inner(solvable, unit, *args, **kwargs):
            largs = []
            for ac in attribute_conversions:
                largs.append(ac(solvable, unit))
            largs.extend(args)
            return conversion(solvable, *largs, **kwargs)
        return inner
    return outer


def utf8_conversion(conversion=lambda solvable, unit: unit):
    def inner(solvable, unit):
        ret = conversion(solvable, unit)
        if ret is not None:
            return ret.encode('utf-8')
        return ret
    return inner


def repeated_attr_conversion(attribute_conversion):
    def outer(conversion):
        def inner(solvable, unit):
            for value in attribute_conversion(solvable, unit):
                conversion(solvable, value)
        return inner
    return outer


def plain_attribute_factory(attr_name):
    return setattr_conversion(attr_name)(utf8_conversion(attr_conversion(attr_name)()))


@utf8_conversion
@multiattr_conversion(
    attr_conversion('epoch')(),
    attr_conversion('version')(),
    attr_conversion('release')()
)
def evr_unit_conversion(solvable, epoch, version, release):
    if version is None:
        return
    return '{}{}{}'.format(
        '{}:'.format(epoch) if epoch else '',
        version,
        '-{}'.format(release) if release else ''
    )


evr_attribute = setattr_conversion('evr')(evr_unit_conversion)


@multiattr_conversion(
    utf8_conversion(attr_conversion('name')()),
    attr_conversion('flags')(),
    evr_unit_conversion
)
def rpm_dependency_conversion(solvable, unit_name, unit_flags, unit_evr,
                              attr_name, dependency_key=None):
    """Set the solvable dependencies.

    The dependencies of a unit are stored as a list of dictionaries,
    containing following values:
            name: <unit name> or a rich dep string; mandatory
            version: version of the dependency; optional
            epoch: epoch of the dependency; optional
            release: release of the dependency; optional
            flags: AND/OR; optional; if missing meaning by default AND

    These values are parsed by librpm.
    There are two cases how libsolv addresses the dependencies:

    * rich: the name of the dependency contains all required information:
        '(foo >= 1.0-3 AND bar != 0.9)'
        all the other attribute values are ignored

    * generic: the name, version, epoch, release and flags attributes
        are processed explicitly

    The dependency list is either of the provides, requires or the weak
    dependencies, the current case being stored under self.attr_name.

    Libsolv tracks a custom Dep object to represent a dependency of a
    solvable object; these are created in the pool object:

        dependency = pool.Dep('foo')

    The relationship to the solvable is tracked by a Rel pool object:

        relationship = pool.Rel(solv.REL_AND, pool.Dep(evr))

    where the evr is the 'epoch:version-release' string. The relationship
    is then recorded on the solvable explicitly by:

        solvable.add_deparray(solv.SOLVABLE_PROVIDES, relationship)

    If no explict relationship is provided in the flags attribute,
    the dependency can be used directly:

        solvable.add_deparray(solv.SOLVABLE_PROVIDES, dependency)

    :param solvable: a libsolv solvable object
    :type solvable: a libsolv solvable
    :param unit: the content unit to get the dependencies from
    :type unit: an object or a dictionary
    :returns: None
    """
    # e.g SOLVABLE_PROVIDES, SOLVABLE_REQUIRES...
    keyname = dependency_key or getattr(solv, 'SOLVABLE_{}'.format(attr_name.upper()))
    pool = solvable.repo.pool
    if unit_name.startswith('('):
        # the Rich/Boolean dependencies have just the 'name' attribute
        # this is always in the form: '(foo >= 1.2 with foo < 2.0)'
        dep = pool.parserpmrichdep(unit_name)
    else:
        # generic dependencies provide at least a solvable name
        dep = pool.Dep(unit_name)
        if unit_flags:
            # in case the flags unit attribute is populated, use it as
            # a solv.Rel object to denote solvable--dependency
            # relationship dependency in this case is a relationship
            # towards the dependency made from the 'flags', e.g:
            # solv.REL_EQ, and the evr fields
            if unit_flags == 'EQ':
                rel_flags = solv.REL_EQ
            elif unit_flags == 'LT':
                rel_flags = solv.REL_LT
            elif unit_flags == 'GT':
                rel_flags = solv.REL_GT
            elif unit_flags == 'LE':
                rel_flags = solv.REL_EQ | solv.REL_LT
            elif unit_flags == 'GE':
                rel_flags = solv.REL_EQ | solv.REL_GT
            else:
                raise ValueError('Unsupported dependency flags %s' % unit_flags)
            dep = dep.Rel(rel_flags, pool.Dep(unit_evr))
        # register the constructed solvable dependency
        solvable.add_deparray(keyname, dep)


def rpm_dependency_attribute_factory(attribute_name, dependency_key=None):
    return repeated_attr_conversion(attr_conversion(attribute_name, default=[])())(
        lambda solvable, unit: rpm_dependency_conversion(
            solvable, unit, attribute_name, dependency_key=dependency_key
        ))


def rpm_filelist_conversion(solvable, unit):
    """A specific, rpm-unit-type filelist attribute conversion."""
    repodata = solvable.repo.first_repodata()
    unit_files = unit.get('files', {}).get('file', [])
    unit_files.extend(unit.get('files', {}).get('dir', []))
    for filename in unit_files:
        dirname = os.path.dirname(filename).encode('utf-8')
        dirname_id = repodata.str2dir(dirname, create=True)
        repodata.add_dirstr(solvable.id, solv.SOLVABLE_FILELIST,
                            dirname_id, os.path.basename(filename).encode('utf-8'))


def unit_solvable_converter(solv_repo, unit, *attribute_factories):
    """Create a factory of a content unit--solv.Solvable converter.

    Each attribute factory either calls setattr on a solvable with a converted attribute value
    or processes the attribute value and changes the state of either the solvable being created
    or the solv.Repo or both by e.g adding dependencies.

    :param attribute_factories: the attribute factories to use for the conversion
    :type attribute_factories: a list of (solvable, unit, repo=None) -> None callables
    :param solv_repo: the repository the unit is being added into
    :type solv_repo: solv.Repo
    :param unit: the unit being converted
    :type unit: pulp_rpm.plugins.models.Model
    :return: the solvable created.
    :rtype: solv.Solvable
    """
    solvable = solv_repo.add_solvable()
    for attribute_factory in attribute_factories:
        attribute_factory(solvable, unit)
    return solvable


def unit_solvable_converter_factory(*attribute_factories):
    return lambda solv_repo, unit: unit_solvable_converter(solv_repo, unit, *attribute_factories)


rpm_unit_solvable_factory = unit_solvable_converter_factory(
    # An RPM content unit nests dependencies in a dict format
    # Would be provided by pulp_rpm
    plain_attribute_factory('name'),
    evr_attribute,
    plain_attribute_factory('arch'),
    plain_attribute_factory('vendor'),
    rpm_dependency_attribute_factory('requires'),
    rpm_dependency_attribute_factory('provides'),
    rpm_dependency_attribute_factory('recommends'),
    rpm_filelist_conversion,
)


class UnitSolvableMapping(object):
    def __init__(self, pool, type_factory_mapping):
        self.type_factory_mapping = type_factory_mapping
        self.pool = pool
        self.mapping = {}
        self.repos = {}

    def _register(self, unit, solvable):
        self.mapping.setdefault(solvable.id, unit['id'])
        self.mapping.setdefault(unit['id'], solvable)
        _LOGGER.debug('Loaded unit %(u)s as %(s)s', {'u': unit['id'], 's': solvable})

    def add_repo_units(self, units, repo_name, installed=False):
        repo = self.repos.get(repo_name)
        if not repo:
            repo = self.repos.setdefault(repo_name, self.pool.add_repo(repo_name))
            repodata = repo.add_repodata()
        else:
            repodata = repo.first_repodata()

        for unit in units:
            try:
                factory = self.type_factory_mapping[unit['_content_type_id']]
            except KeyError as err:
                raise ValueError('Unsupported unit type: {}', err)
            solvable = factory(repo, unit)
            self._register(unit, solvable)

        if installed:
            self.pool.installed = repo

        repodata.internalize()

    def get_unit_id(self, solvable):
        return self.mapping.get(solvable.id)

    def get_solvable(self, unit):
        return self.mapping.get(unit['id'])


class Solver(object):
    type_factory_mapping = {
        'rpm': rpm_unit_solvable_factory,
    }
    rpm_key_fields = list(models.RPM.unit_key_fields)
    rpm_fields = set([
        'name',
        'version',
        'release',
        'epoch',
        'arch',
        'vendor',
        'provides',
        'requires',
        'files',
        '_content_type_id',
        'id',
    ])
    rpm_exclude_fields = set([
        'id',
        'build_time',
        'buildhost',
        'pulp_user_metadata',
        '_content_type_id',
        'checksums',
        'size',
        'license',
        'group',
        '_ns',
        'filename',
        'epoch',
        'version',
        'version_sort_index',
        'provides',
        'files',
        'repodata',
        'description',
        '_last_updated',
        'time',
        'downloaded',
        'header_range',
        'arch',
        'name',
        '_storage_path',
        'sourcerpm',
        'checksumtype',
        'release_sort_index',
        'changelog',
        'url',
        'checksum',
        'signing_key',
        'summary',
        'relativepath',
        'release',
        'requires',
    ]) - rpm_fields

    def __init__(self, source_repo, target_repo=None):
        super(Solver, self).__init__()
        self.source_repo = source_repo
        self.target_repo = target_repo
        self._loaded = False
        self.pool = solv.Pool()
        # prevent https://github.com/openSUSE/libsolv/issues/267
        self.pool.setarch()
        self.mapping = UnitSolvableMapping(
            self.pool, self.type_factory_mapping)

    def _repo_units(self, repo_id):
        # NOTE: optimization; the solver has to visit every unit of a repo.
        # Using a custom, as-pymongo query to load the units as fast as possible.
        rcuq = server_model.RepositoryContentUnit.objects.filter(
            repo_id=repo_id, unit_type_id=ids.TYPE_ID_RPM).only('unit_id').as_pymongo()

        for rcu_batch in misc_utils.paginate(rcuq):
            rcu_ids = [rcu['unit_id'] for rcu in rcu_batch]
            for rpm in models.RPM.objects.filter(id__in=rcu_ids).exclude(
                    *self.rpm_exclude_fields).as_pymongo():
                rpm['id'] = rpm['_id']
                yield rpm

    def load(self):
        if self._loaded:
            return
        self._loaded = True
        repo_name = str(self.source_repo.repo_id)
        self.mapping.add_repo_units(self._repo_units(repo_name), repo_name)

        if self.target_repo:
            repo_name = str(self.target_repo.repo_id)
            self.mapping.add_repo_units(self._repo_units(repo_name), repo_name, installed=True)

        self.pool.addfileprovides()
        self.pool.createwhatprovides()
        _LOGGER.info('Loaded source repository %s', self.source_repo.repo_id)
        if self.target_repo:
            _LOGGER.info('Loaded target repository %s', self.target_repo.repo_id)

    def _units_jobs(self, units):
        flags = solv.Job.SOLVER_INSTALL | solv.Job.SOLVER_SOLVABLE
        for unit in units:
            solvable = self.mapping.get_solvable(unit)
            if not solvable:
                raise ValueError('Encountered an unknown unit {}'.format(unit))
            yield self.pool.Job(flags, solvable.id)

    def find_dependent_rpms(self, units):
        solver = self.pool.Solver()
        problems = solver.solve(self._units_jobs(units))
        # The solver is simply ignoring the problems encountered and proceeds associating
        # any new solvables/units. This might be reported back to the user one day over
        # the REST API.
        if problems:
            _LOGGER.warning('Encountered problems solving: %s',
                            ", ".join([str(problem) for problem in problems]))

        transaction = solver.transaction()
        ret = set()
        for solvables in misc_utils.paginate(transaction.newsolvables()):
            unit_ids = [self.mapping.get_unit_id(solvable) for solvable in solvables]
            for unit in models.RPM.objects.filter(id__in=unit_ids).only(*self.rpm_key_fields):
                ret.add(unit)

        return ret
