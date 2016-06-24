import os

from pulp.plugins.util.metadata_writer import XmlFileContext
from pulp.plugins.util.saxwriter import XMLWriter

from pulp_rpm.plugins.distributors.yum.metadata.metadata import REPO_DATA_DIR_NAME
from pulp_rpm.plugins.db import models
from pulp_rpm.yum_plugin import util


_logger = util.getLogger(__name__)

UPDATE_INFO_XML_FILE_NAME = 'updateinfo.xml.gz'


class UpdateinfoXMLFileContext(XmlFileContext):

    def __init__(self, working_dir, nevra_in_repo, checksum_type=None, conduit=None):
        """
        Creates and writes updateinfo XML data.

        :param working_dir: The working directory for the request
        :type working_dir:  basestring
        :param nevra_in_repo: The nevra of all rpms in the repo.
        :type nevra_in_repo:  set of models.NEVRA objects
        :param checksum_type: The type of checksum to be used
        :type checksum_type:  basestring
        :param conduit: A conduit to use
        :type conduit:  pulp.plugins.conduits.repo_publish.RepoPublishConduit
        """
        self.nevra_in_repo = nevra_in_repo
        metadata_file_path = os.path.join(working_dir, REPO_DATA_DIR_NAME,
                                          UPDATE_INFO_XML_FILE_NAME)
        self.conduit = conduit
        super(UpdateinfoXMLFileContext, self).__init__(
            metadata_file_path, 'updates', checksum_type=checksum_type)
        self.optional_errata_fields = ('title', 'release', 'rights', 'solution', 'severity',
                                       'summary', 'pushcount')
        self.mandatory_errata_fields = ('description',)

    def _open_metadata_file_handle(self):
        """
        Open the metadata file handle, creating any missing parent directories.
        If the file already exists, this will overwrite it.
        """
        super(XmlFileContext, self)._open_metadata_file_handle()
        self.xml_generator = XMLWriter(self.metadata_file_handle, short_empty_elements=True)

    def _get_repo_unit_nevra(self, erratum_unit):
        """
        Return a list of NEVRA dicts for units in a single repo referenced by the given errata.

        Pulp errata units combine the known packages from all synced repos. Given an errata unit
        and a repo, return a list of NEVRA dicts that can be used to filter out packages not
        linked to that repo when generating a repo's updateinfo XML file.

        :param erratum_unit: The erratum unit that should be written to updateinfo.xml.
        :type erratum_unit: pulp_rpm.plugins.db.models.Errata

        :return: a list of NEVRA dicts for units in a single repo referenced by the given errata
        :rtype: list
        """
        nevra_in_repo_and_pkglist = []
        for pkglist in erratum_unit.pkglist:
            for pkg in pkglist['packages']:
                pkg_nevra = models.NEVRA(name=pkg['name'], epoch=pkg['epoch'],
                                         version=pkg['version'], release=pkg['release'],
                                         arch=pkg['arch'])
                if pkg_nevra in self.nevra_in_repo:
                    pkg_dict = {
                        'name': pkg_nevra.name,
                        'epoch': pkg_nevra.epoch,
                        'version': pkg_nevra.version,
                        'release': pkg_nevra.release,
                        'arch': pkg_nevra.arch,
                    }
                    nevra_in_repo_and_pkglist.append(pkg_dict)
        return nevra_in_repo_and_pkglist

    def _get_package_checksum_tuple(self, package):
        """
        Decide which checksum to publish for the given package in the erratum package list.

        Handle two possible ways of specifying the checksum in the erratum package list:
        - in the `sum` package field as a list of alternating checksum types and values,
          e.g. ['type1', 'checksum1', 'type2', 'checksum2']
        - in the `type` and `sums` package fields. It is only the case when the erratum was uploaded
          via pulp-admin. Only one type of the checksum could be specified this way.

        :param package: package from the erratum package list
        :type  package: dict
        :return: checksum type and value to publish. An empty tuple is returned if there is
                 no checksum of the repository checksum type available.
        :rtype: tuple
        """
        package_checksum_tuple = ()
        repo_checksum_type = self.checksum_type
        package_checksums = package.get('sum')
        if package_checksums:
            checksum_types = package_checksums[::2]
            checksum_values = package_checksums[1::2]
            checksums = dict(zip(checksum_types, checksum_values))
            if repo_checksum_type in checksums:
                checksum_value = checksums[repo_checksum_type]
                package_checksum_tuple = (repo_checksum_type, checksum_value)
        else:
            checksum_type = package.get('type')
            checksum_value = package.get('sums')
            if checksum_type == repo_checksum_type and checksum_value:
                package_checksum_tuple = (checksum_type, checksum_value)
        return package_checksum_tuple

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
        self.xml_generator.startElement('update', update_attributes)
        self.xml_generator.completeElement('id', {}, erratum_unit.errata_id)
        issued_attributes = {'date': erratum_unit.issued}
        self.xml_generator.completeElement('issued', issued_attributes, '')

        if erratum_unit.reboot_suggested is None:
            erratum_unit.reboot_suggested = False
        reboot_suggested_str = str(erratum_unit.reboot_suggested)
        self.xml_generator.completeElement('reboot_suggested', {}, reboot_suggested_str)

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

        # If we can pull a repo_id off the conduit, use that to generate repo-specific nevra
        if self.conduit and hasattr(self.conduit, 'repo_id'):
            repo_unit_nevra = self._get_repo_unit_nevra(erratum_unit)
        else:
            repo_unit_nevra = None

        seen_pkglists = set()
        for pkglist in erratum_unit.pkglist:
            packages = tuple(sorted(p['filename'] for p in pkglist['packages']))
            if packages in seen_pkglists:
                continue
            seen_pkglists.add(packages)

            self.xml_generator.startElement('pkglist')
            collection_attributes = {}
            short = pkglist.get('short')
            if short is not None:
                collection_attributes['short'] = short
            self.xml_generator.startElement('collection', collection_attributes)
            self.xml_generator.completeElement('name', {}, pkglist['name'])

            for package in pkglist['packages']:
                package_attributes = {'name': package['name'],
                                      'version': package['version'],
                                      'release': package['release'],
                                      'epoch': package['epoch'] or '0',
                                      'arch': package['arch'],
                                      'src': package.get('src', '') or ''}
                if repo_unit_nevra is not None:
                    # If repo_unit_nevra can be used for comparison, take the src attr out of a
                    # copy of this package's attrs to get a nevra dict for comparison
                    package_nevra = package_attributes.copy()
                    del(package_nevra['src'])
                    if package_nevra not in repo_unit_nevra:
                        # current package not in the specified repo, don't add it to the output
                        continue

                self.xml_generator.startElement('package', package_attributes)
                self.xml_generator.completeElement('filename', {}, package['filename'])

                package_checksum_tuple = self._get_package_checksum_tuple(package)
                if package_checksum_tuple:
                    checksum_type, checksum_value = package_checksum_tuple
                    sum_attributes = {'type': checksum_type}
                    self.xml_generator.completeElement('sum', sum_attributes, checksum_value)

                reboot_suggested_str = str(package.get('reboot_suggested', False))
                self.xml_generator.completeElement('reboot_suggested', {}, reboot_suggested_str)
                self.xml_generator.endElement('package')

            self.xml_generator.endElement('collection')
            self.xml_generator.endElement('pkglist')
        self.xml_generator.endElement('update')
