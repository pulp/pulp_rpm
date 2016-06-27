import os
from xml.etree import ElementTree

import mongoengine
from pulp.plugins.util.metadata_writer import XmlFileContext
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
        update_element = ElementTree.Element('update', update_attributes)

        id_element = ElementTree.SubElement(update_element, 'id')
        id_element.text = erratum_unit.errata_id

        issued_attributes = {'date': erratum_unit.issued}
        ElementTree.SubElement(update_element, 'issued', issued_attributes)

        reboot_element = ElementTree.SubElement(update_element, 'reboot_suggested')
        if erratum_unit.reboot_suggested is None:
            erratum_unit.reboot_suggested = False
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

                if repo_unit_nevra is not None:
                    # If repo_unit_nevra can be used for comparison, take the src attr out of a
                    # copy of this package's attrs to get a nevra dict for comparison
                    package_nevra = package_attributes.copy()
                    del(package_nevra['src'])
                    if package_nevra not in repo_unit_nevra:
                        # current package not in the specified repo, don't add it to the output
                        continue

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
