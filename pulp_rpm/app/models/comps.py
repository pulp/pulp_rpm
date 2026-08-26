from logging import getLogger

import rpmrepo_metadata as rpmmd
from django.db import models

from pulpcore.plugin.models import Content
from pulpcore.plugin.util import get_domain_pk

from pulp_rpm.app.constants import (
    PULP_CATEGORY_ATTRS,
    PULP_ENVIRONMENT_ATTRS,
    PULP_GROUP_ATTRS,
    PULP_LANGPACKS_ATTRS,
)

log = getLogger(__name__)

PACKAGE_TYPE_MAPPING = {
    rpmmd.PackageReqType.DEFAULT: 0,
    rpmmd.PackageReqType.OPTIONAL: 1,
    rpmmd.PackageReqType.CONDITIONAL: 2,
    rpmmd.PackageReqType.MANDATORY: 3,
}

PACKAGE_TYPE_REVERSE = {v: k for k, v in PACKAGE_TYPE_MAPPING.items()}


class PackageGroup(Content):
    """
    The "PackageGroup" content type.

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

    TYPE = "packagegroup"

    # Required metadata
    id = models.TextField()

    default = models.BooleanField(default=False)
    user_visible = models.BooleanField(default=False)

    display_order = models.IntegerField(null=True)
    name = models.TextField()
    description = models.TextField(default="")
    packages = models.JSONField(default=list)

    biarch_only = models.BooleanField(default=False)

    desc_by_lang = models.JSONField(default=dict)
    name_by_lang = models.JSONField(default=dict)

    digest = models.TextField(db_index=True)

    repo_key_fields = ("id",)

    _pulp_domain = models.ForeignKey("core.Domain", default=get_domain_pk, on_delete=models.PROTECT)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = ("_pulp_domain", "digest")

    @classmethod
    def pkglist_to_list(cls, packages):
        """Convert rpmmd CompsPackageReq objects to a JSON-serializable list of dicts."""
        package_list = []
        for pkg in packages:
            as_dict = {
                "name": pkg.name,
                # libcomps historically normalized used a default value of "mandatory",
                # we do the same to preserve the behavior continuity.
                "type": PACKAGE_TYPE_MAPPING.get(
                    pkg.reqtype, PACKAGE_TYPE_MAPPING[rpmmd.PackageReqType.MANDATORY]
                ),
                "basearchonly": pkg.basearchonly,
                "requires": pkg.requires,
            }
            if as_dict not in package_list:
                package_list.append(as_dict)
        return package_list

    @classmethod
    def list_to_pkglist(cls, lst):
        pkglist = []
        for pkg in lst:
            pkglist.append(
                rpmmd.CompsPackageReq(
                    name=pkg["name"],
                    # libcomps historically normalized used a default value of "mandatory",
                    # we do the same to preserve the behavior continuity.
                    reqtype=PACKAGE_TYPE_REVERSE.get(pkg["type"], rpmmd.PackageReqType.MANDATORY),
                    requires=pkg["requires"],
                    # libcomps only initialized `basearchonly` when it had a value of "true" during parsing.
                    # Any other value including "false" and absent attribute would leave the value null.
                    # Therefore, libcomps could only return "True" or "None" when parsing from a comps document.
                    #
                    # Therefore, the value stored in the DB could be None, and we kept that behavior for
                    # continuity with existing documents.
                    basearchonly=bool(pkg["basearchonly"]),
                )
            )
        return pkglist

    @classmethod
    def comps_to_dict(cls, group):
        # libcomps defaulted to True here
        uservisible = group.uservisible if group.uservisible is not None else True
        return {
            PULP_GROUP_ATTRS.ID: group.id,
            PULP_GROUP_ATTRS.DEFAULT: group.default,
            PULP_GROUP_ATTRS.USER_VISIBLE: uservisible,
            PULP_GROUP_ATTRS.DISPLAY_ORDER: group.display_order,
            PULP_GROUP_ATTRS.NAME: group.name,
            PULP_GROUP_ATTRS.DESCRIPTION: group.description or "",
            PULP_GROUP_ATTRS.PACKAGES: cls.pkglist_to_list(group.packages),
            PULP_GROUP_ATTRS.BIARCH_ONLY: group.biarchonly,
            PULP_GROUP_ATTRS.DESC_BY_LANG: group.desc_by_lang,
            PULP_GROUP_ATTRS.NAME_BY_LANG: group.name_by_lang,
        }

    def to_comps_group(self):
        group = rpmmd.CompsGroup(
            id=self.id,
            name=self.name,
            description=self.description,
            default=self.default,
            uservisible=self.user_visible,
            display_order=self.display_order,
            biarchonly=self.biarch_only,
        )
        group.packages = self.list_to_pkglist(self.packages)
        group.desc_by_lang = self.desc_by_lang
        group.name_by_lang = self.name_by_lang
        return group


class PackageCategory(Content):
    """
    The "PackageCategory" content type.

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

    TYPE = "packagecategory"

    # Required metadata
    id = models.TextField()

    name = models.TextField()
    description = models.TextField(default="")
    display_order = models.IntegerField(null=True)

    group_ids = models.JSONField(default=list)

    desc_by_lang = models.JSONField(default=dict)
    name_by_lang = models.JSONField(default=dict)

    digest = models.TextField(db_index=True)

    repo_key_fields = ("id",)

    _pulp_domain = models.ForeignKey("core.Domain", default=get_domain_pk, on_delete=models.PROTECT)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = ("_pulp_domain", "digest")

    @classmethod
    def grouplist_to_list(cls, group_ids):
        """Convert rpmmd group id strings into Pulp's `[{"name", "default"}]` shape.

        A category's `grouplist` in comps.xml is a plain list of group ids with no
        per-group `default` flag, so `default` is always `False` here. The dict
        shape is retained to match Pulp's stored/serialized representation.
        """
        return [{PULP_GROUP_ATTRS.NAME: gid, PULP_GROUP_ATTRS.DEFAULT: False} for gid in group_ids]

    @classmethod
    def comps_to_dict(cls, category):
        return {
            PULP_CATEGORY_ATTRS.ID: category.id,
            PULP_CATEGORY_ATTRS.NAME: category.name,
            PULP_CATEGORY_ATTRS.DESCRIPTION: category.description or "",
            PULP_CATEGORY_ATTRS.DISPLAY_ORDER: category.display_order,
            PULP_CATEGORY_ATTRS.GROUP_IDS: cls.grouplist_to_list(category.group_ids),
            PULP_CATEGORY_ATTRS.DESC_BY_LANG: category.desc_by_lang,
            PULP_CATEGORY_ATTRS.NAME_BY_LANG: category.name_by_lang,
        }

    def to_comps_category(self):
        cat = rpmmd.CompsCategory(
            id=self.id,
            name=self.name,
            description=self.description,
            display_order=self.display_order,
        )
        cat.group_ids = [g["name"] for g in self.group_ids]
        cat.desc_by_lang = self.desc_by_lang
        cat.name_by_lang = self.name_by_lang
        return cat


