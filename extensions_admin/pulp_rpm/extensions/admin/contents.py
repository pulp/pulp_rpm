from gettext import gettext as _
import logging

from pulp.client.commands.criteria import DisplayUnitAssociationsCommand
from pulp.client.extensions.extensions import PulpCliOptionGroup, PulpCliOption

from pulp_rpm.extensions.admin import criteria_utils


# -- constants ----------------------------------------------------------------

# Must correspond to the IDs in the type definitions

TYPE_RPM = 'rpm'
TYPE_SRPM = 'srpm'
TYPE_DRPM = 'drpm'
TYPE_ERRATUM = 'erratum'
TYPE_DISTRIBUTION = 'distribution'
TYPE_PACKAGE_GROUP = 'package_group'
TYPE_PACKAGE_CATEGORY = 'package_category'
TYPE_PACKAGE_ENVIRONMENT = 'package_environment'

# Intentionally does not include distributions; they should be looked up specifically
ALL_TYPES = (TYPE_RPM, TYPE_SRPM, TYPE_DRPM, TYPE_ERRATUM, TYPE_PACKAGE_GROUP,
             TYPE_PACKAGE_CATEGORY, TYPE_PACKAGE_ENVIRONMENT)

# List of all fields that the user can elect to display for each supported type
FIELDS_RPM = ('arch', 'buildhost', 'checksum', 'checksumtype', 'description',
              'epoch', 'filename', 'license', 'name', 'provides', 'release',
              'requires', 'vendor', 'version')
FIELDS_ERRATA = ('id', 'title', 'summary', 'severity', 'type', 'description')
FIELDS_PACKAGE_GROUP = ('id', 'name', 'description', 'mandatory_package_names',
                        'conditional_package_names', 'optional_package_names',
                        'default_package_names', 'user_visible')
FIELDS_PACKAGE_CATEGORY = ('id', 'name', 'description', 'packagegroupids')
FIELDS_PACKAGE_ENVIRONMENT = ('id', 'name', 'description', 'group_ids', 'options')

# Used when generating the --fields help text so it can be customized by type
FIELDS_BY_TYPE = {
    TYPE_RPM: FIELDS_RPM,
    TYPE_SRPM: FIELDS_RPM,
    TYPE_DRPM: FIELDS_RPM,
    TYPE_ERRATUM: FIELDS_ERRATA,
    TYPE_PACKAGE_GROUP: FIELDS_PACKAGE_GROUP,
    TYPE_PACKAGE_CATEGORY: FIELDS_PACKAGE_CATEGORY,
    TYPE_PACKAGE_ENVIRONMENT: FIELDS_PACKAGE_ENVIRONMENT
}

# Ordering of metadata fields in each type. Keep in mind these are the display
# ordering within a unit; the order of the units themselves in the returned
# list from the server is dictated by the --ascending/--descending options.
ORDER_RPM = ['name', 'epoch', 'version', 'release', 'arch']
ORDER_ERRATA = ['id', 'tite', 'summary', 'severity', 'type', 'description']
ORDER_PACKAGE_GROUP = ['id', 'name', 'description', 'default_package_names',
                       'mandatory_package_names', 'optional_package_names',
                       'conditional_package_names', 'user_visible']
ORDER_PACKAGE_CATEGORY = ['id', 'name', 'description', 'packagegroupids']
ORDER_PACKAGE_ENVIRONMENT = ['id', 'name', 'description', 'group_ids', 'options']

# Used to lookup the right order list based on type
ORDER_BY_TYPE = {
    TYPE_RPM: ORDER_RPM,
    TYPE_SRPM: ORDER_RPM,
    TYPE_DRPM: ORDER_RPM,
    TYPE_ERRATUM: ORDER_ERRATA,
    TYPE_PACKAGE_GROUP: ORDER_PACKAGE_GROUP,
    TYPE_PACKAGE_CATEGORY: ORDER_PACKAGE_CATEGORY,
    TYPE_PACKAGE_ENVIRONMENT: ORDER_PACKAGE_ENVIRONMENT,
}

REQUIRES_COMPARISON_TRANSLATIONS = {
    'EQ': '=',
    'LT': '<',
    'LE': '<=',
    'GT': '>',
    'GE': '>=',
}

# Format to use when displaying the details of a single erratum
SINGLE_ERRATUM_TEMPLATE = _('''Id:                %(id)s
Title:             %(title)s
Summary:           %(summary)s
Description:
%(desc)s

Severity:          %(severity)s
Type:              %(type)s
Issued:            %(issued)s
Updated:           %(updated)s
Version:           %(version)s
Release:           %(release)s
Status:            %(status)s
Reboot Suggested:  %(reboot)s

Updated Packages:
%(pkgs)s

References:
%(refs)s
''')

