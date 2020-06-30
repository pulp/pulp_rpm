from logging import getLogger

import libcomps

from django.contrib.postgres.fields import JSONField
from django.db import models

from pulpcore.plugin.models import Content

from pulp_rpm.app.constants import (
    LIBCOMPS_CATEGORY_ATTRS,
    LIBCOMPS_ENVIRONMENT_ATTRS,
    LIBCOMPS_GROUP_ATTRS,
    PULP_CATEGORY_ATTRS,
    PULP_ENVIRONMENT_ATTRS,
    PULP_GROUP_ATTRS,
    PULP_LANGPACKS_ATTRS,
)

from pulp_rpm.app.comps import dict_to_strdict, list_to_idlist, strdict_to_dict

log = getLogger(__name__)


class PackageGroup(Content):
    """
    The "PackageGroup" content type.

    Maps directly to the fields provided by libcomps.
    https://github.com/rpm-software-management/libcomps

    Fields:

        id (Text):
            ID of the group
        default (Bool):
            Flag to identify whether the group is a default
        user_visible (Bool):
            Flag to identify if the group is visible to the user

        display_order (Int):
            Number representing the order of display
        name (Text):
            Name of the group
        description (Text):
            Description of the group
        packages (Text):
            The list of packages in this group
        biarch_only (Bool):
            Flag to identify whether the group is biarch
        desc_by_lang (Text):
            A dictionary of descriptions by language
        name_by_lang (Text):
            A dictionary of names by language
        digest (Text):
            A checksum for the group
    """

    TYPE = 'packagegroup'

    # Required metadata
    id = models.CharField(max_length=255)

    default = models.BooleanField(default=False)
    user_visible = models.BooleanField(default=False)

    display_order = models.IntegerField(null=True)
    name = models.CharField(max_length=255)
    description = models.TextField(default='')
    packages = JSONField(default=list)

    biarch_only = models.BooleanField(default=False)

    desc_by_lang = JSONField(default=dict)
    name_by_lang = JSONField(default=dict)

    digest = models.CharField(unique=True, max_length=64)

    repo_key_fields = ('id',)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"

    @classmethod
    def natural_key_fields(cls):
        """
        Digest is used as a natural key for PackageGroups.
        """
        return ('digest',)

    @classmethod
    def pkglist_to_list(cls, value):
        """
        Convert libcomps PkgList to list.

        Args:
            value: a libcomps PkgList

        Returns:
            A list

        """
        package_list = []
        for i in value:
            as_dict = {
                'name': i.name,
                'type': i.type,
                'basearchonly': i.basearchonly,
                'requires': i.requires
            }
            if as_dict not in package_list:
                package_list.append(as_dict)
        return package_list

    @classmethod
    def list_to_pkglist(cls, lst):
        """
        Convert list of Packages to libcomps PackageList object.

        Args:
            list: a list of Packages

        Returns:
            pkglist: a libcomps PackageList

        """
        pkglist = libcomps.PackageList()
        for pkg in lst:
            lib_pkg = libcomps.Package()
            lib_pkg.name = pkg['name']
            lib_pkg.type = pkg['type']
            lib_pkg.basearchonly = bool(pkg['basearchonly'])
            lib_pkg.requires = pkg['requires']
            pkglist.append(lib_pkg)

        return pkglist

    @classmethod
    def libcomps_to_dict(cls, group):
        """
        Convert libcomps group object to dict for instantiating PackageGroup object.

        Args:
            group(libcomps.group): a RPM/SRPM group to convert

        Returns:
            dict: all data for RPM/SRPM group content creation

        """
        return {
            PULP_GROUP_ATTRS.ID: getattr(group, LIBCOMPS_GROUP_ATTRS.ID),
            PULP_GROUP_ATTRS.DEFAULT: getattr(group, LIBCOMPS_GROUP_ATTRS.DEFAULT),
            PULP_GROUP_ATTRS.USER_VISIBLE: getattr(group, LIBCOMPS_GROUP_ATTRS.USER_VISIBLE),
            PULP_GROUP_ATTRS.DISPLAY_ORDER: getattr(group, LIBCOMPS_GROUP_ATTRS.DISPLAY_ORDER),
            PULP_GROUP_ATTRS.NAME: getattr(group, LIBCOMPS_GROUP_ATTRS.NAME),
            PULP_GROUP_ATTRS.DESCRIPTION: getattr(group, LIBCOMPS_GROUP_ATTRS.DESCRIPTION) or '',
            PULP_GROUP_ATTRS.PACKAGES: cls.pkglist_to_list(getattr(group,
                                                                   LIBCOMPS_GROUP_ATTRS.PACKAGES)),
            PULP_GROUP_ATTRS.BIARCH_ONLY: getattr(group, LIBCOMPS_GROUP_ATTRS.BIARCH_ONLY),
            PULP_GROUP_ATTRS.DESC_BY_LANG: strdict_to_dict(
                getattr(group, LIBCOMPS_GROUP_ATTRS.DESC_BY_LANG)
            ),
            PULP_GROUP_ATTRS.NAME_BY_LANG: strdict_to_dict(
                getattr(group, LIBCOMPS_GROUP_ATTRS.NAME_BY_LANG)
            ),
        }

    def pkg_grp_to_libcomps(self):
        """
        Convert PackageGroup object to libcomps Group object.

        Returns:
            group: libcomps.Group object

        """
        group = libcomps.Group()

        group.id = getattr(self, PULP_GROUP_ATTRS.ID)
        group.default = getattr(self, PULP_GROUP_ATTRS.DEFAULT)
        group.uservisible = getattr(self, PULP_GROUP_ATTRS.USER_VISIBLE)
        group.display_order = getattr(self, PULP_GROUP_ATTRS.DISPLAY_ORDER)
        group.name = getattr(self, PULP_GROUP_ATTRS.NAME)
        group.desc = getattr(self, PULP_GROUP_ATTRS.DESCRIPTION)
        group.packages = self.list_to_pkglist(getattr(self, PULP_GROUP_ATTRS.PACKAGES))
        group.biarchonly = getattr(self, PULP_GROUP_ATTRS.BIARCH_ONLY)
        group.desc_by_lang = dict_to_strdict(getattr(self, PULP_GROUP_ATTRS.DESC_BY_LANG))
        group.name_by_lang = dict_to_strdict(getattr(self, PULP_GROUP_ATTRS.NAME_BY_LANG))

        return group


