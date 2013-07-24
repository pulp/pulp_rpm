# -*- coding: utf-8 -*-
#
# Copyright (c) 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

"""
Profiler plugin to support RPM Errata functionality
"""

import gettext

from pulp.plugins.conduits.mixins import UnitAssociationCriteria
from pulp.plugins.profiler import Profiler, InvalidUnitTypeForApplicability
from pulp_rpm.common.ids import TYPE_ID_PROFILER_RPM_ERRATA, TYPE_ID_ERRATA, TYPE_ID_RPM
from pulp_rpm.yum_plugin import util

_ = gettext.gettext
_LOG = util.getLogger(__name__)

class RPMErrataProfiler(Profiler):
    def __init__(self):
        super(RPMErrataProfiler, self).__init__()

    @classmethod
    def metadata(cls):
        return { 
                'id': TYPE_ID_PROFILER_RPM_ERRATA,
                'display_name': "RPM Errata Profiler",
                'types': [TYPE_ID_ERRATA],
                }


    def install_units(self, consumer, units, options, config, conduit):
        """
        Translate the specified content units to be installed.
        The specified content units are intended to be installed on the
        specified consumer.  It is requested that the profiler translate
        the units as needed.

        :param consumer: A consumer.
        :type consumer: pulp.server.plugins.model.Consumer

        :param units: A list of content units to be installed.
        :type units: list of:
            { type_id:<str>, unit_key:<dict> }

        :param options: Install options; based on unit type.
        :type options: dict

        :param config: plugin configuration
        :type config: pulp.server.plugins.config.PluginCallConfiguration

        :param conduit: provides access to relevant Pulp functionality
        :type conduit: pulp.plugins.conduits.profile.ProfilerConduit

        :return:    a list of dictionaries containing info on the 'translated units'.
                    each dictionary contains a 'name' key which refers 
                    to the rpm name associated to the errata
        :rtype [{'unit_key':{'name':name.arch}, 'type_id':'rpm'}]
        """
        return self.translate_units(units, consumer, conduit)


    # -- applicability ---------------------------------------------------------


    def calculate_applicable_units(self, unit_type_id, unit_profile, bound_repo_id, config, conduit):
        """
        Calculate and return a list of content unit ids applicable to consumers with given unit_profile.
        Applicability is calculated against all content units of given type belonging to 
        the given bound repository.

        :param unit_type_id: content unit type id
        :type unit_type_id: str

        :param unit_profile: a consumer unit profile
        :type unit_profile: list of dicts

        :param bound_repo_id: repo id of a repository to be used to calculate applicability
                              against the given consumer profile
        :type bound_repo_id: str

        :param config: plugin configuration
        :type config: pulp.server.plugins.config.PluginCallConfiguration

        :param conduit: provides access to relevant Pulp functionality
        :type conduit: pulp.plugins.conduits.profile.ProfilerConduit

        :return: a list of content unit ids
        :rtype: list of str
        """
        
        if unit_type_id != TYPE_ID_ERRATA:
            error_msg = _("calculate_applicable_units invoked with type_id [%s], expected [%s]") % (unit_type_id, TYPE_ID_ERRATA)
            _LOG.error(error_msg)
            raise InvalidUnitTypeForApplicability(unit_type_id, error_msg)

        # Get all rpms associated with given repository
        additional_unit_fields = ['pkglist']
        units = conduit.get_repo_units(bound_repo_id, unit_type_id, additional_unit_fields)

        # Form a lookup table for consumer unit profile so that package lookups are constant time
        profile_lookup_table = self.form_lookup_table(unit_profile)

        applicable_unit_ids = []
        # Check applicability for each unit
        for unit in units:
            applicable = self.is_applicable(unit, profile_lookup_table)
            if applicable:
                applicable_unit_ids.append(unit['unit_id'])

        return applicable_unit_ids


    # -- Below are helper methods not part of the Profiler interface ----


    def is_applicable(self, errata, profile_lookup_table):
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
        errata_rpms = []
        if not errata.has_key('pkglist'):
            _LOG.warning("metadata for errata <%s> lacks a 'pkglist'" % (errata['unit_key']['id']))
            return False
        for pkgs in errata['pkglist']:
            for rpm in pkgs['packages']:
                errata_rpms.append(rpm)

        _LOG.debug("Errata <%s> refers to %s rpms of: %s" % (errata['unit_key']['id'], len(errata_rpms), errata_rpms))

        # Check if any rpm from errata is applicable to the consumer
        for errata_rpm in errata_rpms:
            key = "%s %s" % (errata_rpm['name'], errata_rpm['arch'])
            if profile_lookup_table.has_key(key):
                installed_rpm = profile_lookup_table[key]
                _LOG.debug("Found a match of rpm <%s> installed on consumer" % key)
                is_newer = util.is_rpm_newer(errata_rpm, installed_rpm)
                if is_newer:
                    _LOG.debug("%s is newer than %s" % (errata_rpm, installed_rpm))
                    return True
            else:
                _LOG.debug("rpm %s was not found in the consumer profile" % key)

        # Return false if none of the errata rpms are applicable    
        return False


    def form_lookup_table(self, rpms):
        lookup = {}
        for r in rpms:
            # Since only one name.arch is allowed to be installed on a machine,
            # we will use "name arch" as a key in the lookup table
            key = "%s %s" % (r['name'], r['arch'])
            lookup[key] = r
        return lookup


    def form_lookup_key(self, item):
        #
        # This key needs to avoid usage of a ".", since it may be stored in mongo
        # when the upgrade_details are returned.
        #
        return "%s %s" % (item['name'], item['arch'])


    def translate_units(self, units, consumer, conduit):
        """
        Will translate passed in errata unit_keys to a list of dictionaries
        containing the associated RPM names applicable to the consumer.

        :param units: A list of content units to be uninstalled.
        :type units: list of:
            { type_id:<str>, unit_key:<dict> }

        :param consumer: A consumer.
        :type consumer: pulp.server.plugins.model.Consumer

        :param conduit: provides access to relevant Pulp functionality
        :type conduit: pulp.plugins.conduits.profile.ProfilerConduit

        :return:    a list of dictionaries containing info on the 'translated units'.
                    each dictionary contains a 'name' key which refers 
                    to the rpm name associated to the errata
        :rtype [{'unit_key':{'name':name.arch}, 'type_id':'rpm'}]
        """
        translated_units = []
        for unit in units:
            values, upgrade_details = self.translate(unit, conduit.get_bindings(consumer.id), consumer, conduit)
            if values:
                translated_units.extend(values)
        return translated_units


    def translate(self, unit, repo_ids, consumer, conduit):
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
        errata = self.find_unit_associated_to_repos(TYPE_ID_ERRATA, unit_key, repo_ids, conduit)
        if not errata:
            error_msg = _("Unable to find errata with unit_key [%s] in bound repos [%s] to consumer [%s]") % \
                    (unit_key, repo_ids, consumer.id)
            _LOG.info(error_msg)
            return None, None
        else:
            updated_rpms = self.get_rpms_from_errata(errata)
            _LOG.info("Errata <%s> refers to %s updated rpms of: %s" % (errata.unit_key['id'], len(updated_rpms), updated_rpms))
            applicable_rpms, upgrade_details = self.rpms_applicable_to_consumer(consumer, updated_rpms)
            if applicable_rpms:
                _LOG.info("Rpms: <%s> were found to be related to errata <%s> and applicable to consumer <%s>" % (applicable_rpms, errata, consumer.id))
            # Return as list of name.arch values
            ret_val = []
            for ar in applicable_rpms:
                pkg_name = "%s-%s:%s-%s.%s" % (ar["name"], ar["epoch"], ar["version"], ar["release"], ar["arch"])
                data = {"unit_key":{"name":pkg_name}, "type_id":TYPE_ID_RPM}
                ret_val.append(data)
            _LOG.info("Translated errata <%s> to <%s>" % (errata, ret_val))
            # Add applicable errata details to the applicability report
            errata_details = errata.metadata
            errata_details['id'] = errata.unit_key['id']
            upgrade_details['errata_details'] = errata_details
            return ret_val, upgrade_details


    def get_rpms_from_errata(self, errata):
        """
        :param errata
        :type errata: pulp.plugins.model.Unit

        :return list of rpms, which are each a dict of nevra info
        :rtype: [{}]
        """
        rpms = []
        if not errata.metadata.has_key("pkglist"):
            _LOG.warning("metadata for errata <%s> lacks a 'pkglist'" % (errata.unit_key['id']))
            return rpms
        for pkgs in errata.metadata['pkglist']:
            for rpm in pkgs["packages"]:
                rpms.append(rpm)
        return rpms


    def rpms_applicable_to_consumer(self, consumer, errata_rpms):
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
            _LOG.warn("Consumer [%s] is missing profile information for [%s], found profiles are: %s" % \
                    (consumer.id, TYPE_ID_RPM, consumer.profiles.keys()))
            return applicable_rpms, older_rpms
        lookup = self.form_lookup_table(consumer.profiles[TYPE_ID_RPM])
        for errata_rpm in errata_rpms:
            key = self.form_lookup_key(errata_rpm)
            if lookup.has_key(key):
                installed_rpm = lookup[key]
                is_newer = util.is_rpm_newer(errata_rpm, installed_rpm)
                _LOG.debug("Found a match of rpm <%s> installed on consumer, is %s newer than %s, %s" % (key, errata_rpm, installed_rpm, is_newer))
                if is_newer:
                    applicable_rpms.append(errata_rpm)
                    older_rpms[key] = {"installed":installed_rpm, "available":errata_rpm}
            else:
                _LOG.debug("rpm %s was not found in consumer profile of %s" % (key, consumer.id))
        return applicable_rpms, older_rpms

    def find_unit_associated_to_repos(self, unit_type, unit_key, repo_ids, conduit):
        criteria = UnitAssociationCriteria(type_ids=[unit_type], unit_filters=unit_key)
        return self.find_unit_associated_to_repos_by_criteria(criteria, repo_ids, conduit)

    def find_unit_associated_to_repos_by_criteria(self, criteria, repo_ids, conduit):
        for repo_id in repo_ids:
            result = conduit.get_units(repo_id, criteria)
            _LOG.debug("Found %s items when searching in repo <%s> for <%s>" % (len(result), repo_id, criteria))
            if result:
                return result[0]
        return None