class PackageEnvironment(Content):
    """
    The "PackageEnvironment" content type.

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

    TYPE = "packageenvironment"

    # Required metadata
    id = models.TextField()

    name = models.TextField()
    description = models.TextField(default="")
    display_order = models.IntegerField(null=True)

    group_ids = models.JSONField(default=list)
    option_ids = models.JSONField(default=list)

    desc_by_lang = models.JSONField(default=dict)
    name_by_lang = models.JSONField(default=dict)

    digest = models.TextField(db_index=True)

    repo_key_fields = ("id",)

    _pulp_domain = models.ForeignKey("core.Domain", default=get_domain_pk, on_delete=models.PROTECT)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = ("_pulp_domain", "digest")

    @classmethod
    def grouplist_to_list(cls, group_ids):
        """Convert rpmmd group id strings into Pulp's `[{"name", "default"}]` shape.

        An environment's `grouplist` holds mandatory groups, which carry no
        `default` attribute, so `default` is always `False` here. Optional
        groups (which do carry a `default` flag) come from `option_ids` instead;
        see `optlist_to_list`.
        """
        return [{PULP_GROUP_ATTRS.NAME: gid, PULP_GROUP_ATTRS.DEFAULT: False} for gid in group_ids]

    @classmethod
    def optlist_to_list(cls, option_ids):
        """Convert rpmmd `CompsEnvironmentOption` objects into Pulp's dict shape.

        An environment's `optionlist` groups each carry a `default` attribute
        indicating whether they are preselected, which is preserved here as
        `[{"name", "default"}]`.
        """
        return [
            {PULP_GROUP_ATTRS.NAME: opt.group_id, PULP_GROUP_ATTRS.DEFAULT: opt.default}
            for opt in option_ids
        ]

    @classmethod
    def comps_to_dict(cls, environment):
        return {
            PULP_ENVIRONMENT_ATTRS.ID: environment.id,
            PULP_ENVIRONMENT_ATTRS.NAME: environment.name,
            PULP_ENVIRONMENT_ATTRS.DESCRIPTION: environment.description or "",
            PULP_ENVIRONMENT_ATTRS.DISPLAY_ORDER: environment.display_order,
            PULP_ENVIRONMENT_ATTRS.GROUP_IDS: cls.grouplist_to_list(environment.group_ids),
            PULP_ENVIRONMENT_ATTRS.OPTION_IDS: cls.optlist_to_list(environment.option_ids),
            PULP_ENVIRONMENT_ATTRS.DESC_BY_LANG: environment.desc_by_lang,
            PULP_ENVIRONMENT_ATTRS.NAME_BY_LANG: environment.name_by_lang,
        }

    def to_comps_environment(self):
        env = rpmmd.CompsEnvironment(
            id=self.id,
            name=self.name,
            description=self.description,
            display_order=self.display_order,
        )
        env.group_ids = [g["name"] for g in self.group_ids]
        env.option_ids = [
            rpmmd.CompsEnvironmentOption(group_id=o["name"], default=o["default"])
            for o in self.option_ids
        ]
        env.desc_by_lang = self.desc_by_lang
        env.name_by_lang = self.name_by_lang
        return env


class PackageLangpacks(Content):
    """
    The "PackageLangpacks" content type.

    Fields:

        matches (Dict):
            The langpacks dictionary
    """

    TYPE = "packagelangpacks"

    matches = models.JSONField(default=dict)

    digest = models.TextField(db_index=True)

    _pulp_domain = models.ForeignKey("core.Domain", default=get_domain_pk, on_delete=models.PROTECT)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = ("_pulp_domain", "digest")

    @classmethod
    def comps_to_dict(cls, langpacks):
        return {PULP_LANGPACKS_ATTRS.MATCHES: {lp.name: lp.install for lp in langpacks}}
