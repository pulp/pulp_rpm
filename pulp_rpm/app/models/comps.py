from logging import getLogger

import rpmrepo_metadata as rpmmd
from django.db import models

from pulpcore.plugin.models import Content
from pulpcore.plugin.util import get_domain_pk

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
        langonly (Text):
            Language restriction for the group, if any
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
    langonly = models.TextField(null=True)

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
                "type": PACKAGE_TYPE_MAPPING.get(pkg.reqtype, 0),
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
                    reqtype=PACKAGE_TYPE_REVERSE.get(pkg["type"], rpmmd.PackageReqType.DEFAULT),
                    requires=pkg["requires"],
                    basearchonly=bool(pkg["basearchonly"]) if pkg["basearchonly"] else None,
                )
            )
        return pkglist

    @classmethod
    def comps_to_dict(cls, group):
        return {
            "id": group.id,
            "default": group.default,
            "user_visible": group.uservisible,
            "display_order": group.display_order,
            "name": group.name,
            "description": group.description or "",
            "packages": cls.pkglist_to_list(group.packages),
            "biarch_only": group.biarchonly,
            "langonly": group.langonly,
            "desc_by_lang": dict(group.desc_by_lang),
            "name_by_lang": dict(group.name_by_lang),
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
            langonly=self.langonly,
        )
        group.packages = self.list_to_pkglist(self.packages)
        group.desc_by_lang = list(self.desc_by_lang.items())
        group.name_by_lang = list(self.name_by_lang.items())
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
    def grplist_to_lst(cls, group_ids):
        return [{"name": gid, "default": False} for gid in group_ids]

    @classmethod
    def comps_to_dict(cls, category):
        return {
            "id": category.id,
            "name": category.name,
            "description": category.description or "",
            "display_order": category.display_order,
            "group_ids": cls.grplist_to_lst(category.group_ids),
            "desc_by_lang": dict(category.desc_by_lang),
            "name_by_lang": dict(category.name_by_lang),
        }

    def to_comps_category(self):
        cat = rpmmd.CompsCategory(
            id=self.id,
            name=self.name,
            description=self.description,
            display_order=self.display_order,
        )
        cat.group_ids = [g["name"] for g in self.group_ids]
        cat.desc_by_lang = list(self.desc_by_lang.items())
        cat.name_by_lang = list(self.name_by_lang.items())
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
    def grplist_to_lst(cls, group_ids):
        return [{"name": gid, "default": False} for gid in group_ids]

    @classmethod
    def optlist_to_lst(cls, option_ids):
        return [{"name": opt.group_id, "default": opt.default} for opt in option_ids]

    @classmethod
    def comps_to_dict(cls, environment):
        return {
            "id": environment.id,
            "name": environment.name,
            "description": environment.description or "",
            "display_order": environment.display_order,
            "group_ids": cls.grplist_to_lst(environment.group_ids),
            "option_ids": cls.optlist_to_lst(environment.option_ids),
            "desc_by_lang": dict(environment.desc_by_lang),
            "name_by_lang": dict(environment.name_by_lang),
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
        env.desc_by_lang = list(self.desc_by_lang.items())
        env.name_by_lang = list(self.name_by_lang.items())
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
        return {"matches": {lp.name: lp.install for lp in langpacks}}
