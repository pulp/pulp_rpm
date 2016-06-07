import os

import mongoengine
from pulp.plugins.util.metadata_writer import XmlFileContext
from pulp.plugins.util.saxwriter import XMLWriter
from pulp.server.db.model import RepositoryContentUnit

from pulp_rpm.plugins.distributors.yum.metadata.metadata import REPO_DATA_DIR_NAME
from pulp_rpm.plugins.db import models
from pulp_rpm.yum_plugin import util


_logger = util.getLogger(__name__)

UPDATE_INFO_XML_FILE_NAME = 'updateinfo.xml.gz'


class UpdateinfoXMLFileContext(XmlFileContext):
    def __init__(self, working_dir, checksum_type=None, conduit=None):
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

    def _repo_unit_nevra(self, erratum_unit, repo_id):
        """
        Return a list of NEVRA dicts for units in a single repo referenced by the given errata.

        Pulp errata units combine the known packages from all synced repos. Given an errata unit
        and a repo, return a list of NEVRA dicts that can be used to filter out packages not
        linked to that repo when generating a repo's updateinfo XML file. While returning that
        list of NEVRA dicts is the main goal, doing so quickly and without running out of memory
        is what makes this a little bit tricky.

        Build up a super-fancy query to get the unit ids for all NEVRA seen in these errata
        check repo/unit associations for this errata to limit the packages in the published
        updateinfo to the units in the repo being currently published.

        :param erratum_unit: The erratum unit that should be written to updateinfo.xml.
        :type erratum_unit: pulp_rpm.plugins.db.models.Errata
        :param repo_id: The repo_id of a pulp repository in which to find units
        :type repo_id: str
        :return: a list of NEVRA dicts for units in a single repo referenced by the given errata
        :rtype: list
        """
        nevra_fields = ('name', 'epoch', 'version', 'release', 'arch')
        nevra_q = mongoengine.Q()
        for pkglist in erratum_unit.pkglist:
            for pkg in pkglist['packages']:
                pkg_nevra = dict((field, pkg[field]) for field in nevra_fields)
                nevra_q |= mongoengine.Q(**pkg_nevra)
        # Aim the super-fancy query at mongo to get the units that this errata refers to
        # The scaler method on the end returns a list of tuples to try to save some memory
        # and also cut down on mongoengine model instance hydration costs.
        nevra_units = models.RPM.objects.filter(nevra_q).scalar('id', *nevra_fields)

        # Split up the nevra unit entries into a mapping of the unit id to its nevra fields
        nevra_unit_map = dict((nevra_unit[0], nevra_unit[1:]) for nevra_unit in nevra_units)

        # Get all of the unit ids from this errata that are associated with the current repo.
        # Cast this as a set for speedier lookups when iterating of the nevra unit map.
        repo_unit_ids = set(RepositoryContentUnit.objects.filter(
            unit_id__in=nevra_unit_map.keys(), repo_id=repo_id).scalar('unit_id'))

        # Finally(!), intersect the repo unit ids with the unit nevra ids to
        # create a list of nevra dicts that can be easily compared to the
        # errata package nevra and exclude unrelated packages
        repo_unit_nevra = []
        for nevra_unit_id, nevra_field_values in nevra_unit_map.items():
            # based on the args to scalar when nevra_units was created:
            if nevra_unit_id in repo_unit_ids:
                repo_unit_nevra.append(dict(zip(nevra_fields, nevra_field_values)))

        return repo_unit_nevra

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
            repo_unit_nevra = self._repo_unit_nevra(erratum_unit, self.conduit.repo_id)
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

                checksum_tuple = package.get('sum', None)
                if checksum_tuple is not None:
                    checksum_type, checksum_value = checksum_tuple
                    sum_attributes = {'type': checksum_type}
                    self.xml_generator.completeElement('sum', sum_attributes, checksum_value)

                reboot_suggested_str = str(package.get('reboot_suggested', False))
                self.xml_generator.completeElement('reboot_suggested', {}, reboot_suggested_str)
                self.xml_generator.endElement('package')

            self.xml_generator.endElement('collection')
            self.xml_generator.endElement('pkglist')
        self.xml_generator.endElement('update')
