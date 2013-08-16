# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

from gettext import gettext as _

from pulp.plugins.conduits.mixins import UnitAssociationCriteria
from pulp.plugins.model import Unit
from pulp.plugins.profiler import Profiler

from pulp_rpm.common.ids import TYPE_ID_ERRATA, TYPE_ID_RPM
from pulp_rpm.yum_plugin import util


logger = util.getLogger(__name__)


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
        return {
            TYPE_ID_RPM: YumProfiler._calculate_applicable_units(TYPE_ID_RPM, unit_profile,
                                                                 bound_repo_id, config, conduit),
            TYPE_ID_ERRATA: YumProfiler._calculate_applicable_units(TYPE_ID_ERRATA, unit_profile,
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
        """
        translated_units = []
        for unit in units:
            if unit['type_id'] == TYPE_ID_RPM:
                translated_units.append(unit)
            elif unit['type_id'] == TYPE_ID_ERRATA:
                values, upgrade_details = YumProfiler._translate_erratum(
                    unit, conduit.get_bindings(consumer.id), consumer, conduit)
                if values:
                    translated_units.extend(values)
        return translated_units

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
                ((p['name'], p['epoch'], p['version'], p['release'], p['arch'], p['vendor']), p) \
                for p in profile]
            profile.sort()
            return [p[1] for p in profile]
        else:
            return profile

    @staticmethod
    def _calculate_applicable_units(content_type, unit_profile, bound_repo_id, config, conduit):
        """
        Calculate and return a list of unit ids of given conten_type applicable to consumers with given
        unit_profile. Applicability is calculated against all units belonging to the given bound
        repository.

        :param content_type:  The content type id that the profile represents
        :type  content_type:  basestring
        :param unit_profile:  a consumer unit profile
        :type  unit_profile:  list of dicts
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

        # Form a lookup table for consumer unit profile so that package lookups are constant time
        profile_lookup_table = YumProfiler._form_lookup_table(unit_profile)

        applicable_unit_ids = []
        # Check applicability for each unit
        for unit in units:
            if content_type == TYPE_ID_RPM:
                applicable = YumProfiler._is_rpm_applicable(unit['unit_key'], profile_lookup_table)
            elif content_type == TYPE_ID_ERRATA:
                applicable = YumProfiler._is_errata_applicable(unit, profile_lookup_table)
            else:
                applicable = False

            if applicable:
                applicable_unit_ids.append(unit['unit_id'])

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
        method) to the full unit key for each RPM.

        :param rpms: A list of RPM unit keys
        :type  rpms: list
        :return:     A dictionary mapping the lookup keys to the RPM unit keys
        :rtype:      dict
        """
        lookup = {}
        for rpm in rpms:
            # Since only one name.arch is allowed to be installed on a machine,
            # we will use "name arch" as a key in the lookup table
            key = YumProfiler._form_lookup_key(rpm)
            lookup[key] = rpm
        return lookup

    @staticmethod
    def _get_rpms_from_errata(errata):
        """
        Return a list of RPMs that are referenced by an errata's pkglist

        :param errata: The errata we wish to query for RPMs it contains
        :type errata:  pulp.plugins.model.Unit
        :return:       list of rpms, which are each a dict of nevra info
        :rtype:        list
        """
        rpms = []
        if not errata.metadata.has_key("pkglist"):
            logger.warning("metadata for errata <%s> lacks a 'pkglist'" % (errata.unit_key['id']))
            return rpms
        for pkgs in errata.metadata['pkglist']:
            for rpm in pkgs["packages"]:
                rpms.append(rpm)
        return rpms

    @staticmethod
    def _is_errata_applicable(errata, profile_lookup_table):
        """
        Checks whether given errata is applicable to the consumer.

        :param errata: Errata for which the applicability is being checked
        :type errata: dict

        :param profile_lookup_table: lookup table of consumer profile keyed by name.arch 
        :type profile_lookup_table: dict

        :return: true if applicable, false otherwise
        :rtype: boolean
        """
        # Get rpms from errata
        # Due to https://bugzilla.redhat.com/show_bug.cgi?id=991500, the errata we get here is not a
        # Unit, but is a dict. This dictionary has "flattened" the metadata out.
        # _get_rpms_from_errata needs a Unit, so we'll need to reconstruct a unit out of our dict.
        # In order to do that, we need to "unflatten" the metadata portion of the unit.
        metadata = dict([(key, value) for key, value in errata.iteritems() if key != 'unit_key'])
        errata_rpms = YumProfiler._get_rpms_from_errata(
            Unit(TYPE_ID_ERRATA, errata['unit_key'], metadata, None))

        # Check if any rpm from errata is applicable to the consumer
        for errata_rpm in errata_rpms:
            if YumProfiler._is_rpm_applicable(errata_rpm, profile_lookup_table):
                return True

        # Return false if none of the errata rpms are applicable    
        return False

    @staticmethod
    def _is_rpm_applicable(rpm_unit_key, profile_lookup_table):
        """
        Checks whether given rpm upgrades an rpm on the consumer.

        :param rpm_unit_key:         An rpm's unit_key
        :type  rpm_unit_key:         dict
        :param profile_lookup_table: lookup table of consumer profile keyed by name.arch 
        :type  profile_lookup_table: dict
        :return:                     true if applicable, false otherwise
        :rtype:                      boolean
        """
        if not rpm_unit_key or not profile_lookup_table:
            return False

        key = YumProfiler._form_lookup_key(rpm_unit_key)

        if profile_lookup_table.has_key(key):
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
        if not consumer.profiles.has_key(TYPE_ID_RPM):
            logger.warn("Consumer [%s] is missing profile information for [%s], found profiles are: %s" % \
                    (consumer.id, TYPE_ID_RPM, consumer.profiles.keys()))
            return applicable_rpms, older_rpms
        lookup = YumProfiler._form_lookup_table(consumer.profiles[TYPE_ID_RPM])
        for errata_rpm in errata_rpms:
            key = YumProfiler._form_lookup_key(errata_rpm)
            if lookup.has_key(key):
                installed_rpm = lookup[key]
                is_newer = util.is_rpm_newer(errata_rpm, installed_rpm)
                logger.debug("Found a match of rpm <%s> installed on consumer, is %s newer than %s, %s" % (key, errata_rpm, installed_rpm, is_newer))
                if is_newer:
                    applicable_rpms.append(errata_rpm)
                    older_rpms[key] = {"installed":installed_rpm, "available":errata_rpm}
            else:
                logger.debug("rpm %s was not found in consumer profile of %s" % (key, consumer.id))
        return applicable_rpms, older_rpms

    @staticmethod
    def _translate_erratum(unit, repo_ids, consumer, conduit):
        """
        Translates an erratum to a list of rpm units from given repo_ids.
        The rpm units refer to the upgraded packages referenced by the erratum
        only those rpms which will upgrade an existing rpm on the consumer are returned

        :param unit: A content unit key
        :type unit: dict

        :param repo_ids: Repo ids to restrict the unit search to.
        :type repo_ids: list of str

        :param consumer: A consumer.
        :type consumer: pulp.server.plugins.model.Consumer

        :param conduit: provides access to relevant Pulp functionality
        :type conduit: pulp.plugins.conduits.profile.ProfilerConduit

        :return:    a tuple consisting of
                        list of dictionaries containing info on the 'translated units'.
                        each dictionary contains a 'name' key which refers 
                        to the rpm name associated to the errata

                        dictionary containing information on what existing rpms will be upgraded

        :rtype ([{'unit_key':{'name':name.arch}, 'type_id':'rpm'}], {'name arch':{'available':{}, 'installed':{}}   })
        """
        unit_key = unit['unit_key']
        errata = YumProfiler._find_unit_associated_to_repos(TYPE_ID_ERRATA, unit_key, repo_ids, conduit)
        if not errata:
            error_msg = _("Unable to find errata with unit_key [%s] in bound repos [%s] to consumer [%s]") % \
                    (unit_key, repo_ids, consumer.id)
            logger.info(error_msg)
            return None, None

        updated_rpms = YumProfiler._get_rpms_from_errata(errata)
        logger.info("Errata <%s> refers to %s updated rpms of: %s" % (errata.unit_key['id'], len(updated_rpms), updated_rpms))
        applicable_rpms, upgrade_details = YumProfiler._rpms_applicable_to_consumer(consumer, updated_rpms)
        if applicable_rpms:
            logger.info("Rpms: <%s> were found to be related to errata <%s> and applicable to consumer <%s>" % (applicable_rpms, errata, consumer.id))
        # Return as list of name.arch values
        ret_val = []
        for ar in applicable_rpms:
            pkg_name = "%s-%s:%s-%s.%s" % (ar["name"], ar["epoch"], ar["version"], ar["release"], ar["arch"])
            data = {"unit_key":{"name":pkg_name}, "type_id":TYPE_ID_RPM}
            ret_val.append(data)
        logger.info("Translated errata <%s> to <%s>" % (errata, ret_val))
        # Add applicable errata details to the applicability report
        errata_details = errata.metadata
        errata_details['id'] = errata.unit_key['id']
        upgrade_details['errata_details'] = errata_details
        return ret_val, upgrade_details
