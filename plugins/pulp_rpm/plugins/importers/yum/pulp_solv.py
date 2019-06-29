import collections
import itertools
import logging
import os

import solv

from pulp.plugins.util import misc as misc_utils
from pulp.server.db import model as server_model

from pulp_rpm.common import ids
from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.importers.yum import parse


_LOGGER = logging.getLogger(__name__)

# Constants for loading data from the database.
# 'pk' maps to 'id' in mongoengine, maps to '_id' in mongodb
BASE_UNIT_FIELDS = set(['pk', '_content_type_id'])

RPM_FIELDS = BASE_UNIT_FIELDS | set([
    'name',
    'version',
    'release',
    'epoch',
    'arch',
    'vendor',
    'provides',
    'requires',
    'files',
])

MODULE_FIELDS = BASE_UNIT_FIELDS | set([
    'name',
    'stream',
    'version',
    'context',
    'arch',
    'profiles',
    'dependencies',
    'artifacts',
])

MODULE_DEFAULTS_FIELDS = BASE_UNIT_FIELDS | set([
    'name',
    'stream',
    'repo_id',
])


def fetch_units_from_repo(repo_id):
    """Load the units from a repository.

    Extract all the content in the provided repository from the database and dump them to dicts.
    For performance, we bypass the ORM and do raw mongo queries, because the extra overhead of
    creating objects vs dicts wastes too much time and space.
    """
    def _repo_units(repo_id, type_id, model, fields):
        # NOTE: optimization; the solver has to visit every unit of a repo.
        # Using a custom, as-pymongo query to load the units as fast as possible.
        rcuq = server_model.RepositoryContentUnit.objects.filter(
            repo_id=repo_id, unit_type_id=type_id).only('unit_id').as_pymongo()

        for rcu_batch in misc_utils.paginate(rcuq):
            rcu_ids = [rcu['unit_id'] for rcu in rcu_batch]
            for unit in model.objects.filter(id__in=rcu_ids).only(*fields).as_pymongo():
                if not unit.get('id'):
                    unit['id'] = unit.get('_id')
                yield unit

    # order matters; e.g module loading requires rpm loading
    units = itertools.chain(
        _repo_units(repo_id, ids.TYPE_ID_RPM, models.RPM, RPM_FIELDS),
        _repo_units(
            repo_id, ids.TYPE_ID_MODULEMD, models.Modulemd, MODULE_FIELDS),
        _repo_units(
            repo_id, ids.TYPE_ID_MODULEMD_DEFAULTS, models.ModulemdDefaults,
            MODULE_DEFAULTS_FIELDS),
    )
    return units


def libsolv_formatted_evr(epoch, version, release):
    """Create an epoch-version-release string from the separate values.

    Pulp stores epoch-version-release separately, libsolv uses them together.
    Convert from Pulp separate values to a combined EVR formatted as libsolv expects.
    """
    # This function is sometimes used with dependencies, not just packages we know full details
    # about. So if there's no specific EVR information, we need to set EVR to None.
    if version is None:
        return None

    return '{}{}{}'.format(
        '{}:'.format(epoch) if epoch else '',
        version,
        '-{}'.format(release) if release else ''
    ).encode('utf-8')