class PackageCategory(Content):
    """
    The "Category" content type. Formerly "PackageCategory" in Pulp 2.

    Maps directly to the fields provided by libcomps.
    https://github.com/rpm-software-management/libcomps

    Fields:

        id (Text):
            ID of the category
        name (Text):
            The name of the category
        description (Text):
            The description of the category
        display_order (Int):
            Number representing the order of display
        group_ids (Text):
            A list of group ids
        desc_by_lang (Text):
            A dictionary of descriptions by language
        name_by_lang (Text):
            A dictionary of names by language
        digest (Text):
            A checksum for the category
    """

    TYPE = 'packagecategory'

    # Required metadata
    id = models.CharField(max_length=255)

    name = models.CharField(max_length=255)
    description = models.TextField(default='')
    display_order = models.IntegerField(null=True)

    group_ids = JSONField(default=list)

    desc_by_lang = JSONField(default=dict)
    name_by_lang = JSONField(default=dict)

    digest = models.CharField(unique=True, max_length=64)

    repo_key_fields = ('id',)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"

    @classmethod
    def natural_key_fields(cls):
        """
        Digest is used as a natural key for PackageCategory.
        """
        return ('digest',)

    @classmethod
    def grplist_to_lst(cls, value):
        """
        Convert libcomps GrpList to list.

        Args:
            value: a libcomps GrpList

        Returns:
            A list

        """
        grp_list = []
        for i in value:
            grp_list.append({'name': i.name,
                             'default': i.default})
        return grp_list

    @classmethod
    def libcomps_to_dict(cls, category):
        """
        Convert libcomps category object to dict for instantiating PackageCategory object.

        Args:
            category(libcomps.category): a RPM/SRPM category to convert

        Returns:
            dict: all data for RPM/SRPM category content creation

        """
        return {
            PULP_CATEGORY_ATTRS.ID: getattr(category, LIBCOMPS_CATEGORY_ATTRS.ID),
            PULP_CATEGORY_ATTRS.NAME: getattr(category, LIBCOMPS_CATEGORY_ATTRS.NAME),
            PULP_CATEGORY_ATTRS.DESCRIPTION: getattr(category,
                                                     LIBCOMPS_CATEGORY_ATTRS.DESCRIPTION) or '',
            PULP_CATEGORY_ATTRS.DISPLAY_ORDER: getattr(category,
                                                       LIBCOMPS_CATEGORY_ATTRS.DISPLAY_ORDER),
            PULP_CATEGORY_ATTRS.GROUP_IDS: cls.grplist_to_lst(
                getattr(category, LIBCOMPS_CATEGORY_ATTRS.GROUP_IDS)
            ),
            PULP_CATEGORY_ATTRS.DESC_BY_LANG: strdict_to_dict(
                getattr(category, LIBCOMPS_CATEGORY_ATTRS.DESC_BY_LANG)
            ),
            PULP_CATEGORY_ATTRS.NAME_BY_LANG: strdict_to_dict(
                getattr(category, LIBCOMPS_CATEGORY_ATTRS.NAME_BY_LANG)
            ),
        }

    def pkg_cat_to_libcomps(self):
        """
        Convert PackageCategory object to libcomps Category object.

        Returns:
            group: libcomps.Category object

        """
        cat = libcomps.Category()

        cat.id = getattr(self, PULP_CATEGORY_ATTRS.ID)
        cat.name = getattr(self, PULP_CATEGORY_ATTRS.NAME)
        cat.desc = getattr(self, PULP_CATEGORY_ATTRS.DESCRIPTION)
        cat.display_order = getattr(self, PULP_CATEGORY_ATTRS.DISPLAY_ORDER)
        cat.group_ids = list_to_idlist(getattr(self, PULP_CATEGORY_ATTRS.GROUP_IDS))
        cat.desc_by_lang = dict_to_strdict(getattr(self, PULP_CATEGORY_ATTRS.DESC_BY_LANG))
        cat.name_by_lang = dict_to_strdict(getattr(self, PULP_CATEGORY_ATTRS.NAME_BY_LANG))

        return cat


