# -*- coding: utf-8 -*-
#
# Copyright © 2012 Red Hat, Inc.
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
from pulp_rpm.common.ids import TYPE_ID_PROFILER_RPM_PKG, TYPE_ID_RPM, UNIT_KEY_RPM
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


    def unit_applicable(self, consumer, repo_ids, unit, config, conduit):
        """
        Determine whether the content unit is applicable to
        the specified consumer. 

        @param consumer: A consumer.
        @type consumer: L{pulp.server.plugins.model.Consumer}
        
        @param repo_ids: Repo ids to confine the applicability search to.
        @type repo_ids: list

        @param unit: A content unit: { type_id:<str>, unit_key:<dict> }
        @type unit: dict

        @param config: plugin configuration
        @type config: L{pulp.server.plugins.config.PluginCallConfiguration}

        @param conduit: provides access to relevant Pulp functionality
        @type conduit: L{pulp.plugins.conduits.profile.ProfilerConduit}

        @return: An applicability report.
        @rtype: L{pulp.plugins.model.ApplicabilityReport}
        """
        applicable = False
        applicable_rpm, upgrade_details = self.find_applicable(unit, consumer, repo_ids, conduit)
        if applicable_rpm:
            summary = {}
            details = {"applicable_rpm": applicable_rpm, "upgrade_details":upgrade_details}
            return ApplicabilityReport(unit, True, summary, details)
        return None

    # -- Below are helper methods not part of the Profiler interface ----

    def find_applicable(self, unit, consumer, repo_ids, conduit):
        """
        The rpm units refer to the upgraded packages. Only those rpms which will 
        upgrade an existing rpm on the consumer are returned

        @param unit: A content unit: { type_id:<str>, unit_key:<dict> }
        @type unit: dict

        @param consumer: A consumer.
        @type consumer: L{pulp.server.plugins.model.Consumer}

        @param repo_ids: Repo ids to confine the applicability search to.
        @type repo_ids: list

        @param conduit: provides access to relevant Pulp functionality
        @type conduit: L{pulp.plugins.conduits.profile.ProfilerConduit}

        @return:    a tuple consisting of a list of dictionaries. 
                    Each dictionary contains a 'name' key which refers to the rpm name

                    dictionary containing information on what existing rpms will be upgraded

        @rtype ([{'unit_key':{'name':name.arch}, 'type_id':'rpm'}], {'name arch':{'available':{}, 'installed':{}}   })
        """
        data = {}
        upgrade_details = {}
        if unit["type_id"] != TYPE_ID_RPM:
            error_msg = _("unit_applicable invoked with type_id [%s], expected [%s]") % (unit["type_id"], TYPE_ID_RPM)
            _LOG.error(error_msg)
            raise InvalidUnitsRequested([unit], error_msg)

        if repo_ids is None:
            repo_ids = conduit.get_bindings(consumer.id)

        rpm = self.find_unit_in_repos(unit["type_id"], unit["unit_key"], repo_ids, conduit)
        if not rpm:
            msg = _("Unable to find package with unit_key [%s] in repos [%s] to consumer [%s]") % \
                    (unit["unit_key"], repo_ids, consumer.id)
            _LOG.info(error_msg)
        else:
            applicable_rpm, upgrade_details = self.rpm_applicable_to_consumer(consumer, rpm.unit_key)
            if applicable_rpm:
                _LOG.info("Rpm: <%s> was found to be applicable to consumer <%s>" % (applicable_rpm, consumer.id))
                pkg_name = "%s.%s" % (applicable_rpm["name"], applicable_rpm["arch"])
                data = {"unit_key":{"name":pkg_name}, "type_id":TYPE_ID_RPM}
        return data, upgrade_details


    def find_unit_in_repos(self, unit_type, unit_key, repo_ids, conduit):
        criteria = UnitAssociationCriteria(type_ids=[unit_type], unit_filters=unit_key)
        return self.find_unit_in_repos_by_criteria(criteria, repo_ids, conduit)


    def find_unit_in_repos_by_criteria(self, criteria, repo_ids, conduit):
        for repo_id in repo_ids:
            result = conduit.get_units(repo_id, criteria)
            _LOG.info("Found %s items when searching in repo <%s> for <%s>" % (len(result), repo_id, criteria))
            if result:
                return result[0]
        return None


    def rpm_applicable_to_consumer(self, consumer, rpm):
        """
        @param consumer:
        @type consumer: L{pulp.server.plugins.model.Consumer}

        @param rpm: 
        @type rpm: dicts

        @return:    tuple, first entry is a dictionary of applicable 
                    rpm, second entry dictionary with more info 
                    of which installed rpm will be upgraded by what rpm

                    Note:
                    This method does not take into consideration if the consumer
                    is bound to the repo containing the RPM.
        @rtype: ({}, {})
        """
        applicable_rpm = None
        older_rpms = {}
        if not consumer.profiles.has_key(TYPE_ID_RPM):
            _LOG.warn("Consumer [%s] is missing profile information for [%s], found profiles are: %s" % \
                    (consumer.id, TYPE_ID_RPM, consumer.profiles.keys()))
            return applicable_rpm, older_rpms
        lookup = self.form_lookup_table(consumer.profiles[TYPE_ID_RPM])

        key = self.form_lookup_key(rpm)
        if lookup.has_key(key):
            installed_rpm = lookup[key]
            is_newer = util.is_rpm_newer(rpm, installed_rpm)
            _LOG.info("Found a match of rpm <%s> installed on consumer, is %s newer than %s, %s" % (key, rpm, installed_rpm, is_newer))
            if is_newer:
                applicable_rpm = rpm
                older_rpms[key] = {"installed":installed_rpm, "available":rpm}
        else:
            _LOG.info("rpm %s was not found in consumer profile of %s" % (key, consumer.id))
        return applicable_rpm, older_rpms

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

    def form_rpm_unit_key(self, rpm_dict):
        unit_key = {}
        for key in UNIT_KEY_RPM:
            unit_key[key] = rpm_dict[key]
        return unit_key