def rpm_unit_to_solvable(solv_repo, unit):
    """Convert a Pulp RPM dict to a libsolv solvable.

    :param solv_repo: the repository the unit is being added into
    :type solv_repo: solv.Repo

    :param unit: the unit being converted
    :type unit: pulp_rpm.plugins.models.Model

    :return: the solvable created.
    :rtype: solv.Solvable
    """
    solvable = solv_repo.add_solvable()

    def rpm_filelist_conversion(solvable, unit):
        """A specific, rpm-unit-type filelist attribute conversion."""
        repodata = solv_repo.first_repodata()
        unit_files = unit.get('files', {}).get('file', [])
        unit_files.extend(unit.get('files', {}).get('dir', []))

        for filename in unit_files:
            dirname = os.path.dirname(filename).encode('utf-8')
            dirname_id = repodata.str2dir(dirname)
            repodata.add_dirstr(
                solvable.id, solv.SOLVABLE_FILELIST,
                dirname_id, os.path.basename(filename).encode('utf-8')
            )

    def rpm_basic_deps(solvable, name, evr, arch):
        # Prv: $n . $a = $evr
        pool = solvable.repo.pool
        name_id = pool.str2id(name)
        evr_id = pool.str2id(evr)
        arch_id = pool.str2id(arch)
        rel = pool.rel2id(name_id, arch_id, solv.REL_ARCH)
        rel = pool.rel2id(rel, evr_id, solv.REL_EQ)
        solvable.add_deparray(solv.SOLVABLE_PROVIDES, rel)

    name = unit.get('name', None).encode('utf-8')
    solvable.name = name

    evr = libsolv_formatted_evr(unit['epoch'], unit['version'], unit['arch'])
    solvable.evr = evr

    arch = unit.get('arch', 'noarch').encode('utf-8')
    solvable.arch = arch

    vendor = unit.get('vendor')
    if vendor:
        vendor = vendor.encode('utf-8')
        solvable.vendor = vendor

    rpm_dependency_attribute_factory('requires', solvable, unit)
    rpm_dependency_attribute_factory('provides', solvable, unit)
    rpm_dependency_attribute_factory('recommends', solvable, unit)

    rpm_filelist_conversion(solvable, unit)
    rpm_basic_deps(solvable, name, evr, arch)

    return solvable


def rpm_dependency_attribute_factory(attribute_name, solvable, unit, dependency_key=None):
    """Create a function that processes Pulp a dependency attribute on a unit.

    e.g. "recommends", "requires", "provides"
    """
    for depunit in unit.get(attribute_name, []):
        rpm_dependency_conversion(
            solvable, depunit, attribute_name, dependency_key=dependency_key
        )