class PackageEnvironment(Content):
    """
    The "Environment" content type. Formerly "PackageEnvironment" in Pulp 2.

    Maps directly to the fields provided by libcomps.
    https://github.com/rpm-software-management/libcomps

    Fields:

        id (Text):
            ID of the environment
        name (Text):
            The name of the environment
        description (Text):
            The description of the environment
        display_order (Int):
            Number representing the order of display
        group_ids (Text):
            A list of group ids
        option_ids (Text):
            A list of option ids
        desc_by_lang (Text):
            A dictionary of descriptions by language
        name_by_lang (Text):
            A dictionary of names by language
        digest (Text):
            A checksum for the environment
    """

    TYPE = 'packageenvironment'

    # Required metadata
    id = models.CharField(max_length=255)

    name = models.CharField(max_length=255)
    description = models.TextField(default='')
    display_order = models.IntegerField(null=True)

    group_ids = JSONField(default=list)
    option_ids = JSONField(default=list)

    desc_by_lang = JSONField(default=dict)
    name_by_lang = JSONField(default=dict)

    digest = models.CharField(unique=True, max_length=64)

    repo_key_fields = ('id',)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"

    @classmethod
    def natural_key_fields(cls):
        """
        Digest is used as a natural key for PackageEnvironment.
        """
        return ('digest',)

    @classmethod
    def grplist_to_lst(cls, value):
        """
        Convert libcomps GrpList to list.

        Args:
            value: a libcomps GrpList

        Returns:
            A list

        """
        grp_list = []
        for i in value:
            grp_list.append({'name': i.name,
                             'default': i.default})
        return grp_list

    @classmethod
    def libcomps_to_dict(cls, environment):
        """
        Convert libcomps environment object to dict for instantiating PackageEnvironment object.

        Args:
            environment(libcomps.environment): a RPM/SRPM environment to convert

        Returns:
            dict: all data for RPM/SRPM environment content creation

        """
        return {
            PULP_ENVIRONMENT_ATTRS.ID: getattr(environment, LIBCOMPS_ENVIRONMENT_ATTRS.ID),
            PULP_ENVIRONMENT_ATTRS.NAME: getattr(environment, LIBCOMPS_ENVIRONMENT_ATTRS.NAME),
            PULP_ENVIRONMENT_ATTRS.DESCRIPTION: getattr(
                environment, LIBCOMPS_ENVIRONMENT_ATTRS.DESCRIPTION
            ) or '',
            PULP_ENVIRONMENT_ATTRS.DISPLAY_ORDER: getattr(environment,
                                                          LIBCOMPS_ENVIRONMENT_ATTRS.DISPLAY_ORDER),
            PULP_ENVIRONMENT_ATTRS.GROUP_IDS: cls.grplist_to_lst(
                getattr(environment, LIBCOMPS_ENVIRONMENT_ATTRS.GROUP_IDS)
            ),
            PULP_ENVIRONMENT_ATTRS.OPTION_IDS: cls.grplist_to_lst(
                getattr(environment, LIBCOMPS_ENVIRONMENT_ATTRS.OPTION_IDS)
            ),
            PULP_ENVIRONMENT_ATTRS.DESC_BY_LANG: strdict_to_dict(
                getattr(environment, LIBCOMPS_ENVIRONMENT_ATTRS.DESC_BY_LANG)
            ),
            PULP_ENVIRONMENT_ATTRS.NAME_BY_LANG: strdict_to_dict(
                getattr(environment, LIBCOMPS_ENVIRONMENT_ATTRS.NAME_BY_LANG)
            ),
        }

    def pkg_env_to_libcomps(self):
        """
        Convert PackageEnvironment object to libcomps Environment object.

        Returns:
            group: libcomps.Environment object

        """
        env = libcomps.Environment()

        env.id = getattr(self, PULP_ENVIRONMENT_ATTRS.ID)
        env.name = getattr(self, PULP_ENVIRONMENT_ATTRS.NAME)
        env.desc = getattr(self, PULP_ENVIRONMENT_ATTRS.DESCRIPTION)
        env.display_order = getattr(self, PULP_ENVIRONMENT_ATTRS.DISPLAY_ORDER)
        env.group_ids = list_to_idlist(getattr(self, PULP_ENVIRONMENT_ATTRS.GROUP_IDS))
        env.option_ids = list_to_idlist(getattr(self, PULP_ENVIRONMENT_ATTRS.OPTION_IDS))
        env.desc_by_lang = dict_to_strdict(getattr(self, PULP_ENVIRONMENT_ATTRS.DESC_BY_LANG))
        env.name_by_lang = dict_to_strdict(getattr(self, PULP_ENVIRONMENT_ATTRS.NAME_BY_LANG))

        return env


class PackageLangpacks(Content):
    """
    The "Langpacks" content type. Formerly "PackageLangpacks" in Pulp 2.

    Maps directly to the fields provided by libcomps.
    https://github.com/rpm-software-management/libcomps

    Fields:

        matches (Dict):
            The langpacks dictionary
    """

    TYPE = 'packagelangpacks'

    matches = JSONField(default=dict)

    digest = models.CharField(unique=True, max_length=64)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"

    @classmethod
    def natural_key_fields(cls):
        """
        Digest is used as a natural key for PackageLangpacks.
        """
        return ('digest',)

    @classmethod
    def libcomps_to_dict(cls, langpacks):
        """
        Convert libcomps langpacks object to dict for instantiating PackageLangpacks object.

        Args:
            langpacks(libcomps.langpacks): a RPM/SRPM langpacks to convert

        Returns:
            dict: all data for RPM/SRPM langpacks content creation

        """
        return {
            PULP_LANGPACKS_ATTRS.MATCHES: strdict_to_dict(langpacks)
        }
