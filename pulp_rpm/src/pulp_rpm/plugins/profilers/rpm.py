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

from pulp.plugins.profiler import Profiler, InvalidUnitTypeForApplicability
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

    def update_profile(self, consumer, profile, config, conduit):
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

        :param consumer: A consumer.
        :type  consumer: pulp.plugins.model.Consumer
        :param profile:  The reported profile.
        :type  profile:  list
        :param config:   plugin configuration
        :type  config:   pulp.plugins.config.PluginCallConfiguration
        :param conduit:  provides access to relevant Pulp functionality
        :type  conduit:  pulp.plugins.conduits.profiler.ProfilerConduit
        :return:         The sorted profile.
        :rtype:          list
        """
        profile = [
            ((p['name'], p['epoch'], p['version'], p['release'], p['arch'], p['vendor']), p) \
            for p in profile]
        profile.sort()
        return [p[1] for p in profile]

    # -- applicability ---------------------------------------------------------

    def calculate_applicable_units(self, unit_type_id, unit_profile, bound_repo_id, config, conduit):
        """
        Calculate and return a list of content unit ids applicable to consumers with given unit_profile.
        Applicability is calculated against all content units of given type belonging to the given 
        bound repository.

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
        
        if unit_type_id != TYPE_ID_RPM:
            error_msg = _("calculate_applicable_units invoked with type_id [%s], expected [%s]") % (unit_type_id, TYPE_ID_RPM)
            _LOG.error(error_msg)
            raise InvalidUnitTypeForApplicability(unit_type_id, error_msg)

        # Get all rpms associated with given repository
        units = conduit.get_repo_units(bound_repo_id, unit_type_id)

        # Form a lookup table for consumer unit profile so that package lookups are constant time
        profile_lookup_table = self.form_lookup_table(unit_profile)

        applicable_unit_ids = []
        # Check applicability for each unit
        for unit in units:
            applicable = self.is_applicable(unit['unit_key'], profile_lookup_table)
            if applicable:
                applicable_unit_ids.append(unit['unit_id'])

        return applicable_unit_ids


    # -- Below are helper methods not part of the Profiler interface ----


    def is_applicable(self, rpm, profile_lookup_table):
        """
        Checks whether given rpm upgrades an rpm on the consumer.

        :param rpm: Values of rpm's unit_key
        :type rpm: dict

        :param profile_lookup_table: lookup table of consumer profile keyed by name.arch 
        :type profile_lookup_table: dict

        :return: true if applicable, false otherwise
        :rtype: boolean
        """
        applicable = False
        if not rpm or not profile_lookup_table: 
            return applicable

        key = "%s %s" % (rpm['name'], rpm['arch'])
        
        if profile_lookup_table.has_key(key):
            installed_rpm = profile_lookup_table[key]
            _LOG.debug("Found a match of rpm <%s> installed on consumer" % key)
            # If an rpm is found, check if it is older than the available rpm
            is_newer = util.is_rpm_newer(rpm, installed_rpm)
            if is_newer:
                _LOG.debug("%s is newer than %s" % (rpm, installed_rpm))
                applicable = True

        return applicable


    def form_lookup_table(self, rpms):
        lookup = {}
        for r in rpms:
            # Since only one name.arch is allowed to be installed on a machine,
            # we will use name.arch as a key in the lookup table
            key = "%s %s" % (r['name'], r['arch'])
            lookup[key] = r
        return lookup

