# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the License
# (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied, including the
# implied warranties of MERCHANTABILITY, NON-INFRINGEMENT, or FITNESS FOR A
# PARTICULAR PURPOSE.
# You should have received a copy of GPLv2 along with this software;
# if not, see http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt

import os
from xml.etree import ElementTree

from pulp_rpm.plugins.distributors.yum.metadata.metadata import (
    MetadataFileContext, REPO_DATA_DIR_NAME)
from pulp_rpm.yum_plugin import util


_LOG = util.getLogger(__name__)

UPDATE_INFO_XML_FILE_NAME = 'updateinfo.xml.gz'


class UpdateinfoXMLFileContext(MetadataFileContext):

    def __init__(self, working_dir):

        metadata_file_path = os.path.join(working_dir, REPO_DATA_DIR_NAME, UPDATE_INFO_XML_FILE_NAME)
        super(UpdateinfoXMLFileContext, self).__init__(metadata_file_path)

    def _write_root_tag_open(self):

        updates_element = ElementTree.Element('updates')
        bogus_element = ElementTree.SubElement(updates_element, '')

        updates_tags_string = ElementTree.tostring(updates_element, 'utf-8')
        bogus_tag_string = ElementTree.tostring(bogus_element, 'utf-8')
        opening_tag, closing_tag = updates_tags_string.split(bogus_tag_string, 1)

        self.metadata_file_handle.write(opening_tag + '\n')

        def _write_root_tag_close_closure(*args):
            self.metadata_file_handle.write(closing_tag + '\n')

        self._write_root_tag_close = _write_root_tag_close_closure

    def add_unit_metadata(self, erratum_unit):

        # XXX refactor me

        update_attributes = {'status': erratum_unit.metadata['status'],
                             'type': erratum_unit.metadata['type'],
                             'version': erratum_unit.metadata['version'],
                             'from': erratum_unit.metadata.get('from', '')}
        update_element = ElementTree.Element('update', update_attributes)

        id_element = ElementTree.SubElement(update_element, 'id')
        id_element.text = erratum_unit.unit_key['id']

        issued_attributes = {'date': erratum_unit.metadata['issued']}
        issued_element = ElementTree.SubElement(update_element, 'issued', issued_attributes)

        reboot_element = ElementTree.SubElement(update_element, 'reboot_suggested')
        reboot_element.text = str(erratum_unit.metadata['reboot_suggested'])

        for key in ('title', 'release', 'rights', 'description', 'solution',
                    'severity', 'summary', 'pushcount'):

            value = erratum_unit.metadata.get(key)

            if not value:
                continue

            sub_element = ElementTree.SubElement(update_element, key)
            sub_element.text = value

        updated = erratum_unit.metadata.get('updated')

        if updated:
            updated_attributes = {'date': updated}
            updated_element = ElementTree.SubElement(update_element, 'updated', updated_attributes)

        references_element = ElementTree.SubElement(update_element, 'references')

        for reference in erratum_unit.metadata.get('references'):

            reference_attributes = {'id': reference['id'] or '',
                                    'title': reference['title'] or '',
                                    'type': reference['type'],
                                    'href': reference['href']}
            reference_element = ElementTree.SubElement(references_element, 'reference', reference_attributes)

        for pkglist in erratum_unit.metadata.get('pkglist', []):

            pkglist_element = ElementTree.SubElement(update_element, 'pkglist')

            collection_attributes = {}
            short = pkglist.get('short')
            if short is not None:
                collection_attributes['short'] = short
            collection_element = ElementTree.SubElement(pkglist_element, 'collection', collection_attributes)

            name_element = ElementTree.SubElement(collection_element, 'name')
            name_element.text = pkglist['name']

            for package in pkglist['packages']:

                package_attributes = {'name': package['name'],
                                      'version': package['version'],
                                      'release': package['release'],
                                      'epoch': package['epoch'] or '0',
                                      'arch': package['arch'],
                                      'src': package.get('src', '')}
                package_element = ElementTree.SubElement(collection_element, 'package', package_attributes)

                filename_element = ElementTree.SubElement(package_element, 'filename')
                filename_element.text = package['filename']

                checksum_type, checksum_value = package['sum']
                sum_attributes = {'type': checksum_type}
                sum_element = ElementTree.SubElement(package_element, 'sum', sum_attributes)
                sum_element.text = checksum_value

                reboot_element = ElementTree.SubElement(package_element, 'reboot_suggested')
                reboot_element.text = str(package.get('reboot_suggested', False))

        # write the top-level XML element out to the file

        update_element_string = ElementTree.tostring(update_element, 'utf-8')

        _LOG.debug('Writing updateinfo unit metadata:\n' + update_element_string)

        self.metadata_file_handle.write(update_element_string + '\n')