def rpm_dependency_conversion(solvable, unit, attr_name, dependency_key=None):
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
    :type solv.Solvable: a libsolv solvable

    :param unit: the content unit to get the dependencies from
    :type unit: an object or a dictionary

    :returns: None
    """

    unit_name = unit.get('name', None)
    if unit_name is not None:
        unit_name = unit_name.encode('utf-8')

    unit_flags = unit.get('flags', None)
    unit_evr = libsolv_formatted_evr(unit['epoch'], unit['version'], unit.get('arch'))

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


def module_unit_to_solvable(solv_repo, unit):
    """Convert a Pulp Module in dict representation to a libsolv solvable.

    :param solv_repo: the repository the unit is being added into
    :type solv_repo: solv.Repo

    :param unit: the unit being converted
    :type unit: pulp_rpm.plugins.models.Model

    :return: the solvable created.
    :rtype: solv.Solvable
    """
    solvable = solv_repo.add_solvable()
    pool = solvable.repo.pool

    def module_solvable_name(unit):
        """
        Create a solvable name from module attributes: module:<name>:<stream>:<version>:<context>
        """
        return 'module:{name}:{stream}:{version!s}:{context}'.format(
            name=unit.get('name').encode('utf-8'),
            stream=unit.get('stream').encode('utf-8'),
            version=unit.get('version'),
            context=unit.get('context').encode('utf-8'),
        )

    def module_basic_deps(pool, solvable, solvable_name, name, stream, version, arch):
        """
        Create the basic module `Provides:` and `Obsoletes:` relations
        """
        # Prv: module:$n:$s:$v:$c . $a
        solvable.nsvca_rel = pool.rel2id(
            pool.str2id(solvable_name),
            pool.str2id(arch), solv.REL_ARCH
        )
        solvable.add_deparray(solv.SOLVABLE_PROVIDES, solvable.nsvca_rel)

        # Prv: module()
        dep = pool.Dep('module()')
        solvable.add_deparray(solv.SOLVABLE_PROVIDES, dep)

        # Prv: module($n)
        dep_n = pool.Dep('module({})'.format(name))
        solvable.add_deparray(solv.SOLVABLE_PROVIDES, dep_n)

        # Obs: module($n)
        # This is a bit of a hack; a weaker than `Conflicts` because same-name module streams should
        # repulse each other.
        solvable.add_deparray(solv.SOLVABLE_OBSOLETES, dep_n)

        # Prv: module($n:$s)
        dep_ns = pool.Dep('module({}:{})'.format(name, stream))
        solvable.add_deparray(solv.SOLVABLE_PROVIDES, dep_ns)

        # Prv: module($n:$s) = $v
        dep_ns_v = dep_n.Rel(solv.REL_EQ, pool.Dep(str(version)))
        solvable.add_deparray(solv.SOLVABLE_PROVIDES, dep_ns_v)

    def module_artifacts_conversion(pool, module_solvable, name, evr, arch):
        # propagate Req: module:$n:$s:$v:$c . $a to the modular RPM i.e
        # make the rpm require this module
        name_id = pool.str2id(name)
        evr_id = pool.str2id(evr)
        arch_id = pool.str2id(arch)

        # $n.$a = $evr
        rel = pool.rel2id(name_id, arch_id, solv.REL_ARCH)
        rel = pool.rel2id(rel, evr_id, solv.REL_EQ)
        selection = pool.matchdepid(
            rel, solv.SOLVABLE_NAME | solv.SOLVABLE_ARCH | solv.SOLVABLE_EVR,
            solv.SOLVABLE_PROVIDES
        )

        for rpm_solvable in selection.solvables():
            # Make the artifact require this module
            rpm_solvable.add_deparray(solv.SOLVABLE_REQUIRES, module_solvable.nsvca_rel)
            # Prv: modular-package()
            rpm_solvable.add_deparray(solv.SOLVABLE_PROVIDES, pool.Dep('modular-package()'))
            # Make the module recommend this artifact too
            module_solvable.add_deparray(solv.SOLVABLE_RECOMMENDS, rel)
            _LOGGER.debug('link {mod} <-rec-> {solv}', mod=module_solvable, solv=rpm_solvable)

    def module_requires_conversion(pool, dependency_list):
        # A direct copy of the algorithm here:
        # https://github.com/fedora-modularity/fus/blob/
        # 72a98d5feb42787813dd89a5915d5840ae514261/fus.c#L35-L66`
        # assuming profiles are subsets of module artifacts, no profiles processing is needed here

        def dep_or_rel(dep, rel, op):
            """
            There are relations between modules in `deps`. For example:
              deps = [{'gtk': ['1'], 'foo': ['1']}]" means "gtk:1 and foo:1" are both required.
              deps = [{'gtk': ['1', '2']}"] means "gtk:1 or gtk:2" are required.

            This method helps creating such relations using following syntax:
              rel_or_dep(solv.Dep, solve.REL_OR, stream_dep(name, stream))
              rel_or_dep(solv.Dep, solve.REL_AND, stream_dep(name, stream))
              rel_or_dep(solv.Dep, solve.REL_WITH, stream_dep(name, stream))
              rel_or_dep(solv.Dep, solve.REL_WITHOUT, stream_dep(name, stream))
            """
            # to "accumulate" stream relations (in a list of module dependencies)
            # in case dep isn't populated yet, gives relative dep
            # A direct copy of the algorithm here:
            # https://pagure.io/fm-orchestrator/blob/master/f/module_build_service/mmd_resolver.py
            # Which was in turn ported from FUS
            dep.Rel(op, rel) if dep is not None else rel

        require = None
        for name, streams in dependency_list.items():
            if name == 'platform':
                # no need to fake the platform (streams) later on
                continue
            name = name.encode('utf8')
            rel = None
            positive = False
            negative = False

            for stream in streams:
                stream = stream.encode('utf8')
                if stream.startswith('-'):
                    negative = True
                else:
                    positive = True
                rel = dep_or_rel(rel, pool.str2id('module({}:{})'.format(name, stream)), solv.REL_OR)
            nprovide = pool.str2id('module({})'.format(name))
            if positive:
                rel = dep_or_rel(nprovide, rel, solv.REL_WITH)
            if negative:
                rel = dep_or_rel(nprovide, rel, solv.REL_WITHOUT)

            require = dep_or_rel(require, rel, solv.REL_AND)

        if require:
            solvable.add_deparray(solv.SOLVABLE_REQUIRES, require)

    solvable_name = module_solvable_name(unit)
    solvable.name = solvable_name
    solvable.evr = ''

    arch = unit.get('arch', 'noarch').encode('utf-8')
    solvable.arch = arch

    name = unit.get('name', None)
    if name:
        name = name.encode('utf-8')

    stream = unit.get('stream', None)
    if stream:
        stream = stream.encode('utf-8')

    version = unit.get('version', None)

    if not arch:
        arch = 'noarch'.encode('utf-8')

    module_basic_deps(pool, solvable, solvable_name, name, stream, version, arch)

    for artifact in unit.get('artifacts', []):
        nevra_tuple = parse.rpm.nevra(artifact)
        artifact_name = nevra_tuple[0]
        artifact_epoch = nevra_tuple[1]
        artifact_version = nevra_tuple[2]
        artifact_release = nevra_tuple[3]
        artifact_arch = nevra_tuple[4] if nevra_tuple[4] else 'noarch'

        if artifact_name is not None:
            artifact_name = artifact_name.encode('utf-8')

        if artifact_arch is not None:
            artifact_arch = artifact_arch.encode('utf-8')

        artifact_evr = libsolv_formatted_evr(artifact_epoch, artifact_version, artifact_release)

        module_artifacts_conversion(pool, solvable, artifact_name, artifact_evr, artifact_arch)

    pool.createwhatprovides()

    for dependency in unit.get('dependencies', []):
        module_requires_conversion(pool, dependency)

    return solvable


def module_defaults_unit_to_solvable(solv_repo, unit):
    """Convert a Pulp Module Default dict to a libsolv solvable.

    :param solv_repo: the repository the unit is being added into
    :type solv_repo: solv.Repo

    :param unit: the unit being converted
    :type unit: pulp_rpm.plugins.models.Model

    :return: the solvable created.
    :rtype: solv.Solvable
    """
    solvable = solv_repo.add_solvable()
    solvable.evr = ''
    solvable.arch = ''

    name = unit.get('name', None)
    if name is not None:
        name = name.encode('utf-8')

    stream = unit.get('stream', None)
    if stream is not None:
        stream = stream.encode('utf-8')

    if stream:
        solvable.name = 'module-default({}:{})'.format(name, stream)
    else:
        solvable.name = 'module-default({})'.format(name)

    pool = solvable.repo.pool

    def module_defaults_basic_deps(solvable, name, stream):
        """
        Links a module and its default with dependencies.
        """
        if stream:
            module_depid = pool.Dep('module({}:{})'.format(name, stream), 0)
            module_default_depid = pool.Dep('module-default({}:{})'.format(name, stream))
        else:
            module_depid = pool.Dep('module({})'.format(name), 0)
            module_default_depid = pool.Dep('module-default({})'.format(name))
        if not module_depid:
            return
        # tell solv this solvable provides a specific name:stream default so it can be pulled-in
        # thru dependencies
        solvable.add_deparray(solv.SOLVABLE_PROVIDES, module_default_depid)
        solvable.add_deparray(solv.SOLVABLE_PROVIDES, pool.str2id('module-default()'))
        for module in pool.whatprovides(module_depid):
            # mark the related module so it can be queried as '(module() with module-default())'
            # i.e such that it's easy visible thru a pool.whatprovides that it has a default
            module.add_deparray(solv.SOLVABLE_PROVIDES, pool.Dep('module-default()'))
            # mark the module such that it recommends its default i.e this solvable
            module.add_deparray(solv.SOLVABLE_RECOMMENDS, module_default_depid)
            # mark the module defaults require the module
            rel = pool.rel2id(pool.str2id(module.name), pool.str2id(module.arch), solv.REL_ARCH)
            solvable.add_deparray(solv.SOLVABLE_REQUIRES, rel)

    module_defaults_basic_deps(solvable, name, stream)

    return solvable


class UnitSolvableMapping(object):
    """Map libsolv solvables to Pulp units and repositories.

    Translate between what libsolv understands, solvable IDs in a pool, and what Pulp understands,
    units and repositories.
    """

    def __init__(self):
        # Stores data in the form (pulp_unit_id, pulp_repo_id): solvable
        self._mapping_unit_to_solvable = {}
        # Stores data in the form solvable_id: (pulp_unit_id, pulp_repo_id)
        self._mapping_solvable_to_unit = {}
        # Stores data in the form pulp_repo_id: libsolv_repo_id
        self._mapping_repos = {}

    def register(self, unit, solvable, repo_id):
        """Store the matching of a unit-repo pair to a solvable inside of the mapping.
        """
        if not self.get_repo(str(repo_id)):
            raise ValueError(
                "Attempting to register unit {} to unregistered repo {}".format(unit, repo_id)
            )

        self._mapping_solvable_to_unit.setdefault(solvable.id, (unit['id'], repo_id))
        self._mapping_unit_to_solvable.setdefault((unit['id'], repo_id), solvable)

        _LOGGER.debug('Loaded unit {unit}, {repo} as {solvable}'.format(
            unit=unit['id'], solvable=solvable, repo=repo_id
        ))

    def register_repo(self, repo_id, libsolv_repo):
        """Store the repo (Pulp) - repo (libsolv) pair.
        """
        return self._mapping_repos.setdefault(str(repo_id), libsolv_repo)

    def get_repo(self, repo_id):
        """Return the repo from the mapping.
        """
        return self._mapping_repos.get(repo_id)

    def get_unit_id(self, solvable):
        """Get the (unit, repo_id) pair for a given solvable.

        :returns: A tuple of (unit, repo_id)
        :rtype: tuple
        """
        return self._mapping_solvable_to_unit.get(solvable.id)

    def get_solvable(self, unit, repo_id):
        """Fetch the libsolv solvable associated with a unit-repo pair.
        """
        return self._mapping_unit_to_solvable.get((unit['id'], repo_id))

    def get_repo_units(self, repo_id):
        """Get back unit ids of all units that were in a repo based on the mapping.
        """
        return set(
            unit_id for (unit_id, unit_repo_id) in self._mapping_unit_to_solvable.keys()
            if unit_repo_id == repo_id
        )

    def get_units_from_solvables(self, solvables):
        """Map a whole list of solvables back into their Pulp units.
        """
        ret = set()
        for solvables in misc_utils.paginate(solvables):
            unit_ids = [self.get_unit_id(solvable)[0] for solvable in solvables]
            iterator = itertools.chain(
                models.RPM.objects.filter(id__in=unit_ids).only(
                    *models.RPM.unit_key_fields),
                models.Modulemd.objects.filter(id__in=unit_ids).only(
                    *models.Modulemd.unit_key_fields),
                models.ModulemdDefaults.objects.filter(id__in=unit_ids).only(
                    *models.ModulemdDefaults.unit_key_fields))
            for unit in iterator:
                ret.add(unit)
        return ret


class Solver(object):

    def __init__(self, source_repo, target_repo=None, conservative=False):
        super(Solver, self).__init__()
        self.source_repo = source_repo
        self.target_repo = target_repo
        self.conservative = conservative
        self._finalized = False
        self._loaded = False
        self._pool = solv.Pool()
        # prevent https://github.com/openSUSE/libsolv/issues/267
        self._pool.setarch()
        self.mapping = UnitSolvableMapping()

    def load(self):
        """Prepare the solver.

        Load units from the database into the mapping used by the solver, and do other init work.
        """
        if self._loaded:
            return

        self.load_source_repo(self.source_repo.repo_id)
        if self.target_repo:
            self.load_target_repo(self.target_repo.repo_id)

        self._loaded = True
        self.finalize()

    def finalize(self):
        """Finalize the solver - a finalized solver is ready for depsolving.

        Libsolv needs to perform some scans/hashing operations before it can do certain things.
        For more details see:
        https://github.com/openSUSE/libsolv/blob/master/doc/libsolv-bindings.txt
        """
        self._pool.addfileprovides()
        self._pool.createwhatprovides()
        self._finalized = True

    def load_source_repo(self, repo_id):
        """Load the provided Pulp repo as a source repo.

        All units in the repo will be available to be "installed", or copied.
        """
        source_units = fetch_units_from_repo(repo_id)
        self.add_repo_units(source_units, repo_id)
        _LOGGER.info('Loaded source repository %s', repo_id)

    def load_target_repo(self, repo_id):
        """Load the provided Pulp repo as a target repo.

        All units in the repo are marked as "installed" inside libsolv, so that it knows they
        don't need to be "installed" (copied)
        """
        target_units = fetch_units_from_repo(self.target_repo.repo_id)
        self.add_repo_units(target_units, repo_id, installed=True)
        _LOGGER.info('Loaded target repository %s', repo_id)

    def add_repo_units(self, units, repo_id, installed=False):
        """Generate solvables from Pulp units and add them to the mapping.
        """
        repo_name = str(repo_id)
        repo = self.mapping.get_repo(repo_name)
        if not repo:
            repo = self.mapping.register_repo(repo_name, self._pool.add_repo(repo_name))
            repodata = repo.add_repodata()
        else:
            repodata = repo.first_repodata()

        for unit in units:
            try:
                type_factory_mapping = {
                    ids.TYPE_ID_RPM: rpm_unit_to_solvable,
                    ids.TYPE_ID_MODULEMD: module_unit_to_solvable,
                    ids.TYPE_ID_MODULEMD_DEFAULTS: module_defaults_unit_to_solvable,
                }
                factory = type_factory_mapping[unit['_content_type_id']]
            except KeyError as err:
                raise ValueError('Unsupported unit type: {}', err)
            solvable = factory(repo, unit)
            self.mapping.register(unit, solvable, repo_id)

        if installed:
            self._pool.installed = repo

        # Need to call pool->addfileprovides(), pool->createwhatprovides() after loading new repo
        self._finalized = False

        repodata.internalize()

    def _create_unit_install_jobs(self, units):
        """Create libsolv jobs for each one of the units passed in.

        A libsolv "Job" is a request for the libsolv sat solver to process. For instance a job with
        the flags SOLVER_INSTALL | SOLVER_SOLVABLE will tell libsolv to solve an installation of
        a package which is specified by solvable ID, as opposed to by name, or by pattern, which
        are other options available.

        See: https://github.com/openSUSE/libsolv/blob/master/doc/libsolv-bindings.txt#the-job-class

        :param units: An iterable of Pulp content units types supported by the type factory mapping.
        :type units: An iterable of dictionaries

        Yields:
            A libsolv "Job" to "install" one of the units

        Raises:
            ValueError: If one of the units passed in does not have a matching solvable
        """
        flags = solv.Job.SOLVER_INSTALL | solv.Job.SOLVER_SOLVABLE
        for unit in units:
            solvable = self.mapping.get_solvable(unit, self.source_repo.repo_id)
            if not solvable:
                raise ValueError('Encountered an unknown unit {}'.format(unit))
            yield self._pool.Job(flags, solvable.id)

    def _handle_nothing_provides(self, info, jobs):
        """Handle a case where nothing provides a given requirement.

        Some units may depend on other units outside the repo, and that will cause issues with the
        solver. We need to create some dummy packages to fulfill those provides so that the
        solver can continue. Essentially we pretend the missing dependencies are already installed.

        :param info: A class describing why the rule was broken
        :type info: solv.RuleInfo

        TODO: why is "jobs" here? it is used in similar functions but not in this one. oversight?
        """
        if not self.target_repo:
            return
        target_repo = self.mapping.get_repo(self.target_repo.repo_id)
        dummy = target_repo.add_solvable()
        dummy.add_deparray(solv.SOLVABLE_PROVIDES, info.dep)
        _LOGGER.debug('Created dummy provides: {name}', name=info.dep.str())

    def _locate_solvable_job(self, solvable, flags, jobs):
        for idx, job in enumerate(jobs):
            if job.what == solvable.id and job.how == flags:
                _LOGGER.debug('Found job: %s', str(job))
                return idx

    def _enforce_solvable_job(self, solvable, flags, jobs):
        idx = self._locate_solvable_job(solvable, flags, jobs)
        if idx is not None:
            return

        enforce_job = self._pool.Job(flags, solvable.id)
        jobs.append(enforce_job)
        _LOGGER.debug('Added job %s', enforce_job)

    def _handle_same_name(self, info, jobs):
        """Handle a case where multiple versions of a package are "installed".

        Libsolv by default will make the assumption that you can't "install" multiple versions of
        a package, so in cases where we create that situation, we need to pass a special flag.
        """
        install_flags = solv.Job.SOLVER_INSTALL | solv.Job.SOLVER_SOLVABLE
        enforce_flags = install_flags | solv.Job.SOLVER_MULTIVERSION
        self._enforce_solvable_job(info.solvable, enforce_flags, jobs)
        self._enforce_solvable_job(info.othersolvable, enforce_flags, jobs)

    def _handle_problems(self, problems, jobs):
        """Handle problems libsolv finds during the depsolving process that can be worked around.
        """
        for problem in problems:
            for problem_rule in problem.findallproblemrules():
                for info in problem_rule.allinfos():
                    if info.type == solv.Solver.SOLVER_RULE_PKG_REQUIRES:
                        continue
                    elif info.type == solv.Solver.SOLVER_RULE_PKG_NOTHING_PROVIDES_DEP:
                        self._handle_nothing_provides(info, jobs)
                    elif info.type == solv.Solver.SOLVER_RULE_PKG_SAME_NAME:
                        self._handle_same_name(info, jobs)
                    else:
                        _LOGGER.warning(
                            'No workaround available for problem type %s. '
                            'You may refer to the libsolv Solver class documetnation '
                            'for more details. See https://github.com/openSUSE/'
                            'libsolv/blob/master/doc/libsolv-bindings.txt'
                            '#the-solver-class.', info.type
                        )
        self._pool.createwhatprovides()

    def find_dependent_rpms_conservative(self, units):
        """Find the RPM dependencies that need to be copied to satisfy copying the provided units,
        taking into consideration what units are already present in the target repository.
        """
        if not units:
            return set()
        previous_problems_ = set()
        attempt = 0
        jobs = list(self._create_unit_install_jobs(units))
        while True:
            attempt += 1
            _LOGGER.debug(
                'Solver attempt {a}; jobs:\n{j}'.format(
                    a=attempt,
                    j='\n\t'.join(str(job) for job in jobs)
                )
            )
            solver = self._pool.Solver()
            problems = solver.solve(jobs)
            problems_ = set(str(problem) for problem in problems)
            # assuming we won't be creating more and more problems all the time
            _LOGGER.debug('Previous solver problems:\n{}'.format('\n'.join(previous_problems_)))
            _LOGGER.debug('Current solver problems:\n{}'.format('\n'.join(problems_)))
            if not problems or previous_problems_ == problems_:
                break
            self._handle_problems(problems, jobs)
            previous_problems_ = problems_
        # The solver is simply ignoring the problems encountered and proceeds associating
        # any new solvables/units. This might be reported back to the user one day over
        # the REST API.
        if problems_:
            _LOGGER.warning('Encountered problems solving: {}'.format(', '.join(problems_)))
        transaction = solver.transaction()
        return self.mapping.get_units_from_solvables(transaction.newsolvables())

    def find_dependent_rpms_relaxed(self, units):
        """Find the RPM dependencies that need to be copied to satisfy copying the provided units,
        without taking into consideration the target repository. Just copy the most recent versions
        of each.
        """
        pool = self._pool
        seen = set()
        # Please note that providers of the requirements can be found in both the target
        # and source repo but each provider is a distinct solvable, so even though a particular
        # unit can seem to appear twice in the pool.whatprovides() set, it's just a different
        # solvable.
        candq = set(self.mapping.get_solvable(unit, self.source_repo.repo_id) for unit in units)
        while candq:
            cand = candq.pop()
            seen.add(cand)
            for key in (solv.SOLVABLE_REQUIRES, solv.SOLVABLE_RECOMMENDS):
                # iterate the dependencies
                for req in cand.lookup_deparray(key):
                    # "providers" is the list of packages that could possibly satisfy (provide) this
                    # dependency. Usually, it is a list of all the versions of one package that will
                    # satisfy it. Sometimes (rich deps), it can be a list of many different package
                    # names that might satisfy it.
                    providers = pool.whatprovides(req)

                    if not providers:
                        continue

                    # Group them by name to make them easier to deal with. Each group is different
                    # versions of one package.
                    providers_grouped = collections.defaultdict(list)
                    for provider in providers:
                        providers_grouped[provider.name].append(provider)

                    # Sort each list of versions in-place, so that the first item in each list is
                    # the newest version of that package.
                    for group in providers_grouped.itervalues():
                        group.sort(cmp=lambda x, y: x.evrcmp(y), reverse=True)

                        # grab the newest version of the package
                        provider = group[0]

                        repo = self.mapping.get_unit_id(provider)[1]

                        if provider in seen or repo != self.source_repo.repo_id:
                            continue
                        candq.add(provider)
        targets = self.mapping.get_repo_units(self.target_repo.repo_id)
        results = self.mapping.get_units_from_solvables(
            s for s in seen
            if self.mapping.get_unit_id(s)[0] not in targets
        )
        return results

    def find_dependent_rpms(self, units):
        assert self._finalized, "Depsolver must be finalized before it can be used"

        if self.conservative:
            return self.find_dependent_rpms_conservative(units)
        return self.find_dependent_rpms_relaxed(units)
