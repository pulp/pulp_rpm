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

import copy

from pulp_rpm.common import models


def associate(source_repo, dest_repo, import_conduit, config, units=None):
    if units is None:
        # this might use a lot of RAM since RPMs tend to have lots of metadata
        units = import_conduit.get_source_units()

    associated_units = []

    for unit in units:
        if unit.type_id in (models.PackageGroup.TYPE, models.PackageCategory.TYPE):
            new_unit = _safe_copy(unit)
            new_unit.unit_key['repo_id'] = dest_repo.id
            saved_unit = import_conduit.save_unit(new_unit)
            associated_units.append(saved_unit)
        else:
            import_conduit.associate_unit(unit)
            associated_units.append(unit)
    return associated_units


def _safe_copy(unit):
    new_unit = copy.deepcopy(unit)
    new_unit.id = None
    for key in new_unit.metadata.keys():
        if key.startswith('_'):
            del new_unit.metadata[key]
    return new_unit
