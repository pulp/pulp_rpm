from gettext import gettext as _

from mongoengine import Q

from pulp.plugins.profiler import Profiler, InvalidUnitsRequested
from pulp.server.controllers import repository as repo_controller
from pulp.server.db import model
from pulp.server.db.model.criteria import UnitAssociationCriteria

from pulp_rpm.common.constants import VIRTUAL_MODULEMDS
from pulp_rpm.common.ids import TYPE_ID_ERRATA, TYPE_ID_RPM, TYPE_ID_MODULEMD
from pulp_rpm.plugins.db import models
from pulp_rpm.yum_plugin import util

_logger = util.getLogger(__name__)

NVREA_KEYS = ['name', 'version', 'release', 'epoch', 'arch']


def entry_point():
    """
    The Pulp platform uses this method to load the profiler.

    :return: YumProfiler class and an (empty) config
    :rtype:  tuple
    """
    return YumProfiler, {}


class YumProfiler(Profiler):
    """
    Profiler plugin to support RPM and Errata functionality
    """
    TYPE_ID = 'yum_profiler'

    @classmethod
    def metadata(cls):
        return {
            'id': cls.TYPE_ID,
            'display_name': "Yum Profiler",
            'types': [TYPE_ID_RPM, TYPE_ID_ERRATA, TYPE_ID_MODULEMD]}

    @staticmethod
    def calculate_applicable_units(unit_profiles, bound_repo_id, config, conduit):
        """
        Calculate and return a dictionary with unit_type_ids as keys that index lists of content
        unit ids applicable to consumers with given unit_profiles. Applicability is calculated
        against all content units belonging to the given bound repository and available for
        given profiles.

        :param unit_profiles:  a list of consumer unit profiles
        :type  unit_profiles:  list of tuples
        :param bound_repo_id: repo id of a repository to be used to calculate applicability
                              against the given consumer profiles
        :type  bound_repo_id: str
        :param config: plugin configuration
        :type  config:        pulp.server.plugins.config.PluginCallConfiguration
        :param conduit:       provides access to relevant Pulp functionality
        :type  conduit:       pulp.plugins.conduits.profile.ProfilerConduit
        :return:              a dictionary mapping content_type_ids to lists of content unit ids
        :rtype:               dict
        """
        profile_lookup_table = {TYPE_ID_RPM: {},
                                TYPE_ID_MODULEMD: {}}

        # Form lookup tables for each of consumer profiles so that package lookups are constant time
        for profile_hash, content_type, profile in unit_profiles:
            profile_lookup_table[content_type] = YumProfiler._form_lookup_table(profile,
                                                                                content_type)

        return YumProfiler._calculate_applicable_units(profile_lookup_table, bound_repo_id,
                                                       config, conduit)

    @staticmethod
    def install_units(consumer, units, options, config, conduit):
        """
        Traverse the list of units to be installed, replacing any errata units with their
        corresponding RPM units, leaving existing RPM units untouched. Return a list of RPMs to be
        installed.

        units is a list of dictionaries with keys 'type_id' and 'unit_key'

        :param consumer: A consumer.
        :type  consumer: pulp.server.plugins.model.Consumer
        :param units:    A list of content units to be installed.
        :type  units:    list
        :param options:  Install options; based on unit type.
        :type  options:  dict
        :param config:   plugin configuration
        :type  config:   pulp.server.plugins.config.PluginCallConfiguration
        :param conduit:  provides access to relevant Pulp functionality
        :type  conduit:  pulp.plugins.conduits.profile.ProfilerConduit
        :return:         a list of dictionaries containing info on the 'translated units'.
                         each dictionary contains 'type_id' and 'unit_key' keys. All type_ids will
                         be of the RPM type.
        :rtype:          list
        :raises InvalidUnitsRequested: if an erratum was specified and no repository was found
                                       that contains the specified errata
        """
        translated_units = []
        for unit in units:
            if unit['type_id'] == TYPE_ID_RPM:
                translated_units.append(unit)
            elif unit['type_id'] == TYPE_ID_ERRATA:
                if TYPE_ID_RPM not in consumer.profiles:
                    reason = _('Consumer has no RPM unit profile')
                    raise InvalidUnitsRequested(units, reason)
                translated_units.append(unit)
        return translated_units

    @staticmethod
    def _remove_superseded_units(translated_units):
        """
        After generating a list of units to install, remove packages from the set that superseded
        by newer units (same name/arch, higher epoch/version/release)

        :param translated_units: a list of dictionaries containing info on the 'translated units'.
                                 each dictionary contains 'type_id' and 'unit_key' keys.
                                 All type_ids should be RPM, other types will be ignored.
        :type translated_units: list

        :return: a version of the translated_units list where superseded packages
                 (packages with newer versions present in the list of units) are removed
        :rtype: list
        """
        # for units that have filterable unit keys (all nevra fields in unit_key), use
        # _from_lookup_table to filter superseded units out of the filterable units
        # based on the install_units docs, all units should be filterable, but working
        # under that guideline breaks tests for this module, so unfilterable units are
        # ignored and returned
        filterable_units = []
        unfilterable_units = []
        for unit in translated_units:
            if 'unit_key' in unit and all(field in unit['unit_key'] for field in NVREA_KEYS):
                filterable_units.append(unit)
            else:
                unfilterable_units.append(unit)

        lookup_keys = [u['unit_key'] for u in filterable_units]
        filter_keys = YumProfiler._form_lookup_table(lookup_keys)[TYPE_ID_RPM].values()
        filtered_units = filter(lambda u: u['unit_key'] in filter_keys, filterable_units)

        # remember to give back the unfilterable units in addition to the filtered ones
        return filtered_units + unfilterable_units

    @staticmethod
    def update_profile(consumer, content_type, profile, config):
        """
        When the platform calculates the hash of our profile, the ordering of the profile list will
        affect the hash. We want the hash of consumers that have the same set of RPMs installed to
        match, regardless of which order they appear in their profiles. Because the profile must be
        stored as a list instead of a set, we will need to make sure that we sort the profile in a
        consistent manner before saving it to the database to guarantee that consumers with the same
        RPMs will have the same profile hash.

        The profile is a list of dictionaries with these keys: 'name', 'epoch', 'version',
        'release', 'arch', and 'vendor'. This method will create a list of the values that
        correspond to these keys, and use the sorting of that list to determine a repeatable sort
        for the profile itself.

        :param consumer:     A consumer.
        :type  consumer:     pulp.plugins.model.Consumer
        :param content_type: The content type id that the profile represents
        :type  content_type: basestring
        :param profile:      The reported profile.
        :type  profile:      list
        :param config:       plugin configuration
        :type  config:       pulp.plugins.config.PluginCallConfiguration
        :return:             The sorted profile.
        :rtype:              list
        """
        if content_type == TYPE_ID_RPM:
            profile = [
                ((p['name'], p['epoch'], p['version'], p['release'], p['arch'], p['vendor']), p)
                for p in profile]
            profile.sort()
            return [p[1] for p in profile]
        else:
            return profile

    @staticmethod
    def _get_enabled_rpm_module_map(profile_lookup_table, bound_repo):
        """
        Create a dict of modular RPMs which are available for a consumer and mapped to their module.

        Modular RPM availability means being present in a repo, having its module enabled and its
        module's dependencies satisfied.

        :param profile_lookup_table: the lookup table for installed RPMs and enabled modules
                                     on a consumer
        :type  profile_lookup_table: dict
        :param bound_repo: the repository consumer is bound to
        :type  bound_repo: pulp.server.db.model.Repository

        :return: enabled RPMs mapped to their module(s)
        :rtype: dict
        """
        # Get all modules
        modulemdq_set = repo_controller.find_repo_content_units(
            bound_repo,
            repo_content_unit_q=Q(unit_type_id=TYPE_ID_MODULEMD),
            unit_fields=models.Modulemd.unit_key_fields + ('artifacts', 'dependencies'),
            yield_content_unit=True)

        # A lookup table after excluding irrelevant modules/RPMs, maps RPM to the modules it's a
        # part of:
        # {modular_rpm_nevra: [modulemd unit_id, ...]}
        enabled_rpm_module_map = {}

        enabled_modules = profile_lookup_table[TYPE_ID_MODULEMD]

        for modulemd in modulemdq_set:
            # Exclude not enabled modules
            if not YumProfiler._is_enabled_module(modulemd.unit_key, enabled_modules):
                continue

            # Check if the first-level module dependencies are satisfied
            deps_resolved = True
            for dep in modulemd.dependencies:
                for dep_name, dep_streams in dep.items():
                    # for now we ignore virtual modules, they are not reported in consumer
                    # profiles, e.g. platform. It can give false negatives.
                    if dep_name in VIRTUAL_MODULEMDS:
                        continue

                    # module dependency is not among enabled ones
                    if dep_name not in profile_lookup_table[TYPE_ID_MODULEMD]:
                        deps_resolved = False
                        break

                    # only one stream can be enabled, so we can use any of the enabled module
                    # versions
                    enabled_stream = profile_lookup_table[TYPE_ID_MODULEMD][dep_name][0]['stream']
                    # no specific stream listed => any stream is ok
                    if not dep_streams:
                        continue

                    blacklisted_streams = [s[1:] for s in dep_streams if s.startswith('-')]
                    required_streams = [s for s in dep_streams if not s.startswith('-')]
                    # the stream is a conflicting one
                    if enabled_stream in blacklisted_streams:
                        deps_resolved = False
                        break

                    # the stream enabled is not among required ones => dependency is not satisfied
                    if required_streams and enabled_stream not in required_streams:
                        deps_resolved = False
                        break

            # Consider only RPMs from the modules which dependencies are satisfied
            if deps_resolved:
                artifacts = modulemd.rpm_search_dicts
                for artifact in artifacts:
                    rpm_nevra = YumProfiler._create_nevra(artifact)
                    enabled_rpm_module_map.setdefault(rpm_nevra, []).append(modulemd.id)
        return enabled_rpm_module_map

    @staticmethod
    def _calculate_applicable_units(profile_lookup_table, bound_repo_id, config, conduit):
        """
        Calculate and return a list of unit ids of given content_type applicable to a unit profile
        represented by given profile_lookup_table. Applicability is calculated against all units
        belonging to the given bound repository.

        :param profile_lookup_table: lookup table of unit profiles
        :type profile_lookup_table: dict
        :param bound_repo_id: repo id of a repository to be used to calculate applicability
                              against the given consumer profile
        :type  bound_repo_id: str
        :param config:        plugin configuration
        :type  config:        pulp.server.plugins.config.PluginCallConfiguration
        :param conduit:       provides access to relevant Pulp functionality
        :type  conduit:       pulp.plugins.conduits.profile.ProfilerConduit
        :return:              a list of errata unit ids
        :rtype:               list
        """
        bound_repo = model.Repository.objects.get_repo_or_missing_resource(bound_repo_id)

        enabled_rpm_module_map = YumProfiler._get_enabled_rpm_module_map(profile_lookup_table,
                                                                         bound_repo)

        modular_rpm_names_to_exclude = set(rpm[0] for rpm in enabled_rpm_module_map)

        applicable_unit_ids = {TYPE_ID_RPM: set(),
                               TYPE_ID_ERRATA: set(),
                               TYPE_ID_MODULEMD: set()}

        # Create lookup table of available RPMs for errata applicability, find applicable RPMs
        # and modules.
        additional_unit_fields = ['is_modular']
        rpms = conduit.get_repo_units(bound_repo_id, TYPE_ID_RPM, additional_unit_fields,
                                      NVREA_KEYS)

        available_rpm_nevras = {'modular': set(), 'non-modular': set()}
        for rpm in rpms:
            rpm_nevra = YumProfiler._create_nevra(rpm.unit_key)
            name = rpm_nevra[0]

            # Modular RPMs have to be among artifacts of enabled modules
            if rpm.metadata['is_modular'] and rpm_nevra in enabled_rpm_module_map:
                available_rpm_nevras['modular'].add(rpm_nevra)
                applicable = YumProfiler._is_rpm_applicable(rpm.unit_key, profile_lookup_table)
                if applicable:
                    applicable_modules = enabled_rpm_module_map[rpm_nevra]
                    applicable_unit_ids[TYPE_ID_MODULEMD] = \
                        applicable_unit_ids[TYPE_ID_MODULEMD].union(applicable_modules)

            # Modular RPMs have precedence over non-modular ones, so names of available non-modular
            # RPMs should not intersect with the modular ones.
            elif not rpm.metadata['is_modular'] and name not in modular_rpm_names_to_exclude:
                available_rpm_nevras['non-modular'].add(rpm_nevra)
                applicable = YumProfiler._is_rpm_applicable(rpm.unit_key, profile_lookup_table)
            else:
                applicable = False

            if applicable:
                applicable_unit_ids[TYPE_ID_RPM].add(rpm.metadata['unit_id'])

        additional_unit_fields = ['pkglist']
        errata = conduit.get_repo_units(bound_repo_id, TYPE_ID_ERRATA, additional_unit_fields)

        # Check applicability for Errata
        for erratum in errata:
            applicable = YumProfiler._is_errata_applicable(erratum, profile_lookup_table,
                                                           available_rpm_nevras)
            if applicable:
                applicable_unit_ids[TYPE_ID_ERRATA].add(erratum.metadata['unit_id'])

        # Convert sets to lists before returning the result
        result = {}
        for content_type, ids in applicable_unit_ids.items():
            result[content_type] = list(ids)
        return result

    @staticmethod
    def _find_unit_associated_to_repos(unit_type, unit_key, repo_ids, conduit):
        criteria = UnitAssociationCriteria(type_ids=[unit_type], unit_filters=unit_key)
        return YumProfiler._find_unit_associated_to_repos_by_criteria(criteria, repo_ids, conduit)

    @staticmethod
    def _find_unit_associated_to_repos_by_criteria(criteria, repo_ids, conduit):
        for repo_id in repo_ids:
            result = conduit.get_units(repo_id, criteria)
            if result:
                return result[0]
        return None

    @staticmethod
    def _form_lookup_key(unit, content_type=TYPE_ID_RPM):
        """
        Generate a key to represent an RPM's name and arch for use as a key in a dictionary. It
        returns a string that is simply the name and arch separated by a space, such as
        "pulp x86_64".
        For modules, name is a key.

        :param rpm: The unit key of the RPM for which we wish to generate a key
        :type  rpm: dict
        :return:    A string representing the RPM's name and arch
        :rtype:     str
        """
        if content_type == TYPE_ID_RPM:
            # This key needs to avoid usage of a ".", since it may be stored in mongo
            # when the upgrade_details are returned.
            return "%s %s" % (unit['name'], unit['arch'])
        elif content_type == TYPE_ID_MODULEMD:
            return unit['name']
        return unit

    @staticmethod
    def _form_lookup_table(units, content_type=TYPE_ID_RPM):
        """
        Build a dictionary mapping:
         - RPM names and arches (generated with the _form_lookup_key()
        method) to the full unit key for each RPM. In case of multiple rpms with same name and
        arch, unit key of the newest rpm is stored as the value.
         - Module names to the full unit key for each module.

        :param units: A list of units
        :type  units: list
        :return:     A dictionary mapping the lookup keys to the RPMor module unit keys
        :rtype:      dict
        """
        lookup = {}
        if content_type == TYPE_ID_RPM:
            for unit in units:
                key = YumProfiler._form_lookup_key(unit, content_type=content_type)
                # In case of duplicate key, replace the value only if the rpm is newer
                # than the old value.
                if key in lookup:
                    existing_unit = lookup[key]
                    if not util.is_rpm_newer(unit, existing_unit):
                        continue
                lookup[key] = unit
        elif content_type == TYPE_ID_MODULEMD:
            # we need a lookup by name for dependencies but there can be multiple module versions
            # enabled, so one module name refers to a list of modules.
            for unit in units:
                key = YumProfiler._form_lookup_key(unit, content_type=content_type)
                lookup.setdefault(key, []).append(unit)
        return lookup

    @staticmethod
    def _is_errata_applicable(errata, profile_lookup_table, available_rpm_nevras):
        """
        Checks whether given errata is applicable to the consumer.

        An erratum is applicable:
         - in case the erratum refers to a module:
           - if module is enabled
           - if dependent modules are enabled
           - if at least one RPM which is referred in the erratum is present in a repo
           - if that RPM is newer than the installed one
         - in case no module is specified in the erratum:
           - if at least one RPM which is referred in the erratum is present in a repo
           - if RPM name doesn't match the name of any of the enabled modular RPMs
           - if that RPM is newer than the installed one

        RHBZ #1171280: ensure we are only checking applicability against RPMs
        we have access to in the repo. This is to prevent a RHEL6 machine
        from finding RHEL7 packages, for example.

        :param errata: Errata unit for which the applicability is being checked
        :type errata: pulp.plugins.model.Unit

        :param profile_lookup_table: lookup table of unit profiles
        :type profile_lookup_table: dict

        :param available_rpm_nevras: NEVRA of packages available in a repo divided by is_modular
                                     flag
        :type available_rpm_nevras: dict

        :return: true if applicable, false otherwise
        :rtype: boolean
        """
        pkglist = errata.metadata.get('pkglist')
        enabled_modules = profile_lookup_table[TYPE_ID_MODULEMD]
        for collection in pkglist:
            rpm_type = 'non-modular'
            module = collection.get('module')
            if module:
                if not YumProfiler._is_enabled_module(module, enabled_modules):
                    continue
                rpm_type = 'modular'

            for errata_rpm in collection['packages']:
                rpm_nevra = YumProfiler._create_nevra(errata_rpm)
                if rpm_nevra in available_rpm_nevras[rpm_type]:
                    applicable = YumProfiler._is_rpm_applicable(errata_rpm,
                                                                profile_lookup_table)
                    if applicable:
                        return True

        # Return false if none of the errata rpms are applicable
        return False

    @staticmethod
    def _is_rpm_applicable(rpm_unit_key, profile_lookup_table):
        """
        Checks whether given rpm upgrades an rpm on the consumer.

        :param rpm_unit_key:         An rpm's unit_key
        :type  rpm_unit_key:         dict
        :param profile_lookup_table: lookup table of consumer profile keyed by "name arch"
        :type  profile_lookup_table: dict
        :return:                     true if applicable, false otherwise
        :rtype:                      boolean
        """
        if not rpm_unit_key or not profile_lookup_table:
            return False

        key = YumProfiler._form_lookup_key(rpm_unit_key)

        if key in profile_lookup_table[TYPE_ID_RPM]:
            installed_rpm = profile_lookup_table[TYPE_ID_RPM][key]
            # If an rpm is found, check if it is older than the available rpm
            if util.is_rpm_newer(rpm_unit_key, installed_rpm):
                return True

        return False

    @staticmethod
    def _create_nevra(r):
        """
        A small helper method for comparing errata packages to rpm units

        The "str()" conversion may be overly defensive but I am not sure. There
        were mocks that needed this but I did not find an example during
        testing with real data.

        """
        if 'epoch' not in r or r['epoch'] is None:
            r['epoch'] = '0'

        return tuple(str(r[k]) for k in ('name', 'epoch', 'version', 'release', 'arch'))

    @staticmethod
    def _is_enabled_module(module, enabled_modules):
        """
        Check if module is enabled

        :param module: NSVCA of a module
        :type  module: dict
        :param enabled_modules: modules enabled on a consumer
        :type  enabled_modules: dict
        :return: True if a module is enabled, False otherwise
        :rtype: bool
        """
        for enabled_module in enabled_modules.get(module['name'], []):
            if YumProfiler._are_equal_modules(module, enabled_module):
                return True
        return False

    @staticmethod
    def _are_equal_modules(module1, module2):
        """
        Compare two modules.

        Due to different sources of module info some casting should happen for proper comparison

        :param module1: NSVCA of one module
        :type  module1: dict
        :param module2: NSVCA of the other module
        :type  module2: dict

        :return: True if modules are the same, False otherwise
        :rtype: bool
        """
        module1_serialized = module1.copy()
        module1_serialized['version'] = int(module1_serialized['version'])

        module2_serialized = module2.copy()
        module2_serialized['version'] = int(module2_serialized['version'])

        return module1_serialized == module2_serialized
