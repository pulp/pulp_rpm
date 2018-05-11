from gettext import gettext as _
from logging import DEBUG

from pulp.plugins.profiler import Profiler, InvalidUnitsRequested
from pulp.server.db.model.criteria import UnitAssociationCriteria

from pulp_rpm.common.ids import TYPE_ID_ERRATA, TYPE_ID_RPM
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
            'types': [TYPE_ID_RPM, TYPE_ID_ERRATA]}

    @staticmethod
    def calculate_applicable_units(unit_profile, bound_repo_id, config, conduit):
        """
        Calculate and return a dictionary with unit_type_ids as keys that index lists of content
        unit ids applicable to consumers with given unit_profile. Applicability is calculated
        against all content units belonging to the given bound repository.

        :param unit_profile:  a consumer unit profile
        :type  unit_profile:  list of dicts
        :param bound_repo_id: repo id of a repository to be used to calculate applicability
                              against the given consumer profile
        :type  bound_repo_id: str
        :param config: plugin configuration
        :type  config:        pulp.server.plugins.config.PluginCallConfiguration
        :param conduit:       provides access to relevant Pulp functionality
        :type  conduit:       pulp.plugins.conduits.profile.ProfilerConduit
        :return:              a dictionary mapping content_type_ids to lists of content unit ids
        :rtype:               dict
        """
        # Form a lookup table for consumer unit profile so that package lookups are constant time
        profile_lookup_table = YumProfiler._form_lookup_table(unit_profile)

        return {
            TYPE_ID_RPM: YumProfiler._calculate_applicable_units(TYPE_ID_RPM, profile_lookup_table,
                                                                 bound_repo_id, config, conduit),
            TYPE_ID_ERRATA: YumProfiler._calculate_applicable_units(TYPE_ID_ERRATA,
                                                                    profile_lookup_table,
                                                                    bound_repo_id, config, conduit)}

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
        filter_keys = YumProfiler._form_lookup_table(lookup_keys).values()
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
    def _calculate_applicable_units(content_type, profile_lookup_table, bound_repo_id, config,
                                    conduit):
        """
        Calculate and return a list of unit ids of given content_type applicable to a unit profile
        represented by given profile_lookup_table. Applicability is calculated against all units
        belonging to the given bound repository.

        :param content_type:  The content type id that the profile represents
        :type  content_type:  basestring
        :param profile_lookup_table: lookup table of a unit profile keyed by "name arch"
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
        # Get all units associated with given repository of content_type
        additional_unit_fields = ['pkglist'] if content_type == TYPE_ID_ERRATA else []
        units = conduit.get_repo_units(bound_repo_id, content_type, additional_unit_fields)

        # this needs to be fetched outside of the units loop :)
        if content_type == TYPE_ID_ERRATA:
            available_rpm_nevras = set([YumProfiler._create_nevra(r.unit_key) for r in
                                        conduit.get_repo_units(bound_repo_id, TYPE_ID_RPM)])

        applicable_unit_ids = []
        # Check applicability for each unit
        for unit in units:
            if content_type == TYPE_ID_RPM:
                applicable = YumProfiler._is_rpm_applicable(unit.unit_key, profile_lookup_table)
            elif content_type == TYPE_ID_ERRATA:
                applicable = YumProfiler._is_errata_applicable(
                    unit, profile_lookup_table, available_rpm_nevras)
            else:
                applicable = False

            if applicable:
                applicable_unit_ids.append(unit.metadata['unit_id'])

        return applicable_unit_ids

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
    def _form_lookup_key(rpm):
        """
        Generate a key to represent an RPM's name and arch for use as a key in a dictionary. It
        returns a string that is simply the name and arch separated by a space, such as
        "pulp x86_64".

        :param rpm: The unit key of the RPM for which we wish to generate a key
        :type  rpm: dict
        :return:    A string representing the RPM's name and arch
        :rtype:     str
        """
        # This key needs to avoid usage of a ".", since it may be stored in mongo
        # when the upgrade_details are returned.
        return "%s %s" % (rpm['name'], rpm['arch'])

    @staticmethod
    def _form_lookup_table(rpms):
        """
        Build a dictionary mapping RPM names and arches (generated with the _form_lookup_key()
        method) to the full unit key for each RPM. In case of multiple rpms with same name and
        arch, unit key of the newest rpm is stored as the value.

        :param rpms: A list of RPM unit keys
        :type  rpms: list
        :return:     A dictionary mapping the lookup keys to the RPM unit keys
        :rtype:      dict
        """
        lookup = {}
        for rpm in rpms:
            key = YumProfiler._form_lookup_key(rpm)
            # In case of duplicate key, replace the value only if the rpm is newer
            # than the old value.
            if key in lookup:
                existing_unit = lookup[key]
                if not util.is_rpm_newer(rpm, existing_unit):
                    continue
            lookup[key] = rpm
        return lookup

    @staticmethod
    def _get_rpms_from_errata(errata):
        """
        Return a list of RPMs that are referenced by an errata's pkglist

        This method will translate 'null' to '0' in the epoch field. All
        package lists should contain epoch fields but some do not.

        :param errata: The errata we wish to query for RPMs it contains
        :type errata:  pulp.plugins.model.Unit
        :return:       list of rpms, which are each a dict of nevra info
        :rtype:        list
        """
        rpms = []
        if "pkglist" not in errata.metadata:
            msg = _("metadata for errata <%(errata_id)s> lacks a 'pkglist'")
            msg_dict = {'errata_id': errata.unit_key.get('errata_id')}
            _logger.warning(msg, msg_dict)
            return rpms
        for pkgs in errata.metadata['pkglist']:
            for rpm in pkgs["packages"]:
                if 'epoch' not in rpm or rpm['epoch'] is None:
                    rpm['epoch'] = '0'
                rpms.append(rpm)
        return rpms

    @staticmethod
    def _is_errata_applicable(errata, profile_lookup_table, available_rpm_nevras):
        """
        Checks whether given errata is applicable to the consumer.

        :param errata: Errata unit for which the applicability is being checked
        :type errata: pulp.plugins.model.Unit

        :param profile_lookup_table: lookup table of a unit profile keyed by "name arch"
        :type profile_lookup_table: dict

        :param available_rpm_nevras: NEVRA of packages available in a repo
        :type available_rpm_nevras: list of tuples

        :return: true if applicable, false otherwise
        :rtype: boolean
        """
        # Get rpms from errata
        pkglists = models.Errata.get_unique_pkglists(errata.unit_key.get('errata_id'))

        # RHBZ #1171280: ensure we are only checking applicability against RPMs
        # we have access to in the repo. This is to prevent a RHEL6 machine
        # from finding RHEL7 packages, for example.
        for pkglist in pkglists:
            for collection in pkglist:
                for errata_rpm in collection:
                    if YumProfiler._create_nevra(errata_rpm) in available_rpm_nevras and \
                       YumProfiler._is_rpm_applicable(errata_rpm, profile_lookup_table):
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

        if key in profile_lookup_table:
            installed_rpm = profile_lookup_table[key]
            # If an rpm is found, check if it is older than the available rpm
            if util.is_rpm_newer(rpm_unit_key, installed_rpm):
                return True

        return False

    @staticmethod
    def _rpms_applicable_to_consumer(consumer, errata_rpms):
        """
        :param consumer: profiled consumer
        :type consumer: pulp.server.plugins.model.Consumer

        :param errata_rpms: list of errata rpms
        :type errata_rpms: list of dicts

        :return: tuple, first entry list of dictionaries of applicable
        rpm entries, second entry dictionary with more info
        of which installed rpm will be upgraded by what rpm

        Note:
        This method does not take into consideration if the consumer
        is bound to the repo containing the RPM.
        :rtype: ([{}], {})
        """
        applicable_rpms = []
        older_rpms = {}
        if TYPE_ID_RPM not in consumer.profiles:
            msg = _("Consumer [%(consumer_id)s] missing profile information for [%("
                    "type_id_rpm)s], found profiles are: %(profiles)s")
            msg_dict = {'consumer_id': consumer.id, 'type_id_rpm': TYPE_ID_RPM,
                        'profiles': consumer.profiles.keys()}
            _logger.warn(msg, msg_dict)
            return applicable_rpms, older_rpms
        lookup = YumProfiler._form_lookup_table(consumer.profiles[TYPE_ID_RPM])
        for errata_rpm in errata_rpms:
            key = YumProfiler._form_lookup_key(errata_rpm)
            if key in lookup:
                installed_rpm = lookup[key]
                is_newer = util.is_rpm_newer(errata_rpm, installed_rpm)
                msg = _("Found a match of rpm <%(rpm)s> installed on consumer, is "
                        "%(errata_rpm)s newer than %(installed_rpm)s, %(is_newer)s")
                msg_dict = {'rpm': key, 'errata_rpm': errata_rpm, 'installed_rpm': installed_rpm,
                            'is_newer': is_newer}
                _logger.debug(msg, msg_dict)
                if is_newer:
                    applicable_rpms.append(errata_rpm)
                    older_rpms[key] = {"installed": installed_rpm, "available": errata_rpm}
            else:
                msg = _("rpm %(key)s was not found in consumer profile of %(consumer_id)s")
                _logger.debug(msg % {'key': key, 'consumer_id': consumer.id})
        return applicable_rpms, older_rpms

    @staticmethod
    def _translate_erratum(unit, repo_ids, consumer, conduit):
        """
        Translates an erratum to a list of rpm unit keys from given repo_ids. The rpm unit keys
        reference the subset of packages referenced by the erratum that are also applicable to the
        consumer. Only those rpms which will upgrade an existing rpm on the consumer are returned

        Note that this method also checks to ensure that the RPMs are actually available to the
        consumer.

        :param unit:                   A content unit key
        :type  unit:                   dict
        :param repo_ids:               Repo ids to restrict the unit search to.
        :type  repo_ids:               list of str
        :param consumer:               A consumer.
        :type  consumer:               pulp.server.plugins.model.Consumer
        :param conduit:                provides access to relevant Pulp functionality
        :type  conduit:                pulp.plugins.conduits.profile.ProfilerConduit
        :return:                       A 2-tuple, the first element of which is a list of
                                       unit keys (dictionaries) containing info on the
                                       'translated units'. Each dictionary contains a 'unit_key' key
                                       which refers to the rpm's unit_key, and a 'type_id' key,
                                       which will always be TYPE_ID_RPM. The second element is a
                                       dictionary describing the details of the upgrade. It is the
                                       second element returned by _rpms_applicable_to_consumer(), so
                                       please see its docblock for details.
        :rtype:                        tuple
        :raises InvalidUnitsRequested: if no repository was found that contains the specified errata
        """
        unit_key = unit['unit_key']
        errata = YumProfiler._find_unit_associated_to_repos(TYPE_ID_ERRATA, unit_key, repo_ids,
                                                            conduit)
        if not errata:
            error_msg = _("Unable to find errata with unit_key [%(key)s] in bound "
                          "repos [%(repos)s] to consumer [%(consumer)s]") % \
                {'key': unit_key, 'repos': repo_ids, 'consumer': consumer.id}
            raise InvalidUnitsRequested(message=error_msg, units=unit_key)

        # Get rpm dicts from errata
        errata_rpms = YumProfiler._get_rpms_from_errata(errata)
        if _logger.isEnabledFor(DEBUG):
            msg = _("Errata <%(errata)s> refers to %(rpm_count)d updated rpms of: %(errata_rpms)s")
            msg_dict = {'errata': errata.unit_key.get('errata_id'), 'rpm_count': len(errata_rpms),
                        'errata_rpms': errata_rpms}
            _logger.debug(msg, msg_dict)
        else:
            msg = _("Errata <%(errata)s> refers to %(rpm_count)d updated rpms")
            msg_dict = {'errata': errata.unit_key.get('errata_id'), 'rpm_count': len(errata_rpms)}
            _logger.info(msg, msg_dict)

        # filter out RPMs we don't have access to (https://pulp.plan.io/issues/770).
        updated_rpms = []

        for errata_rpm in errata_rpms:
            # the dicts from _get_rpms_from_errata contain some extra fields
            # that are not in the RPM unit key.
            nvrea = dict((k, v) for k, v in errata_rpm.iteritems() if k in NVREA_KEYS)
            if YumProfiler._find_unit_associated_to_repos(TYPE_ID_RPM, nvrea,
                                                          repo_ids, conduit):
                updated_rpms.append(errata_rpm)

        applicable_rpms, upgrade_details = YumProfiler._rpms_applicable_to_consumer(consumer,
                                                                                    updated_rpms)

        if _logger.isEnabledFor(DEBUG):
            msg = _("RPMs: <%(applicable_rpms)s> found to be related to errata <%(errata)s> and "
                    "applicable to consumer <%(consumer_id)s>")
            msg_dict = {'applicable_rpms': applicable_rpms, 'errata': errata,
                        'consumer_id': consumer.id}
            _logger.debug(msg, msg_dict)
        else:
            msg = _("<%(rpm_count)d> RPMs found to be related to errata <%(errata)s> "
                    "and applicable to consumer <%(consumer_id)s>")
            msg_dict = {'rpm_count': len(applicable_rpms), 'errata': errata,
                        'consumer_id': consumer.id}
            _logger.info(msg, msg_dict)

        # Return as list of name.arch values
        ret_val = []
        for applicable_rpm in applicable_rpms:
            applicable_rpm = {"unit_key": applicable_rpm, "type_id": TYPE_ID_RPM}
            ret_val.append(applicable_rpm)
        msg = _("Translated errata <%(errata)s> to <%(ret_val)s>")
        msg_dict = {'errata': errata, 'ret_val': ret_val}
        _logger.info(msg, msg_dict)
        # Add applicable errata details to the applicability report
        errata_details = errata.metadata
        errata_details['id'] = errata.unit_key.get('errata_id')
        upgrade_details['errata_details'] = errata_details
        return ret_val, upgrade_details

    @staticmethod
    def _create_nevra(r):
        """
        A small helper method for comparing errata packages to rpm units

        The "str()" conversion may be overly defensive but I am not sure. There
        were mocks that needed this but I did not find an example during
        testing with real data.

        """
        return tuple(str(r[k]) for k in ('name', 'epoch', 'version', 'release', 'arch'))