# Renders the references section of an erratum. The spacing within matters so
# be careful when changing it.
REFERENCES_TEMPLATE = _('''  ID:   %(i)s
  Type: %(t)s
  Link: %(h)s

''')

LOG = logging.getLogger(__name__)

# -- constants ----------------------------------------------------------------

DESC_RPMS = _('search for RPMs in a repository')
DESC_SRPMS = _('search for SRPMs in a repository')
DESC_DRPMS = _('search for DRPMs in a repository')
DESC_GROUPS = _('search for package groups in a repository')
DESC_CATEGORIES = _('search for package categories (groups of package groups) in a repository')
DESC_ENVIRONMENTS = _('search for package environments (collections of package groups)'
                      'in a repository')
DESC_DISTRIBUTIONS = _('list distributions in a repository')
DESC_ERRATA = _('search errata in a repository')

ASSOCIATION_METADATA_KEYWORD = 'metadata'

# -- commands -----------------------------------------------------------------


class BaseSearchCommand(DisplayUnitAssociationsCommand):
    """
    Root of all search commands in this module. This currently only does modifications
    """

    def __init__(self, method, context, *args, **kwargs):
        super(BaseSearchCommand, self).__init__(method, *args, **kwargs)
        self.context = context

    def run_search(self, type_ids, out_func=None, **kwargs):
        """
        This is a generic command that will perform a search for any type or
        types of content.

        :param type_ids:    list of type IDs that the command should operate on
        :type  type_ids:    list, tuple

        :param out_func:    optional callable to be used in place of
                            prompt.render_document. Must accept one dict and an
                            optional list of fields
        :type  out_func:    callable

        :param kwargs:  CLI options as input by the user and passed in by okaara
        :type  kwargs:  dict
        """
        out_func = out_func or self.context.prompt.render_document_list

        repo_id = kwargs.pop('repo-id')
        kwargs['type_ids'] = type_ids
        units = self.context.server.repo_unit.search(repo_id, **kwargs).response_body

        if not kwargs.get(DisplayUnitAssociationsCommand.ASSOCIATION_FLAG.keyword):
            units = [u[ASSOCIATION_METADATA_KEYWORD] for u in units]

        # Some items either override output function and are not included
        # in the FIELDS_BY_TYPE dictionary.  Check so tha they can
        # override the default behavior
        if len(type_ids) == 1 and FIELDS_BY_TYPE.get(type_ids[0]):
            out_func(units, FIELDS_BY_TYPE[type_ids[0]])
        else:
            out_func(units)


class PackageSearchCommand(BaseSearchCommand):

    def __init__(self, type_id, context, *args, **kwargs):
        super(PackageSearchCommand, self).__init__(self.package_search, context, *args, **kwargs)
        self.type_id = type_id

    @staticmethod
    def _parse_key_value(args):
        return criteria_utils.parse_key_value(args)

    @classmethod
    def _parse_sort(cls, sort_args):
        return criteria_utils.parse_sort(DisplayUnitAssociationsCommand, sort_args)

    def package_search(self, **kwargs):
        def out_func(document_list, display_filter=FIELDS_RPM):
            """Inner function to filter rpm fields to display to the end user"""

            order = []

            # if the --details option has been specified, we need to manually
            # apply filtering to the unit data itself, since okaara's filtering
            # only operates at the top level of the document.
            if kwargs.get(self.ASSOCIATION_FLAG.keyword):
                # including most fields
                display_filter = ['updated', 'repo_id', 'created', 'unit_id', 'metadata',
                                  'unit_type_id', 'owner_type', 'id', 'owner_id']
                # display the unit info first
                order = [ASSOCIATION_METADATA_KEYWORD]

                # apply the same filtering that would normally be done by okaara
                for doc in document_list:
                    for key in doc[ASSOCIATION_METADATA_KEYWORD].keys():
                        if key not in FIELDS_RPM:
                            del doc[ASSOCIATION_METADATA_KEYWORD][key]

            # Create user-friendly translations for the requires and provides lists
            map(self._reformat_rpm_provides_requires, document_list)

            self.context.prompt.render_document_list(
                document_list, filters=display_filter, order=order)

        self.run_search([self.type_id], out_func=out_func, **kwargs)

    @staticmethod
    def _reformat_rpm_provides_requires(rpm):
        """
        Condenses the dict version of the provides and requires lists into single strings
        for each entry. The specified RPM is updated.

        :param rpm: single RPM from the result of the search
        :type  rpm: dict
        """

        def process_one(related_rpm):
            """
            Returns the single string view of an entry in the requires or provides list.
            Format: concatenated values (if present) separated by -
            """
            start = related_rpm['name']

            tail = '-'.join([related_rpm[key] for key in ['version', 'release', 'epoch']
                             if related_rpm[key] is not None])

            if related_rpm['flags'] is not None and \
               related_rpm['flags'] in REQUIRES_COMPARISON_TRANSLATIONS:
                # Bridge between name and version info with the comparison operator if present
                middle = ' ' + REQUIRES_COMPARISON_TRANSLATIONS[related_rpm['flags']] + ' '
            else:
                # If there is a tail, connect it with the - connector, but make sure to
                # not leave a trailing - if the version isn't present.
                if len(tail) > 0:
                    middle = '-'
                else:
                    middle = ''

            return start + middle + tail

        for reformat_me in ['requires', 'provides']:
            # First, check to see if the field has been included in --fields.
            if reformat_me in rpm or (ASSOCIATION_METADATA_KEYWORD in rpm and
                                      reformat_me in rpm[ASSOCIATION_METADATA_KEYWORD]):
                # If the --details flag was used, all the rpm data except for the association
                # data is placed inside a metadata dict by out_func. See if the key is in rpm
                # and act accordingly
                if ASSOCIATION_METADATA_KEYWORD in rpm:
                    related_rpm_list = rpm[ASSOCIATION_METADATA_KEYWORD][reformat_me]
                else:
                    related_rpm_list = rpm[reformat_me]

                formatted_rpms = [process_one(r) for r in related_rpm_list]
                if ASSOCIATION_METADATA_KEYWORD in rpm:
                    rpm[ASSOCIATION_METADATA_KEYWORD][reformat_me] = formatted_rpms
                else:
                    rpm[reformat_me] = formatted_rpms


