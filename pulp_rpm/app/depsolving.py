import collections
import logging
import os

import solv

from pulp_rpm.app import models


logger = logging.getLogger(__name__)

# The name for the repo inside libsolv which represents the combined set of target/destination
# repositories. Libsolv only supports one "installed" repo at a time, therefore we need to
# combine them and determine what units actually go where afterwards.
COMBINED_TARGET_REPO_NAME = "combined_target_repo"

# Constants for loading data from the database.
RPM_FIELDS = [
    'pk',
    'name',
    'version',
    'release',
    'epoch',
    'arch',
    'rpm_vendor',
    'provides',
    'requires',
    'files',
]

MODULE_FIELDS = [
    'pk',
    'name',
    'stream',
    'version',
    'context',
    'arch',
    'dependencies',
    'artifacts',
]

MODULE_DEFAULTS_FIELDS = [
    'pk',
    'module',
    'stream',
    'profiles',
]


def parse_nevra(name):
    """Parse NEVRA.

    Original from Pulp 2.

    Args:
        name (str): NEVR "jay-3:3.10-4.fc3.x86_64"

    Returns: (tuple) Parsed NEVR (name: str, epoch: int, version: str, release: str, arch: str)
    """
    if name.count(".") < 1:
        raise ValueError("failed to parse nevra '%s' not a valid nevra" % name)

    arch_dot_pos = name.rfind(".")
    arch = name[arch_dot_pos + 1:]

    return parse_nevr(name[:arch_dot_pos]) + (arch, )


def parse_nevr(name):
    """Parse NEVR.

    Originally from Pulp 2.

    Args:
        name (str): NEVR "jay-3:3.10-4.fc3"

    Returns: (tuple) Parsed NEVR (name: str, epoch: int, version: str, release: str)
    """
    if name.count("-") < 2:  # release or name is missing
        raise ValueError("failed to parse nevr '%s' not a valid nevr" % name)

    release_dash_pos = name.rfind("-")
    release = name[release_dash_pos + 1:]
    name_epoch_version = name[:release_dash_pos]
    name_dash_pos = name_epoch_version.rfind("-")
    package_name = name_epoch_version[:name_dash_pos]

    epoch_version = name_epoch_version[name_dash_pos + 1:].split(":")
    if len(epoch_version) == 1:
        epoch = 0
        version = epoch_version[0]
    elif len(epoch_version) == 2:
        epoch = int(epoch_version[0])
        version = epoch_version[1]
    else:
        # more than one ':'
        raise ValueError("failed to parse nevr '%s' not a valid nevr" % name)

    return package_name, epoch, version, release


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
    )


