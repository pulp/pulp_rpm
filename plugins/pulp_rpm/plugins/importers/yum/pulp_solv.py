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

# The name for the repo inside libsolv which represents the combined set of target/destination
# repositories. Libsolv only supports one "installed" repo at a time, therefore we need to
# combine them and determine what units actually go where afterwards.
COMBINED_TARGET_REPO_NAME = "combined_target_repo"

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
    'recommends',
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

RPM_EXCLUDE_FIELDS = set([
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
    'pk'
]) - RPM_FIELDS

MODULE_EXCLUDE_FIELDS = set([
    'name',
    'stream',
    'version',
    'context',
    'arch',
    'summary',
    'description',
    'checksum',
    'profiles',
    'artifacts',
    'checksum',
    'dependencies',
    '_content_type_id',
    '_ns',
    '_storage_path',
    '_last_updated',
    'downloaded',
    'pulp_user_metadata',
    'pk'
]) - MODULE_FIELDS

MODULE_DEFAULTS_EXCLUDE_FIELDS = set([
    'pulp_user_metadata',
    '_last_updated',
    '_storage_path',
    'downloaded',
    'name',
    'repo_id',
    'profiles',
    'checksum',
    '_ns',
    '_content_type_id',
    'pk',
]) - MODULE_DEFAULTS_FIELDS


