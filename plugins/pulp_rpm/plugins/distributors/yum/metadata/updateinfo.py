import os

from pulp.plugins.util.metadata_writer import FastForwardXmlFileContext
from pulp.plugins.util.saxwriter import XMLWriter
from pulp.server.exceptions import PulpCodedException

from pulp_rpm.plugins import error_codes
from pulp_rpm.plugins.distributors.yum.metadata.metadata import REPO_DATA_DIR_NAME
from pulp_rpm.yum_plugin import util

_logger = util.getLogger(__name__)

UPDATE_INFO_XML_FILE_NAME = 'updateinfo.xml.gz'


class UpdateinfoXMLFileContext(FastForwardXmlFileContext):
    def __init__(self, working_dir, checksum_type=None, conduit=None,
                 updateinfo_checksum_type=None):
        """
        Creates and writes updateinfo XML data.

        :param working_dir: The working directory for the request
        :type working_dir:  basestring
        :param checksum_type: The type of checksum to be used
        :type checksum_type:  basestring
        :param conduit: A conduit to use
        :type conduit:  pulp.plugins.conduits.repo_publish.RepoPublishConduit
        :param updateinfo_checksum_type: The type of checksum to be used in the package list
        :type updateinfo_checksum_type:  basestring
        """
        metadata_file_path = os.path.join(working_dir, REPO_DATA_DIR_NAME,
                                          UPDATE_INFO_XML_FILE_NAME)
        self.conduit = conduit
        root_tag, search_tag = 'updates', None
        super(UpdateinfoXMLFileContext, self).__init__(
            metadata_file_path, root_tag, search_tag, checksum_type=checksum_type)
        self.updateinfo_checksum_type = updateinfo_checksum_type
        self.optional_errata_fields = ('title', 'release', 'rights', 'solution', 'severity',
                                       'summary', 'pushcount')
        self.mandatory_errata_fields = ('description',)

    def _open_metadata_file_handle(self):
        """
        Open the metadata file handle, creating any missing parent directories.
        If the file already exists, this will overwrite it.
        """
        super(UpdateinfoXMLFileContext, self)._open_metadata_file_handle()
        self.xml_generator = XMLWriter(self.metadata_file_handle, short_empty_elements=True)

    def _get_package_checksum_tuple(self, package):
        """
        Decide which checksum to publish for the given package in the erratum package list.
        If updateinfo_checksum_type is requested explicitly, the checksum of this type will be
        published.
        If no checksum_type is requested, the checksum of the distributor checksum type
        will be published, if available. Otherwise the longest one will be chosen.

        Handle two possible ways of specifying the checksum in the erratum package list:
        - in the `sum` package field as a list of alternating checksum types and values,
          e.g. ['type1', 'checksum1', 'type2', 'checksum2']
        - in the `type` and `sums` package fields. It is only the case when the erratum was uploaded
          via pulp-admin. Only one type of the checksum could be specified this way.

        :param package: package from the erratum package list
        :type  package: dict
        :return: checksum type and value to publish. An empty tuple is returned if there is
                 no checksum available.
        :rtype: tuple
        :raises PulpCodedException: if updateinfo_checksum_type is not available
        """
        package_checksum_tuple = ()
        dist_checksum_type = self.checksum_type
        package_checksums = package.get('sum') or []
        if package.get('type'):
            package_checksums += [package['type'], package.get('sums')]

        for checksum_type in (self.updateinfo_checksum_type, dist_checksum_type):
            try:
                checksum_index = package_checksums.index(checksum_type) + 1
            except (ValueError, IndexError):
                # raise exception if updateinfo_checksum_type is unavailable
                if self.updateinfo_checksum_type and \
                   checksum_type == self.updateinfo_checksum_type:
                    raise PulpCodedException(error_codes.RPM1012,
                                             checksumtype=self.updateinfo_checksum_type)
                continue
            else:
                checksum_value = package_checksums[checksum_index]
                package_checksum_tuple = (checksum_type, checksum_value)
                break
        else:
            if package_checksums:
                # choose the longest(the best?) checksum available
                checksum_value = max(package_checksums[1::2], key=len)
                checksum_type_index = package_checksums.index(checksum_value) - 1
                checksum_type = package_checksums[checksum_type_index]
                package_checksum_tuple = (checksum_type, checksum_value)

        return package_checksum_tuple

    def add_unit_metadata(self, item, filtered_pkglist):
        """
        Write the XML representation of erratum_unit to self.metadata_file_handle
        (updateinfo.xml.gx).

        :param item: The erratum unit that should be written to updateinfo.xml.
        :type  item: pulp_rpm.plugins.db.models.Errata
        :param filtered_pkglist: The pkglist containing unique non-empty collections
                                with packages which are present in repo.
        :type filtered_pkglist: dict
        """
        erratum_unit = item
        update_attributes = {'status': erratum_unit.status,
                             'type': erratum_unit.type,
                             'version': erratum_unit.version,
                             'from': erratum_unit.errata_from or ''}
        self.xml_generator.startElement('update', update_attributes)
        self.xml_generator.completeElement('id', {}, erratum_unit.errata_id)
        issued_attributes = {'date': erratum_unit.issued}
        self.xml_generator.completeElement('issued', issued_attributes, '')

        if erratum_unit.reboot_suggested:
            self.xml_generator.completeElement('reboot_suggested', {}, 'True')

        for element in self.optional_errata_fields:
            element_value = getattr(erratum_unit, element)
            if not element_value:
                continue
            self.xml_generator.completeElement(element, {}, unicode(element_value))

        for element in self.mandatory_errata_fields:
            element_value = getattr(erratum_unit, element)
            element_value = '' if element_value is None else element_value
            self.xml_generator.completeElement(element, {}, unicode(element_value))

        updated = erratum_unit.updated
        if updated:
            updated_attributes = {'date': updated}
            self.xml_generator.completeElement('updated', updated_attributes, '')

        self.xml_generator.startElement('references')
        for reference in erratum_unit.references:
            reference_attributes = {'id': reference['id'] or '',
                                    'title': reference['title'] or '',
                                    'type': reference['type'],
                                    'href': reference['href']}
            self.xml_generator.completeElement('reference', reference_attributes, '')
        self.xml_generator.endElement('references')

        self.xml_generator.startElement('pkglist')
        collection_attributes = {}
        short = filtered_pkglist.get('short')
        if short is not None:
            collection_attributes['short'] = short
        self.xml_generator.startElement('collection', collection_attributes)
        self.xml_generator.completeElement('name', {}, filtered_pkglist['name'])

        for package in filtered_pkglist['packages']:
            package_attributes = {'name': package['name'],
                                  'version': package['version'],
                                  'release': package['release'],
                                  'epoch': package['epoch'] or '0',
                                  'arch': package['arch'],
                                  'src': package.get('src', '') or ''}
            self.xml_generator.startElement('package', package_attributes)
            self.xml_generator.completeElement('filename', {}, package['filename'])

            package_checksum_tuple = self._get_package_checksum_tuple(package)
            if package_checksum_tuple:
                checksum_type, checksum_value = package_checksum_tuple
                sum_attributes = {'type': checksum_type}
                self.xml_generator.completeElement('sum', sum_attributes, checksum_value)

            if package.get('reboot_suggested'):
                self.xml_generator.completeElement('reboot_suggested', {}, 'True')
            self.xml_generator.endElement('package')

        self.xml_generator.endElement('collection')
        self.xml_generator.endElement('pkglist')
        self.xml_generator.endElement('update')