def rpm_to_solvable(solv_repo, unit):
    """Convert a Pulp RPM dict to a libsolv solvable.

    Args:
        solv_repo (solv.Repo): The libsolv repository the unit is being created in.
        unit (dict): The unit being converted.

    Returns:
        (solv.Solvable) The solvable created.

    """
    solvable = solv_repo.add_solvable()

    def rpm_filelist_conversion(solvable, unit):
        """A specific, rpm-unit-type filelist attribute conversion."""
        repodata = solv_repo.first_repodata()

        for file_repr in unit.get('files', []):
            dir_path = file_repr[1]
            dirname_id = repodata.str2dir(dir_path)
            repodata.add_dirstr(
                solvable.id, solv.SOLVABLE_FILELIST,
                dirname_id, os.path.basename(dir_path)
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

    name = unit.get('name')
    solvable.name = name

    evr = libsolv_formatted_evr(unit.get('epoch'), unit.get('version'), unit.get('arch'))
    solvable.evr = evr

    arch = unit.get('arch', 'noarch')
    solvable.arch = arch

    vendor = unit.get('vendor')
    if vendor:
        vendor = vendor
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

    Args:
        solvable (solvable): a libsolv solvable object
        unit (dict): the content unit to get the dependencies from

    """
    unit_name = unit[0]
    unit_flags = unit[1]
    unit_evr = libsolv_formatted_evr(unit[2], unit[3], unit[4])

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


def module_to_solvable(solv_repo, unit):
    """Convert a Pulp Module in dict representation to a libsolv solvable.

    Args:
        solv_repo (solv.Repo): The repository the unit is being added into
        unit (pulp_rpm.plugins.models.Model): The unit being converted

    Returns: (solv.Solvable) The solvable created.
    """
    solvable = solv_repo.add_solvable()
    pool = solvable.repo.pool

    def module_solvable_name(unit):
        """
        Create a solvable name from module attributes.

        e.g. module:<name>:<stream>:<version>:<context>
        """
        return 'module:{name}:{stream}:{version!s}:{context}'.format(
            name=unit.get('name'),
            stream=unit.get('stream'),
            version=unit.get('version'),
            context=unit.get('context'),
        )

    def module_basic_deps(pool, solvable, solvable_name, name, stream, version, arch):
        """
        Create the basic module `Provides:` relations.
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

    arch = unit.get('arch', 'noarch')
    solvable.arch = arch

    name = unit.get('name')
    stream = unit.get('stream')
    version = unit.get('version')

    module_basic_deps(pool, solvable, solvable_name, name, stream, version, arch)

    for artifact in unit.get('artifacts', []):
        nevra_tuple = parse_nevra(artifact)
        artifact_name = nevra_tuple[0]
        artifact_epoch = nevra_tuple[1]
        artifact_version = nevra_tuple[2]
        artifact_release = nevra_tuple[3]
        artifact_arch = nevra_tuple[4] if nevra_tuple[4] else 'noarch'
        artifact_evr = libsolv_formatted_evr(artifact_epoch, artifact_version, artifact_release)

        module_artifacts_conversion(pool, solvable, artifact_name, artifact_evr, artifact_arch)

    module_dependencies_conversion(pool, solvable, unit.get('dependencies', {}))
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

    Args:
        pool (solv.Pool): The libsolv pool that owns the module
        module_solvable (solv.Solvable): A solvable representing the module
        dependency_list (list): List of dictionaries representing modulemd dependency data.
    """
    # A near exact copy of the algorithm here:
    # https://pagure.io/fm-orchestrator/blob/db03f0a7f530cc2bf2f8971f085a9e6b71595d70/f/
    # module_build_service/mmd_resolver.py#_53

    def stream_dep(name, stream):
        """
        Create a libsolv Dep from a name and stream.

        Every name:stream combination from dict in `deps` list is expressed as `solv.Dep`
        instance and is represented internally in solv with "module(name:stream)".
        This is parallel to RPM-world "Provides: perl(foo)" or "Requires: perl(foo)",
        but in this method, we are only constructing the condition after the "Provides:"
        or "Requires:". This method creates such solve.Dep().
        """
        return pool.Dep("module({}:{})".format(name, stream))

    def dep_or_rel(dep, op, rel):
        """
        Helper method for creating reps and relational deps.

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

            # The req_pos will store solv.Dep expression for "positive" requirements.
            # That is the case of 'gtk': ['1', '2'].
            # The req_neg will store negative requirements like 'gtk': ['-1', '-2'].
            req_pos = req_neg = None

            # For each stream in `streams` for this dependency, generate the
            # module(name:stream) solv.Dep and add REL_OR relations between them.
            for stream in streams:
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

    Args:
        solv_repo (solv.Repo): The repository the unit is being added into.
        unit (pulp_rpm.plugins.models.Model): The unit being converted.

    Returns: (solv.Solvable) The solvable created.
    """
    solvable = solv_repo.add_solvable()
    solvable.evr = ''
    # a module default has no arch, use 'noarch'
    solvable.arch = 'noarch'

    name = unit.get('name')
    stream = unit.get('stream')

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
                # mark the related module so it can be queried as
                # '(module() with module-default())' i.e such that it's easy visible through
                # a pool.whatprovides that it has a default
                module.add_deparray(solv.SOLVABLE_PROVIDES, pool.Dep('module-default()'))

        # Note: Since we're copying the module default metadata as-is without modification or
        # regeneration, that means that "profiles" may be copied for streams that do not exist.
        # We think this is probably OK but if it is not, the solution is to "require" all streams
        # for which a profile exists.

    module_defaults_basic_deps(solvable, name, stream)

    return solvable


class UnitSolvableMapping:
    """Map libsolv solvables to Pulp units and repositories.

    Translate between what libsolv understands, solvable IDs in a pool, and what Pulp understands,
    units and repositories.
    """

    def __init__(self):
        """Mapping Init."""
        # Stores data in the form (pulp_unit_id, pulp_repo_id): solvable
        self._mapping_unit_to_solvable = {}
        # Stores data in the form solvable_id: (pulp_unit_id, pulp_repo_id)
        self._mapping_solvable_to_unit = {}
        # Stores data in the form pulp_repo_id: libsolv_repo_id
        self._mapping_repos = {}

    def register(self, unit_id, solvable, repo_id):
        """Store the matching of a unit-repo pair to a solvable inside of the mapping.
        """
        if not self.get_repo(str(repo_id)):
            raise ValueError(
                "Attempting to register unit {} to unregistered repo {}".format(unit_id, repo_id)
            )

        self._mapping_solvable_to_unit.setdefault(solvable.id, (unit_id, repo_id))
        self._mapping_unit_to_solvable.setdefault((unit_id, repo_id), solvable)

        logger.debug('Loaded unit {unit}, {repo} as {solvable}'.format(
            unit=unit_id, solvable=solvable, repo=repo_id
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
        """
        return self._mapping_solvable_to_unit.get(solvable.id)

    def get_solvable(self, unit_id, repo_id):
        """Fetch the libsolv solvable associated with a unit-repo pair.
        """
        return self._mapping_unit_to_solvable.get((unit_id, repo_id))

    def get_repo_units(self, repo_id):
        """Get back unit ids of all units that were in a repo based on the mapping.
        """
        return set(
            unit_id for (unit_id, unit_repo_id) in self._mapping_unit_to_solvable.keys()
            if unit_repo_id == repo_id
        )

    def get_units_from_solvables(self, solvables):
        """Map a list of solvables into their Pulp units, keyed by the repo they came from.
        """
        repo_unit_map = collections.defaultdict(set)
        for solvable in solvables:
            (unit_id, repo_id) = self.get_unit_id(solvable)
            repo_unit_map[repo_id].add(unit_id)

        return repo_unit_map


class Solver:
    """A Solver object that can speak in terms of Pulp units.
    """

    def __init__(self):
        """Solver Init."""
        self._finalized = False
        self._pool = solv.Pool()
        self._pool.setarch()  # prevent https://github.com/openSUSE/libsolv/issues/267
        self.mapping = UnitSolvableMapping()

    def finalize(self):
        """Finalize the solver - a finalized solver is ready for depsolving.

        Libsolv needs to perform some scans/hashing operations before it can do certain things.
        For more details see:
        https://github.com/openSUSE/libsolv/blob/master/doc/libsolv-bindings.txt
        """
        self._pool.installed = self.mapping.get_repo(COMBINED_TARGET_REPO_NAME)
        self._pool.addfileprovides()
        self._pool.createwhatprovides()
        self._finalized = True

    def load_source_repo(self, repo_version):
        """Load the provided Pulp repo as a source repo.

        All units in the repo will be available to be "installed", or copied.
        """
        libsolv_repo_name = self._load_from_version(repo_version)
        logger.debug("Loaded repository '{}' version '{}' as source repo".format(
            repo_version.repository, repo_version.number)
        )
        return libsolv_repo_name

    def load_target_repo(self, repo_version):
        """Load the provided Pulp repo into the combined target repo.

        All units in the repo will be added to the combined target repo, the contents of which
        are considered "installed" by the solver.
        """
        libsolv_repo_name = self._load_from_version(repo_version, as_target=True)
        logger.debug("Loaded repository '{}' version '{}' into combined target repo".format(
            repo_version.repository, repo_version.number)
        )
        return libsolv_repo_name

    def _repo_version_to_libsolv_name(self, repo_version):
        """Produce a name to use for the libsolv repo from the repo version."""
        return "{}: version={}".format(repo_version.repository.name, repo_version.number)

    def _load_from_version(self, repo_version, as_target=False):
        """
        Generate solvables from Pulp units and add them to the mapping.

        In some circumstances, we want to load multiple Pulp "repos" together into one libsolv
        "repo", because libsolv can only have one repo be "installed" at a time. Therefore, when
        the override_repo_name is specified, the created solvables are associated with the
        override repo, but the mapping stores them with their original Pulp repo_id.

        Args:
            override_repo_name (str): Override name to use when adding solvables to a libsolv repo
        """
        if as_target:
            libsolv_repo_name = COMBINED_TARGET_REPO_NAME
        else:
            libsolv_repo_name = self._repo_version_to_libsolv_name(repo_version)

        repo = self.mapping.get_repo(libsolv_repo_name)
        if not repo:
            repo = self.mapping.register_repo(
                libsolv_repo_name,
                self._pool.add_repo(libsolv_repo_name)
            )
            repodata = repo.add_repodata()
        else:
            repodata = repo.first_repodata()

        # Load packages into the solver

        package_ids = repo_version.content.filter(
            pulp_type=models.Package.get_pulp_type()
        ).only('pk')

        nonmodular_rpms = models.Package.objects.filter(
            pk__in=package_ids, is_modular=False
        ).values(*RPM_FIELDS)

        for rpm in nonmodular_rpms.iterator(chunk_size=5000):
            self._add_unit_to_solver(rpm_to_solvable, rpm, repo, libsolv_repo_name)

        modular_rpms = models.Package.objects.filter(
            pk__in=package_ids, is_modular=True
        ).values(*RPM_FIELDS)

        for rpm in modular_rpms.iterator(chunk_size=5000):
            self._add_unit_to_solver(rpm_to_solvable, rpm, repo, libsolv_repo_name)

        # Load modules into the solver

        module_ids = repo_version.content.filter(
            pulp_type=models.Modulemd.get_pulp_type()
        ).only('pk')

        modules = models.Modulemd.objects.filter(pk__in=module_ids).values(*MODULE_FIELDS)

        for module in modules.iterator(chunk_size=5000):
            self._add_unit_to_solver(module_to_solvable, module, repo, libsolv_repo_name)

        # Load module defaults into the solver

        module_defaults_ids = repo_version.content.filter(
            pulp_type=models.ModulemdDefaults.get_pulp_type()
        ).only('pk')

        modulemd_defaults = models.ModulemdDefaults.objects.filter(
            pk__in=module_defaults_ids
        ).values(*MODULE_DEFAULTS_FIELDS)

        for module_default in modulemd_defaults.iterator(chunk_size=5000):
            self._add_unit_to_solver(
                module_defaults_unit_to_solvable, module_default, repo, libsolv_repo_name
            )

        # Need to call pool->addfileprovides(), pool->createwhatprovides() after loading new repo
        self._finalized = False

        repodata.internalize()
        return libsolv_repo_name

    def _add_unit_to_solver(self, conversion_func, unit, repo, libsolv_repo_name):
        solvable = conversion_func(repo, unit)
        self.mapping.register(unit['pk'], solvable, libsolv_repo_name)

    # def _handle_nothing_provides(self, info):
    #     """Handle a case where nothing provides a given requirement.

    #     Some units may depend on other units outside the repo, and that will cause issues with
    #     the solver. We need to create some dummy packages to fulfill those provides so that the
    #     solver can continue. Essentially we pretend the missing dependencies are already
    #     installed.

    #     :param info: A class describing why the rule was broken
    #     :type info: solv.RuleInfo
    #     """
    #     target_repo = self.mapping.get_repo(COMBINED_TARGET_REPO_NAME)
    #     if not target_repo:
    #         return
    #     dummy = target_repo.add_solvable()
    #     dummy.name = 'dummy-provides:{}'.format(str(info.dep))
    #     dummy.arch = 'noarch'
    #     dummy.evr = ''
    #     dummy.add_deparray(solv.SOLVABLE_PROVIDES, info.dep)
    #     self._pool.createwhatprovides()
    #     _LOGGER.debug('Created dummy provides: {name}', name=info.dep.str())

    # def _handle_same_name(self, info, jobs):
    #     """Handle a case where multiple versions of a package are "installed".

    #     Libsolv by default will make the assumption that you can't "install" multiple versions of
    #     a package, so in cases where we create that situation, we need to pass a special flag.
    #     """

    #     def locate_solvable_job(solvable, flags, jobs):
    #         for idx, job in enumerate(jobs):
    #             if job.what == solvable.id and job.how == flags:
    #                 _LOGGER.debug('Found job: %s', str(job))
    #                 return idx

    #     def enforce_solvable_job(solvable, flags, jobs):
    #         idx = locate_solvable_job(solvable, flags, jobs)
    #         if idx is not None:
    #             return

    #         enforce_job = self._pool.Job(flags, solvable.id)
    #         jobs.append(enforce_job)
    #         _LOGGER.debug('Added job %s', enforce_job)

    #     install_flags = solv.Job.SOLVER_INSTALL | solv.Job.SOLVER_SOLVABLE
    #     enforce_flags = install_flags | solv.Job.SOLVER_MULTIVERSION

    #     enforce_solvable_job(info.solvable, enforce_flags, jobs)
    #     enforce_solvable_job(info.othersolvable, enforce_flags, jobs)

    # def _handle_problems(self, problems, jobs):
    #     """Handle problems libsolv finds during the depsolving process that can be worked around.
    #     """
    #     for problem in problems:
    #         for problem_rule in problem.findallproblemrules():
    #             for info in problem_rule.allinfos():
    #                 if info.type == solv.Solver.SOLVER_RULE_PKG_NOTHING_PROVIDES_DEP:
    #                     # No solvable provides the dep
    #                     if not self.ignore_missing:
    #                         continue
    #                     self._handle_nothing_provides(info)

    #                 elif info.type == solv.Solver.SOLVER_RULE_PKG_REQUIRES:
    #                     # A solvable provides the dep but could not be installed for some reason
    #                     continue

    #                 elif info.type == solv.Solver.SOLVER_RULE_INFARCH:
    #                     # The solver isn't allowed to rely on packages of an inferior architecture
    #                     # ie. i686 when x86_64 is being solved for
    #                     continue

    #                 elif info.type == solv.Solver.SOLVER_RULE_PKG_SAME_NAME:
    #                     # The deps can only be fulfilled by multiple versions of a package,
    #                     # but installing multiple versions of the same package is not allowed.
    #                     self._handle_same_name(info, jobs)

    #                 else:
    #                     _LOGGER.warning(
    #                         'No workaround available for problem \'%s\'. '
    #                         'You may refer to the libsolv Solver class documentation '
    #                         'for more details. See https://github.com/openSUSE/'
    #                         'libsolv/blob/master/doc/libsolv-bindings.txt'
    #                         '#the-solver-class.', problem_rule.info().problemstr()
    #                     )
    #     self._pool.createwhatprovides()

    def resolve_dependencies(self, unit_repo_map):
        """Resolve the total set of packages needed for the packages passed in, as DNF would.

        Find the set of dependent units and return them in a dictionary where
        the key is the repository the set of units came from.

        Find the RPM dependencies that need to be copied to satisfy copying the provided units,
        taking into consideration what units are already present in the target repository.

        Create libsolv jobs to install each one of the units passed in, collect and combine the
        results. For modules, libsolv jobs are created to install each of their artifacts
        separately.

        A libsolv "Job" is a request for the libsolv sat solver to process. For instance a job with
        the flags SOLVER_INSTALL | SOLVER_SOLVABLE will tell libsolv to solve an installation of
        a package which is specified by solvable ID, as opposed to by name, or by pattern, which
        are other options available.

        See: https://github.com/openSUSE/libsolv/blob/master/doc/libsolv-bindings.txt#the-job-class

        Args:
            unit_repo_map: (dict) An iterable oflibsolv_repo_name =

        Returns: (dict) A dictionary of form {'repo_id': set(unit_ids**)}
        """
        assert self._finalized, "Depsolver must be finalized before it can be used"

        solvables = []
        # units (like advisories) that aren't solved for in the dependency solver need to be
        # passed through to the end somehow, so let's add them to a second mapping that mirrors
        # the first and combine them again at the end.
        passthrough = {k: set() for k in unit_repo_map.keys()}
        for repo, units in unit_repo_map.items():
            for unit in units:
                if unit.pulp_type in {"rpm.package", "rpm.modulemd", "rpm.modulemd_defaults"}:
                    solvables.append(self.mapping.get_solvable(unit.pk, repo))
                passthrough[repo].add(unit.pk)

        self._pool.createwhatprovides()
        flags = solv.Job.SOLVER_INSTALL | solv.Job.SOLVER_SOLVABLE

        def run_solver_jobs(jobs):
            """Execute the libsolv jobs, return results.

            Take a list of jobs, get a solution, return the set of solvables that needed to
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
                # self._handle_problems(raw_problems, jobs)  TODO
                previous_problems = problems
                attempt += 1

            if problems:
                # The solver is simply ignoring the problems encountered and proceeds associating
                # any new solvables/units. This might be reported back to the user one day over
                # the REST API.
                logger.debug('Encountered problems solving: {}'.format(', '.join(problems)))

            transaction = solver.transaction()
            return set(transaction.newsolvables())

        solvables_to_copy = set(solvables)
        result_solvables = set()
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

            # Depsolve using the list of unit install jobs, add them to the results
            solvables_copied = run_solver_jobs(install_jobs)
            result_solvables.update(solvables_copied)

        solved_units = self.mapping.get_units_from_solvables(result_solvables)
        for k in unit_repo_map.keys():
            solved_units[k] |= passthrough[k]

        return solved_units
