import os
from xml.etree import ElementTree

from pulp.plugins.util.metadata_writer import XmlFileContext

from pulp_rpm.plugins.distributors.yum.metadata.metadata import REPO_DATA_DIR_NAME
from pulp_rpm.yum_plugin import util


_logger = util.getLogger(__name__)

UPDATE_INFO_XML_FILE_NAME = 'updateinfo.xml.gz'


class UpdateinfoXMLFileContext(XmlFileContext):
    def __init__(self, working_dir, checksum_type=None):
        metadata_file_path = os.path.join(working_dir, REPO_DATA_DIR_NAME,
                                          UPDATE_INFO_XML_FILE_NAME)
        super(UpdateinfoXMLFileContext, self).__init__(
            metadata_file_path, 'updates', checksum_type=checksum_type)

    def add_unit_metadata(self, item):
        """
        Write the XML representation of erratum_unit to self.metadata_file_handle
        (updateinfo.xml.gx).

        :param item: The erratum unit that should be written to updateinfo.xml.
        :type  item: pulp_rpm.plugins.db.models.Errata
        """
        erratum_unit = item
        update_attributes = {'status': erratum_unit.status,
                             'type': erratum_unit.type,
                             'version': erratum_unit.version,
                             'from': erratum_unit.errata_from or ''}
        update_element = ElementTree.Element('update', update_attributes)

        id_element = ElementTree.SubElement(update_element, 'id')
        id_element.text = erratum_unit.errata_id

        issued_attributes = {'date': erratum_unit.issued}
        ElementTree.SubElement(update_element, 'issued', issued_attributes)

        reboot_element = ElementTree.SubElement(update_element, 'reboot_suggested')
        reboot_element.text = str(erratum_unit.reboot_suggested)

        # these elements are optional
        for key in ('title', 'release', 'rights', 'solution',
                    'severity', 'summary', 'pushcount'):

            value = getattr(erratum_unit, key)

            if not value:
                continue

            sub_element = ElementTree.SubElement(update_element, key)
            sub_element.text = unicode(value)

        # these elements must be present even if text is empty
        for key in ('description',):

            value = getattr(erratum_unit, key)
            if value is None:
                value = ''

            sub_element = ElementTree.SubElement(update_element, key)
            sub_element.text = unicode(value)

        updated = erratum_unit.updated

        if updated:
            updated_attributes = {'date': updated}
            ElementTree.SubElement(update_element, 'updated', updated_attributes)

        references_element = ElementTree.SubElement(update_element, 'references')

        for reference in erratum_unit.references:
            reference_attributes = {'id': reference['id'] or '',
                                    'title': reference['title'] or '',
                                    'type': reference['type'],
                                    'href': reference['href']}
            ElementTree.SubElement(references_element, 'reference', reference_attributes)

        for pkglist in erratum_unit.pkglist:

            pkglist_element = ElementTree.SubElement(update_element, 'pkglist')

            collection_attributes = {}
            short = pkglist.get('short')
            if short is not None:
                collection_attributes['short'] = short
            collection_element = ElementTree.SubElement(pkglist_element, 'collection',
                                                        collection_attributes)

            name_element = ElementTree.SubElement(collection_element, 'name')
            name_element.text = pkglist['name']

            for package in pkglist['packages']:

                package_attributes = {'name': package['name'],
                                      'version': package['version'],
                                      'release': package['release'],
                                      'epoch': package['epoch'] or '0',
                                      'arch': package['arch'],
                                      'src': package.get('src', '') or ''}
                package_element = ElementTree.SubElement(collection_element, 'package',
                                                         package_attributes)

                filename_element = ElementTree.SubElement(package_element, 'filename')
                filename_element.text = package['filename']

                checksum_tuple = package.get('sum', None)

                if checksum_tuple is not None:
                    checksum_type, checksum_value = checksum_tuple
                    sum_attributes = {'type': checksum_type}
                    sum_element = ElementTree.SubElement(package_element, 'sum', sum_attributes)
                    sum_element.text = checksum_value

                reboot_element = ElementTree.SubElement(package_element, 'reboot_suggested')
                reboot_element.text = str(package.get('reboot_suggested', False))

        # write the top-level XML element out to the file
        update_element_string = ElementTree.tostring(update_element, 'utf-8')

        _logger.debug('Writing updateinfo unit metadata:\n' + update_element_string)

        self.metadata_file_handle.write(update_element_string + '\n')