class SearchRpmsCommand(PackageSearchCommand):

    def __init__(self, context):
        super(SearchRpmsCommand, self).__init__(TYPE_RPM, context, name='rpm',
                                                description=DESC_RPMS)


class SearchSrpmsCommand(PackageSearchCommand):

    def __init__(self, context):
        super(SearchSrpmsCommand, self).__init__(TYPE_SRPM, context, name='srpm',
                                                 description=DESC_SRPMS)


class SearchDrpmsCommand(BaseSearchCommand):

    def __init__(self, context):
        super(SearchDrpmsCommand, self).__init__(self.drpm, context, name='drpm',
                                                 description=DESC_DRPMS)

    def drpm(self, **kwargs):
        self.run_search([TYPE_DRPM], **kwargs)


class SearchPackageGroupsCommand(BaseSearchCommand):

    def __init__(self, context):
        super(SearchPackageGroupsCommand, self).__init__(self.package_group, context, name='group',
                                                         description=DESC_GROUPS)

    def package_group(self, **kwargs):
        self.run_search([TYPE_PACKAGE_GROUP], **kwargs)


class SearchPackageCategoriesCommand(BaseSearchCommand):

    def __init__(self, context):
        super(SearchPackageCategoriesCommand, self).__init__(self.package_category, context,
                                                             name='category',
                                                             description=DESC_CATEGORIES)

    def package_category(self, **kwargs):
        self.run_search([TYPE_PACKAGE_CATEGORY], **kwargs)


class SearchPackageEnvironmentsCommand(BaseSearchCommand):

    def __init__(self, context):
        super(SearchPackageEnvironmentsCommand, self).__init__(self.package_environment, context,
                                                               name='environment',
                                                               description=DESC_ENVIRONMENTS)

    def package_environment(self, **kwargs):
        self.run_search([TYPE_PACKAGE_ENVIRONMENT], **kwargs)


class SearchDistributionsCommand(BaseSearchCommand):

    def __init__(self, context):
        super(SearchDistributionsCommand, self).__init__(self.distribution, context,
                                                         name='distribution',
                                                         description=DESC_DISTRIBUTIONS)

    def distribution(self, **kwargs):
        self.run_search([TYPE_DISTRIBUTION], self.write_distro, **kwargs)

    def write_distro(self, distro_list):
        """
        Write a distro out in a specially formatted way. This call assumes
        there will be either 0 or 1 distributions in the repository.

        :param distro_list: list of distribution documents; will be of length 1
        :type  distro_list: list
        """
        if len(distro_list) == 0:
            return

        distro = distro_list[0]

        # Distro Metadata
        # id, family, arch, variant, _storage_path

        data = {
            'id': distro['id'],
            'family': distro['family'],
            'arch': distro['arch'],
            'variant': distro['variant'],
            'path': distro['_storage_path'],
        }

        self.context.prompt.write(_('Id:            %(id)s') % data)
        self.context.prompt.write(_('Family:        %(family)s') % data)
        self.context.prompt.write(_('Architecture:  %(arch)s') % data)
        self.context.prompt.write(_('Variant:       %(variant)s') % data)
        self.context.prompt.write(_('Storage Path:  %(path)s') % data)
        self.context.prompt.render_spacer()

        # Files
        # filename, relativepath, checksum, checksumtype, size
        self.context.prompt.write(_('Files:'))
        for f in distro['files']:
            data = {
                'filename': f['filename'],
                'path': f['relativepath'],
                'size': f['size'],
                'type': f['checksumtype'],
                'checksum': f['checksum'],
            }

            self.context.prompt.write(_('  Filename:       %(filename)s') % data)
            self.context.prompt.write(_('  Relative Path:  %(path)s') % data)
            self.context.prompt.write(_('  Size:           %(size)s') % data)
            self.context.prompt.write(_('  Checksum Type:  %(type)s') % data)

            checksum = self.context.prompt.wrap(_('  Checksum:       %(checksum)s') % data,
                                                remaining_line_indent=18)
            self.context.prompt.write(checksum, skip_wrap=True)
            self.context.prompt.render_spacer()