def fetch_units_from_repo(repo_id):
    """Load the units from a repository.

    Extract all the content in the provided repository from the database and dump them to dicts.
    For performance, we bypass the ORM and do raw mongo queries, because the extra overhead of
    creating objects vs dicts wastes too much time and space.
    """
    assert repo_id, "Must provide a valid repo_id, not None"

    def _repo_units(repo_id, type_id, model, excludes):
        # NOTE: optimization; the solver has to visit every unit of a repo.
        # Using a custom, as-pymongo query to load the units as fast as possible.
        rcuq = server_model.RepositoryContentUnit.objects.filter(
            repo_id=repo_id, unit_type_id=type_id).only('unit_id').as_pymongo()

        for rcu_batch in misc_utils.paginate(rcuq):
            rcu_ids = [rcu['unit_id'] for rcu in rcu_batch]
            # Why use .excludes() instead of .only()? Because: https://pulp.plan.io/issues/5131
            for unit in model.objects.filter(id__in=rcu_ids).exclude(*excludes).as_pymongo():
                if not unit.get('id'):
                    unit['id'] = unit.get('_id')
                yield unit

    # order matters; e.g module loading requires rpm loading
    units = itertools.chain(
        _repo_units(repo_id, ids.TYPE_ID_RPM, models.RPM, RPM_EXCLUDE_FIELDS),
        _repo_units(
            repo_id, ids.TYPE_ID_MODULEMD, models.Modulemd, MODULE_EXCLUDE_FIELDS),
        _repo_units(
            repo_id, ids.TYPE_ID_MODULEMD_DEFAULTS, models.ModulemdDefaults,
            MODULE_DEFAULTS_EXCLUDE_FIELDS),
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

    name = unit.get('name').encode('utf-8')
    solvable.name = name

    evr = libsolv_formatted_evr(unit.get('epoch'), unit.get('version'), unit.get('arch'))
    solvable.evr = evr

    arch = unit.get('arch', 'noarch').encode('utf-8')
    solvable.arch = arch

    vendor = unit.get('vendor')
    if vendor:
        vendor = vendor.encode('utf-8')
        solvable.vendor = vendor

    for attribute_name in ('requires', 'provides', 'recommends'):
        for depunit in unit.get(attribute_name, []):
            rpm_dependency_conversion(solvable, depunit, attribute_name)

    rpm_filelist_conversion(solvable, unit)
    rpm_basic_deps(solvable, name, evr, arch)

    return solvable


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

    unit_name = unit.get('name')
    if unit_name is not None:
        unit_name = unit_name.encode('utf-8')

    unit_flags = unit.get('flags')
    unit_evr = libsolv_formatted_evr(unit.get('epoch'), unit.get('version'), unit.get('arch'))

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
        Create the basic module `Provides:` relations
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
            # Provide: modular-package()
            rpm_solvable.add_deparray(solv.SOLVABLE_PROVIDES, pool.Dep('modular-package()'))

    solvable_name = module_solvable_name(unit)
    solvable.name = solvable_name
    solvable.evr = ''

    arch = unit.get('arch', 'noarch').encode('utf-8')
    solvable.arch = arch

    name = unit.get('name')
    if name:
        name = name.encode('utf-8')

    stream = unit.get('stream')
    if stream:
        stream = stream.encode('utf-8')

    version = unit.get('version')

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

    module_dependencies_conversion(pool, solvable, unit.get('dependencies', []))
    pool.createwhatprovides()  # TODO: It would be great to do this less often

    return solvable


def module_dependencies_conversion(pool, module_solvable, dependency_list):
    """
    Process the module dependency list.

    So for example for following input:
        dependency_list = [{'gtk': ['1'], 'foo': ['1']}]

    The resulting solv.Dep expression will be:
        ((module(gtk) with module(gtk:1)) and (module(foo) with module(foo:1)))

    This Dep expression is then applied to the REQUIRES: deparray of the module solvable.

    :param pool: The libsolv pool that owns the module
    :type pool: solv.Pool
    :param module_solvable: A solvable representing the module
    :type module_solvable: solv.Solvable
    :param dependency_list: List of dictionaries representing modulemd dependency data.
    :type dependency_list: list
    """
    # A near exact copy of the algorithm here:
    # https://pagure.io/fm-orchestrator/blob/db03f0a7f530cc2bf2f8971f085a9e6b71595d70/f/
    # module_build_service/mmd_resolver.py#_53

    def stream_dep(name, stream):
        """
        Every name:stream combination from dict in `deps` list is expressed as `solv.Dep`
        instance and is represented internally in solv with "module(name:stream)".
        This is parallel to RPM-world "Provides: perl(foo)" or "Requires: perl(foo)",
        but in this method, we are only constructing the condition after the "Provides:"
        or "Requires:". This method creates such solve.Dep().
        """
        return pool.Dep("module({}:{})".format(name, stream))

    def dep_or_rel(dep, op, rel):
        """
        There are relations between modules in `deps`. For example:
          deps = [{'gtk': ['1'], 'foo': ['1']}]" means "gtk:1 and foo:1" are both required.
          deps = [{'gtk': ['1', '2']}"] means "gtk:1 or gtk:2" are required.

        This method helps creating such relations using following syntax:
          dep_or_rel(solv.Dep, solve.REL_OR, stream_dep(name, stream))
          dep_or_rel(solv.Dep, solve.REL_AND, stream_dep(name, stream))
          dep_or_rel(solv.Dep, solve.REL_WITH, stream_dep(name, stream))
          dep_or_rel(solv.Dep, solve.REL_WITHOUT, stream_dep(name, stream))
        """
        dep.Rel(op, rel) if dep is not None else rel

    # Check each dependency dict in dependency_list and generate the solv requirements.
    reqs = None
    for dep_dict in dependency_list:
        require = None
        for name, streams in dep_dict.items():
            if name == 'platform':
                # no need to fake the platform (streams) later on
                continue
            name = name.encode('utf8')

            # The req_pos will store solv.Dep expression for "positive" requirements.
            # That is the case of 'gtk': ['1', '2'].
            # The req_neg will store negative requirements like 'gtk': ['-1', '-2'].
            req_pos = req_neg = None

            # For each stream in `streams` for this dependency, generate the
            # module(name:stream) solv.Dep and add REL_OR relations between them.
            for stream in streams:
                stream = stream.encode('utf8')

                if stream.startswith("-"):
                    req_neg = dep_or_rel(req_neg, solv.REL_OR, stream_dep(name, stream[1:]))
                else:
                    req_pos = dep_or_rel(req_pos, solv.REL_OR, stream_dep(name, stream))

            # Generate the module(name) solv.Dep.
            req = pool.Dep("module({})".format(name))

            # Use the REL_WITH for positive requirements and REL_WITHOUT for negative
            # requirements.
            if req_pos is not None:
                req = req.Rel(solv.REL_WITH, req_pos)
            elif req_neg is not None:
                req = req.Rel(solv.REL_WITHOUT, req_neg)

            # And in the end use AND between the last name:[streams] and the current one.
            require = dep_or_rel(require, solv.REL_AND, req)

        # NOTE: In the original algorithm, this was an OR operation. We don't want only one
        # set of deps (for one platform), we want the deps for all platforms. Hence, solv.REL_AND.
        reqs = dep_or_rel(reqs, solv.REL_AND, require)

    module_solvable.add_deparray(solv.SOLVABLE_REQUIRES, reqs)


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
    # a module default has no arch, use 'noarch'
    solvable.arch = 'noarch'

    name = unit.get('name')
    if name is not None:
        name = name.encode('utf-8')

    stream = unit.get('stream')
    if stream is not None:
        stream = stream.encode('utf-8')

    solvable.name = 'module-default:{}'.format(name)

    pool = solvable.repo.pool

    def module_defaults_basic_deps(solvable, name, stream):
        """
        Links a module and its default with dependencies.
        """
        # we are making all modules require the module-default regardless of they are default
        # since the module-default can cary profile information
        module_depid = pool.Dep('module({})'.format(name), 0)

        module_default_depid = pool.Dep(solvable.name)
        if not module_depid:
            return

        # tell libsolv that this solvable provides the module-default for the module name
        solvable.add_deparray(solv.SOLVABLE_PROVIDES, module_default_depid)

        pool.createwhatprovides()
        for module in pool.whatprovides(module_depid):
            # module default metadata doesn't have to specify a stream, we only want to make
            # module:name:stream:{ver}:{ctx} provide the default when it does. However, in either
            # case we want the modules to require the module-default because it can carry
            # important profile information.
            if stream:
                # mark the related module so it can be queried as '(module() with module-default())'
                # i.e such that it's easy visible thru a pool.whatprovides that it has a default
                module.add_deparray(solv.SOLVABLE_PROVIDES, pool.Dep('module-default()'))

            # mark the module such that it requires its default i.e this solvable
            module.add_deparray(solv.SOLVABLE_REQUIRES, module_default_depid)

        # Note: Since we're copying the module default metadata as-is without modification or
        # regeneration, that means that "profiles" may be copied for streams that do not exist.
        # We think this is probably OK but if it is not, the solution is to "require" all streams
        # for which a profile exists.

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
        """Map a whole list of solvables back into their Pulp units, keyed by the repo they
        come from.
        """
        repo_unit_map = collections.defaultdict(set)
        for solvable in solvables:
            (unit_id, repo_id) = self.get_unit_id(solvable)
            repo_unit_map[repo_id].add(unit_id)

        ret = collections.defaultdict(set)
        for repo, unit_ids in repo_unit_map.items():
            for paginated_unit_ids in misc_utils.paginate(unit_ids):
                modulemd_fields = ['_storage_path']
                modulemd_fields.extend(models.ModulemdDefaults.unit_key_fields)
                iterator = itertools.chain(
                    models.RPM.objects.filter(id__in=paginated_unit_ids).only(
                        *models.RPM.unit_key_fields),
                    models.Modulemd.objects.filter(id__in=paginated_unit_ids).only(
                        *models.Modulemd.unit_key_fields),
                    models.ModulemdDefaults.objects.filter(id__in=paginated_unit_ids).only(
                        *modulemd_fields))
                for unit in iterator:
                    ret[repo].add(unit)
        return ret


class Solver(object):

    type_factory_mapping = {
        ids.TYPE_ID_RPM: rpm_unit_to_solvable,
        ids.TYPE_ID_MODULEMD: module_unit_to_solvable,
        ids.TYPE_ID_MODULEMD_DEFAULTS: module_defaults_unit_to_solvable,
    }

    def __init__(self, source_repo, target_repo=None, additional_repos=None,
                 conservative=False, ignore_missing=True):
        super(Solver, self).__init__()

        self.primary_source_repo = source_repo
        self.primary_target_repo = target_repo
        self._additional_repo_mapping = additional_repos if additional_repos else {}
        self.conservative = conservative
        self._finalized = False
        self._loaded = False
        self._pool = solv.Pool()
        # prevent https://github.com/openSUSE/libsolv/issues/267
        self._pool.setarch()
        self.mapping = UnitSolvableMapping()
        self.ignore_missing = ignore_missing

    def load(self):
        """Prepare the solver.

        Load units from the database into the mapping used by the solver, and do other init work.
        """
        if self._loaded:
            return

        source_repos = \
            set([self.primary_source_repo.repo_id]) | set(self._additional_repo_mapping.keys())
        target_repos = \
            set([self.primary_target_repo.repo_id]) | set(self._additional_repo_mapping.values())

        for source_repo_id in source_repos:
            self.load_source_repo(source_repo_id)

        for target_repo_id in target_repos:
            self.load_target_repo(target_repo_id)

        self._pool.installed = self.mapping.get_repo(COMBINED_TARGET_REPO_NAME)

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
        units = fetch_units_from_repo(repo_id)
        self.add_repo_units(units, repo_id)
        _LOGGER.debug('Loaded repository %s', repo_id)

    def load_target_repo(self, repo_id):
        """Load the provided Pulp repo into the combined target repo.

        All units in the repo will be added to the combined target repo, the contents of which
        are considered "installed" by the solver.
        """
        units = fetch_units_from_repo(repo_id)
        self.add_repo_units(units, repo_id, override_repo_name=COMBINED_TARGET_REPO_NAME)
        _LOGGER.debug('Loaded repository %s into combined target repo' % str(repo_id))

    def add_repo_units(self, units, repo_id, override_repo_name=None):
        """Generate solvables from Pulp units and add them to the mapping.

        In some circumstances, we want to load multiple Pulp "repos" together into one libsolv
        "repo", because libsolv can only have one repo be "installed" at a time. Therefore, when
        the override_repo_name is specified, the created solvables are associated with the
        override repo, but the mapping stores them with their original Pulp repo_id.

        :param override_repo_name: Override name to use when adding solvables to a libsolv repo
        :type override_repo_name: str
        """
        repo_name = str(repo_id)
        libsolv_repo_name = str(override_repo_name) if override_repo_name else repo_name
        repo = self.mapping.get_repo(libsolv_repo_name)
        if not repo:
            repo = self.mapping.register_repo(
                libsolv_repo_name,
                self._pool.add_repo(libsolv_repo_name)
            )
            repodata = repo.add_repodata()
        else:
            repodata = repo.first_repodata()

        for unit in units:
            try:
                factory = self.type_factory_mapping[unit['_content_type_id']]
            except KeyError as err:
                raise ValueError('Unsupported unit type: {}', err)
            solvable = factory(repo, unit)
            self.mapping.register(unit, solvable, libsolv_repo_name)

        # Need to call pool->addfileprovides(), pool->createwhatprovides() after loading new repo
        self._finalized = False

        repodata.internalize()

    def _handle_nothing_provides(self, info):
        """Handle a case where nothing provides a given requirement.

        Some units may depend on other units outside the repo, and that will cause issues with the
        solver. We need to create some dummy packages to fulfill those provides so that the
        solver can continue. Essentially we pretend the missing dependencies are already installed.

        :param info: A class describing why the rule was broken
        :type info: solv.RuleInfo
        """
        target_repo = self.mapping.get_repo(COMBINED_TARGET_REPO_NAME)
        if not target_repo:
            return
        dummy = target_repo.add_solvable()
        dummy.name = 'dummy-provides:{}'.format(str(info.dep))
        dummy.arch = 'noarch'
        dummy.evr = ''
        dummy.add_deparray(solv.SOLVABLE_PROVIDES, info.dep)
        self._pool.createwhatprovides()
        _LOGGER.debug('Created dummy provides: {name}', name=info.dep.str())

    def _handle_same_name(self, info, jobs):
        """Handle a case where multiple versions of a package are "installed".

        Libsolv by default will make the assumption that you can't "install" multiple versions of
        a package, so in cases where we create that situation, we need to pass a special flag.
        """

        def locate_solvable_job(solvable, flags, jobs):
            for idx, job in enumerate(jobs):
                if job.what == solvable.id and job.how == flags:
                    _LOGGER.debug('Found job: %s', str(job))
                    return idx

        def enforce_solvable_job(solvable, flags, jobs):
            idx = locate_solvable_job(solvable, flags, jobs)
            if idx is not None:
                return

            enforce_job = self._pool.Job(flags, solvable.id)
            jobs.append(enforce_job)
            _LOGGER.debug('Added job %s', enforce_job)

        install_flags = solv.Job.SOLVER_INSTALL | solv.Job.SOLVER_SOLVABLE
        enforce_flags = install_flags | solv.Job.SOLVER_MULTIVERSION

        enforce_solvable_job(info.solvable, enforce_flags, jobs)
        enforce_solvable_job(info.othersolvable, enforce_flags, jobs)

    def _handle_problems(self, problems, jobs):
        """Handle problems libsolv finds during the depsolving process that can be worked around.
        """
        for problem in problems:
            for problem_rule in problem.findallproblemrules():
                for info in problem_rule.allinfos():
                    if info.type == solv.Solver.SOLVER_RULE_PKG_NOTHING_PROVIDES_DEP:
                        # No solvable provides the dep
                        if not self.ignore_missing:
                            continue
                        self._handle_nothing_provides(info)

                    elif info.type == solv.Solver.SOLVER_RULE_PKG_REQUIRES:
                        # A solvable provides the dep but could not be installed for some reason
                        continue

                    elif info.type == solv.Solver.SOLVER_RULE_INFARCH:
                        # The solver isn't allowed to rely on packages of an inferior architecture
                        # ie. i686 when x86_64 is being solved for
                        continue

                    elif info.type == solv.Solver.SOLVER_RULE_PKG_SAME_NAME:
                        # The deps can only be fulfilled by multiple versions of a package,
                        # but installing multiple versions of the same package is not allowed.
                        self._handle_same_name(info, jobs)

                    else:
                        _LOGGER.warning(
                            'No workaround available for problem \'%s\'. '
                            'You may refer to the libsolv Solver class documentation '
                            'for more details. See https://github.com/openSUSE/'
                            'libsolv/blob/master/doc/libsolv-bindings.txt'
                            '#the-solver-class.', problem_rule.info().problemstr()
                        )
        self._pool.createwhatprovides()

    def find_dependent_solvables_conservative(self, solvables):
        """Find the RPM dependencies that need to be copied to satisfy copying the provided units,
        taking into consideration what units are already present in the target repository.

        Create libsolv jobs to install each one of the units passed in, collect and combine the
        results. For modules, libsolv jobs are created to install each of their artifacts
        separately.

        A libsolv "Job" is a request for the libsolv sat solver to process. For instance a job with
        the flags SOLVER_INSTALL | SOLVER_SOLVABLE will tell libsolv to solve an installation of
        a package which is specified by solvable ID, as opposed to by name, or by pattern, which
        are other options available.

        See: https://github.com/openSUSE/libsolv/blob/master/doc/libsolv-bindings.txt#the-job-class

        :param units: An iterable of Pulp content units types supported by the type factory mapping.
        :type units: An iterable of dictionaries
        """
        if not solvables:
            return set()

        result_solvables = set()
        self._pool.createwhatprovides()
        flags = solv.Job.SOLVER_INSTALL | solv.Job.SOLVER_SOLVABLE

        def run_solver_jobs(jobs):
            """ Take a list of jobs, get a solution, return the set of solvables that needed to
            be installed.
            """
            previous_problems = set()
            attempt = 1

            while True:
                solver = self._pool.Solver()
                raw_problems = solver.solve(jobs)
                problems = set(str(problem) for problem in raw_problems)
                if not problems or previous_problems == problems:
                    break
                self._handle_problems(raw_problems, jobs)
                previous_problems = problems
                attempt += 1

            if problems:
                # The solver is simply ignoring the problems encountered and proceeds associating
                # any new solvables/units. This might be reported back to the user one day over
                # the REST API.
                _LOGGER.debug('Encountered problems solving: {}'.format(', '.join(problems)))

            transaction = solver.transaction()
            return set(transaction.newsolvables())

        solvables_to_copy = set(solvables)
        while solvables_to_copy:
            # Take one solvable
            solvable = solvables_to_copy.pop()
            install_jobs = []

            if solvable.name.startswith("module:"):
                # If the solvable being installed is a module, try to install it and all of its
                # modular artifact dependencies
                module_dep = self._pool.rel2id(
                    self._pool.str2id(solvable.name),
                    self._pool.str2id(solvable.arch),
                    solv.REL_ARCH
                )
                module_artifacts = self._pool.whatcontainsdep(solv.SOLVABLE_REQUIRES, module_dep)

                module_install_job = self._pool.Job(flags, solvable.id)
                install_jobs.append(module_install_job)

                for artifact in module_artifacts:
                    artifact_install_job = self._pool.Job(flags, artifact.id)
                    install_jobs.append(artifact_install_job)
            else:
                # If the unit being copied is not a module, just install it alone
                unit_install_job = self._pool.Job(flags, solvable.id)
                install_jobs.append(unit_install_job)

            # Depsolv using the list of unit install jobs, add them to the results
            solvables_copied = run_solver_jobs(install_jobs)
            result_solvables.update(solvables_copied)

        return result_solvables

    def find_dependent_solvables_relaxed(self, solvables):
        """Find the dependent solvables that need to be copied to satisfy copying the provided
        solvables, without taking into consideration the target repository. Just copy the most
        recent versions of each.
        """
        pool = self._pool
        seen = set()
        # Please note that providers of the requirements can be found in both the target
        # and source repo but each provider is a distinct solvable, so even though a particular
        # unit can seem to appear twice in the pool.whatprovides() set, it's just a different
        # solvable.
        candq = set(solvables)
        pool.createwhatprovides()
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

                        if provider in seen or repo != self.primary_source_repo.repo_id:
                            continue
                        candq.add(provider)

        targets = self.mapping.get_repo_units(self.primary_target_repo.repo_id)
        for target_repo in self._additional_repo_mapping.values():
            targets |= self.mapping.get_repo_units(target_repo)

        return [s for s in seen if self.mapping.get_unit_id(s)[0] not in targets]

    def find_dependent_rpms(self, units):
        """Find the set of dependent units and return them in a dictionary where
        the key is the repository the set of units came from.

        :returns: A dictionary of form {'repo_id': set(unit_ids**)}
        :rtype: dict
        """
        assert self._finalized, "Depsolver must be finalized before it can be used"

        solvables = [
            self.mapping.get_solvable(unit, self.primary_source_repo.repo_id) for unit in units
        ]

        if self.conservative:
            result_solvables = self.find_dependent_solvables_conservative(solvables)
        else:
            result_solvables = self.find_dependent_solvables_relaxed(solvables)

        return self.mapping.get_units_from_solvables(result_solvables)
