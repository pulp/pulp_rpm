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
Profiler plugin to support RPM Package functionality
"""
import gettext

from pulp.plugins.model import ApplicabilityReport
from pulp.plugins.profiler import Profiler, InvalidUnitsRequested
from pulp.plugins.conduits.mixins import UnitAssociationCriteria
from pulp_rpm.common.ids import TYPE_ID_PROFILER_RPM_PKG, TYPE_ID_RPM
from pulp_rpm.yum_plugin import util

_ = gettext.gettext
_LOG = util.getLogger(__name__)

class RPMPkgProfiler(Profiler):
    def __init__(self):
        super(RPMPkgProfiler, self).__init__()

    @classmethod
    def metadata(cls):
        return { 
                'id': TYPE_ID_PROFILER_RPM_PKG,
                'display_name': "RPM Package Profiler",
                'types': [TYPE_ID_RPM],
                }

    # -- applicability ---------------------------------------------------------


    def units_applicable(self, consumer, repo_ids, unit_type_id, unit_keys, config, conduit):
        """
        Determine whether content units with given unit_keys and unit_type_id 
        are applicable to the specified consumer with given repo_ids.

        :param consumer: A consumer.
        :type consumer: pulp.server.plugins.model.Consumer
        
        :param repo_ids: Repo ids to restrict the applicability search to.
        :type repo_ids: list of str

        :param unit_type_id: Common type id of all given unit keys
        :type unit_type_id: str

        :param unit_keys: list of unit keys to identify units 
        :type unit_keys: list of dict

        :param config: plugin configuration
        :type config: pulp.server.plugins.config.PluginCallConfiguration

        :param conduit: provides access to relevant Pulp functionality
        :type conduit: pulp.plugins.conduits.profile.ProfilerConduit

        :return: A list of applicability reports.
        :rtype: List of pulp.plugins.model.ApplicabilityReport
        """
        
        if unit_type_id != TYPE_ID_RPM:
            error_msg = _("units_applicable invoked with type_id [%s], expected [%s]") % (unit_type_id, TYPE_ID_RPM)
            _LOG.error(error_msg)
            raise InvalidUnitsRequested(unit_keys, error_msg)

        applicability_reports = []

        # If repo_ids or units are empty lists, no need to check for applicability.
        if not repo_ids or not unit_keys:
            return applicability_reports

        # For each unit 
        for unit_key in unit_keys:
            applicable, upgrade_details = self.find_applicable(unit_key, consumer, repo_ids, conduit)
            if applicable:
                details = upgrade_details
                summary = {}
                applicability_reports.append(ApplicabilityReport(summary, details))

        return applicability_reports


    # -- Below are helper methods not part of the Profiler interface ----


    def find_applicable(self, unit_key, consumer, repo_ids, conduit):
        """
        Find whether a package with given unit_key in repo_ids is applicable
        to the consumer.

        :param unit: A content unit key
        :type unit: dict

        :param consumer: A consumer.
        :type consumer: pulp.server.plugins.model.Consumer

        :param repo_ids: Repo ids to restrict the applicability search to.
        :type repo_ids: list

        :param conduit: provides access to relevant Pulp functionality
        :type conduit: pulp.plugins.conduits.profile.ProfilerConduit

        :return:    a tuple consisting of applicable flag and upgrade details

        :rtype: (applicable_flag, {'name arch':{'available':{}, 'installed':{}}})
        """
        applicable = False
        upgrade_details = {}

        # First check whether rpm exists in given repos 
        rpm = self.find_rpm_in_repos(unit_key, repo_ids, conduit)
        if not rpm:
            error_msg = _("Unable to find package with unit_key [%s] in repos [%s] to consumer [%s]") % \
                    (unit_key, repo_ids, consumer.id)
            _LOG.debug(error_msg)
        else:
            # If rpm exists, find whether it upgrades a consumer profile unit.
            applicable, upgrade_details = self.rpm_applicable_to_consumer(consumer, rpm.unit_key)
            if applicable:
                _LOG.debug("Rpm: <%s> was found to be applicable to consumer <%s>" % (rpm, consumer.id))

        return applicable, upgrade_details


    def find_rpm_in_repos(self, unit_key, repo_ids, conduit):
        """
        Return details of an rpm, if it exists in given repos. 
        Returns none if rpm doesn't exist.
        """
        criteria = UnitAssociationCriteria(type_ids=[TYPE_ID_RPM], unit_filters=unit_key)
        for repo_id in repo_ids:
            result = conduit.get_units(repo_id, criteria)
            _LOG.debug("Found %s items when searching in repo <%s> for <%s>" % (len(result), repo_id, criteria))
            if result:
                return result[0]
        return None


    def rpm_applicable_to_consumer(self, consumer, rpm):
        """
        Checks whether given rpm upgrades an rpm on the consumer.

        :param consumer: a profiled consumer
        :type consumer: pulp.server.plugins.model.Consumer

        :param rpm: a package rpm
        :type rpm: dict

        :return:  a tuple consisting of applicable flag and upgrade details
        :rtype: (applicable_flag, {'name arch':{'available':{}, 'installed':{}}})
        """
        applicable = False
        older_rpm = {}

        if not consumer.profiles.has_key(TYPE_ID_RPM):
            _LOG.warn("Consumer [%s] is missing profile information for [%s], found profiles are: %s" % \
                    (consumer.id, TYPE_ID_RPM, consumer.profiles.keys()))
            return applicable, older_rpm

        # Form a lookup table from consumer profile
        lookup = self.form_lookup_table(consumer.profiles[TYPE_ID_RPM])
        key = self.form_lookup_key(rpm)
        
        if lookup.has_key(key):
            installed_rpm = lookup[key]
            # If an rpm is found, check if it is older than the available rpm
            is_newer = util.is_rpm_newer(rpm, installed_rpm)
            _LOG.debug("Found a match of rpm <%s> installed on consumer, is %s newer than %s, %s" % (key, rpm, installed_rpm, is_newer))
            if is_newer:
                applicable = True
                older_rpm[key] = {"installed":installed_rpm, "available":rpm}
        else:
            _LOG.debug("rpm %s was not found in consumer profile of %s" % (key, consumer.id))

        return applicable, older_rpm


    def form_lookup_table(self, rpms):
        lookup = {}
        for r in rpms:
            # Assuming that only 1 name.arch is allowed to be installed on a machine
            # therefore we will handle only one name.arch in the lookup table
            key = self.form_lookup_key(r)
            lookup[key] = r
        return lookup


    def form_lookup_key(self, item):
        #
        # This key needs to avoid usage of a "." since it may be stored in mongo
        # when the upgrade_details are returned for an ApplicableReport
        #
        return "%s %s" % (item['name'], item['arch'])