class SearchErrataCommand(BaseSearchCommand):

    def __init__(self, context):
        super(SearchErrataCommand, self).__init__(self.errata, context, name='errata',
                                                  description=DESC_ERRATA)

        erratum_group = PulpCliOptionGroup(_('Erratum'))

        m = _('if specified, the full details of an individual erratum are '
              'displayed, and all other options are ignored except for '
              '--repo-id.')
        erratum_group.add_option(PulpCliOption('--erratum-id', m, required=False))
        self.add_option_group(erratum_group)

    def errata(self, **kwargs):
        if kwargs['erratum-id'] is None:
            self.run_search([TYPE_ERRATUM], **kwargs)
        else:
            # Collect data
            repo_id = kwargs.pop('repo-id')
            erratum_id = kwargs.pop('erratum-id')
            new_kwargs = {
                'repo-id': repo_id,
                'filters': {'id': erratum_id}
            }
            self.run_search([TYPE_ERRATUM], self.write_erratum_detail, **new_kwargs)

    def write_erratum_detail(self, erratum_list, fields=None):
        """
        Write an erratum out in a specially formatted way. It is not known why this
        was originally needed.

        This function is only called when the --erratum-id argument is used, which
        prints the details for an erratum. The generic run_search function still
        passes the FIELDS_ERRATA list (which is for the render_document_list function),
        but since this is specifically for errata details, it is ignored here.

        :param erratum_list:    list one erratum documents; will be of length 1
        :type  erratum_list:    list
        :param fields:          A list of fields that the generic run_search function
                                hands to all output functions with a single type id in
                                the search. This is ignored.
        :type  fields:          list
        """
        erratum_meta = erratum_list[0]

        self.context.prompt.render_title(_('Erratum: %(e)s') % {'e': erratum_meta['id']})

        # Reformat the description
        description = erratum_meta['description']
        if description is not None:
            description = ''
            description_pieces = erratum_meta['description'].split('\n\n')
            for index, paragraph in enumerate(description_pieces):
                single_line_paragraph = paragraph.replace('\n', '')

                indent = 2
                wrapped = self.context.prompt.wrap((' ' * indent) + single_line_paragraph,
                                                   remaining_line_indent=indent)

                description += wrapped
                if index < len(description_pieces) - 1:
                    description += '\n\n'

        # Reformat packages affected
        package_list = []
        for pkglist in erratum_meta['pkglist']:
            for p in pkglist['packages']:
                package_list.append('  %s-%s:%s-%s.%s' %
                                    (p['name'], p['epoch'], p['version'], p['release'], p['arch']))

        # Reformat reboot flag
        if erratum_meta['reboot_suggested']:
            reboot = _('Yes')
        else:
            reboot = _('No')

        # Reformat the references
        references = ''
        for r in erratum_meta['references']:
            data = {'i': r['id'],
                    't': r['type'],
                    'h': r['href']}
            line = REFERENCES_TEMPLATE % data
            references += line

        template_data = {
            'id': erratum_meta['id'],
            'title': erratum_meta['title'],
            'summary': erratum_meta['summary'],
            'desc': description,
            'severity': erratum_meta['severity'],
            'type': erratum_meta['type'],
            'issued': erratum_meta['issued'],
            'updated': erratum_meta['updated'],
            'version': erratum_meta['version'],
            'release': erratum_meta['release'],
            'status': erratum_meta['status'],
            'reboot': reboot,
            'pkgs': '\n'.join(package_list),
            'refs': references,
        }

        display = SINGLE_ERRATUM_TEMPLATE % template_data
        self.context.prompt.write(display, skip_wrap=True)
