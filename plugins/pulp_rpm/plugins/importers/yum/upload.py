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

import logging
import shutil

from xml.etree import cElementTree as ET

from pulp.plugins.model import SyncReport
from pulp.server.db.model.criteria import UnitAssociationCriteria

from pulp_rpm.common import models
from pulp_rpm.plugins.importers.yum import utils
from pulp_rpm.plugins.importers.yum.parse import rpm
from pulp_rpm.plugins.importers.yum.repomd import primary


# this is required because some of the pre-migration XML tags use the "rpm"
# namespace, which causes a parse error if that namespace isn't declared.
FAKE_XML = '<?xml version="1.0" encoding="%(encoding)s"?><faketag xmlns:rpm="http://pulpproject.org">%(xml)s</faketag>'

_LOGGER = logging.getLogger(__name__)


def upload(repo, type_id, unit_key, metadata, file_path, conduit, config):
    """
    :param repo: metadata describing the repository
    :type  repo: pulp.plugins.model.Repository

    :param type_id: type of unit being uploaded
    :type  type_id: str

    :param unit_key: identifier for the unit, specified by the user
    :type  unit_key: dict

    :param metadata: any user-specified metadata for the unit
    :type  metadata: dict

    :param file_path: path on the Pulp server's filesystem to the temporary
           location of the uploaded file; may be None in the event that a
           unit is comprised entirely of metadata and has no bits associated
    :type  file_path: str

    :param conduit: provides access to relevant Pulp functionality
    :type  conduit: pulp.plugins.conduits.unit_add.UnitAddConduit

    :param config: plugin configuration for the repository
    :type  config: pulp.plugins.config.PluginCallConfiguration

    :return: report of the details of the sync
    :rtype:  pulp.plugins.model.SyncReport
    """
    if type_id not in (models.RPM.TYPE, models.SRPM.TYPE, models.PackageGroup.TYPE,
                        models.PackageCategory.TYPE, models.Errata.TYPE):
        return _fail_report('%s is not a supported type for upload' % type_id)

    model_type = models.TYPE_MAP[type_id]

    # get metadata
    try:
        model = model_type(metadata=metadata, **unit_key)
    except TypeError:
        return _fail_report('invalid unit key or metadata')

    if type_id == models.RPM.TYPE:
        # TODO: replace this call with something that doesn't use yum
        model.metadata['repodata'] = rpm.get_package_xml(file_path)

    # not all models have a relative path
    relative_path = getattr(model, 'relative_path', '')

    # The provides and requires are not provided by the client, so extract them now
    _update_provides_requires(model)

    # both of the below operations perform IO
    try:
        # init unit
        unit = conduit.init_unit(model.TYPE, model.unit_key, model.metadata, relative_path)
        # copy file to destination
        shutil.copy(file_path, unit.storage_path)
    except IOError:
        return _fail_report('failed to copy file to destination')

    # save unit
    conduit.save_unit(unit)

    if type_id == models.Errata.TYPE:
        link_errata_to_rpms(conduit, model, unit)

    # TODO: add more info to this report?
    report = SyncReport(True, 1, 0, 0, '', {})
    return report


def _update_provides_requires(model):
    """
    Determines the provides and requires fields based on the RPM's XML snippet and updates
    the model instance.
    """

    try:
        # make a guess at the encoding
        codec = 'UTF-8'
        model.metadata['repodata']['primary'].encode(codec)
    except UnicodeEncodeError:
        # best second guess we have, and it will never fail due to the nature
        # of the encoding.
        codec = 'ISO-8859-1'
        model.metadata['repodata']['primary'].encode(codec)
    fake_xml = FAKE_XML % {'encoding': codec, 'xml': model.metadata['repodata']['primary']}
    fake_element = ET.fromstring(fake_xml.encode(codec))
    utils.strip_ns(fake_element)
    primary_element = fake_element.find('package')
    format_element = primary_element.find('format')
    provides_element = format_element.find('provides')
    requires_element = format_element.find('requires')
    model.metadata['provides'] = map(primary._process_rpm_entry_element,
                                     provides_element.findall('entry')) if provides_element else []
    model.metadata['requires'] = map(primary._process_rpm_entry_element,
                                     requires_element.findall('entry')) if requires_element else []


def link_errata_to_rpms(conduit, errata_model, errata_unit):
    """
    :param conduit: provides access to relevant Pulp functionality
    :type  conduit: pulp.plugins.conduits.unit_add.UnitAddConduit
    :param errata_model:    model object representing an errata
    :type  errata_model:    pulp_rpm.common.models.Errata
    :param errata_unit:     unit object representing an errata
    :type  errata_unit:     pulp.plugins.model.Unit
    """
    fields = list(models.RPM.UNIT_KEY_NAMES)
    fields.append('_storage_path')
    filters = {'$or': errata_model.package_unit_keys}
    for model_type in (models.RPM.TYPE, models.SRPM.TYPE):
        criteria = UnitAssociationCriteria(type_ids=[model_type], unit_fields=fields,
                                           unit_filters=filters)
        for unit in conduit.get_units(criteria):
            conduit.link_unit(errata_unit, unit, bidirectional=True)


def _fail_report(message):
    # this is the format returned by the original importer. I'm not sure if
    # anything is actually parsing it
    details = {'errors': [message]}
    return SyncReport(False, 0, 0, 0, '', details)
