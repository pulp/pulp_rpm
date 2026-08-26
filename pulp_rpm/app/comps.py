import hashlib

import rpmrepo_metadata as rpmmd

from pulp_rpm.app.models import (
    PackageCategory,
    PackageEnvironment,
    PackageGroup,
    PackageLangpacks,
)


def dict_digest(dict):
    """
    Calculate a hexdigest for a given dictionary.

    Args:
        dict: a dictionary

    Returns:
        A digest

    """
    prep_hash = list(dict.values())
    str_prep_hash = [str(i) for i in prep_hash]
    str_prep_hash.sort()
    return hashlib.sha256("".join(str_prep_hash).encode("utf-8")).hexdigest()


def comps_to_model_dicts(comps_data, domain=None):
    """Convert rpmmd.CompsData to Pulp model field dictionaries with digests.

    Pure conversion function that mirrors parse_comps_components without DB operations.
    Returns dicts ready for get_or_create() or instance construction.

    Args:
        comps_data: rpmmd.CompsData instance from parsing comps.xml
        domain: optional _pulp_domain to include in the dicts

    Returns:
        Tuple of (groups, categories, environments, langpacks) where each is a list
        of dicts (or None for langpacks if not present), with digests calculated.
    """
    groups = []
    for group in comps_data.groups:
        group_dict = PackageGroup.comps_to_dict(group)
        group_dict["digest"] = dict_digest(group_dict)
        if domain:
            group_dict["_pulp_domain"] = domain
        groups.append(group_dict)

    categories = []
    for category in comps_data.categories:
        category_dict = PackageCategory.comps_to_dict(category)
        category_dict["digest"] = dict_digest(category_dict)
        if domain:
            category_dict["_pulp_domain"] = domain
        categories.append(category_dict)

    environments = []
    for environment in comps_data.environments:
        environment_dict = PackageEnvironment.comps_to_dict(environment)
        environment_dict["digest"] = dict_digest(environment_dict)
        if domain:
            environment_dict["_pulp_domain"] = domain
        environments.append(environment_dict)

    langpacks = None
    if comps_data.langpacks:
        langpack_dict = PackageLangpacks.comps_to_dict(comps_data.langpacks)
        langpack_dict["digest"] = dict_digest(langpack_dict)
        if domain:
            langpack_dict["_pulp_domain"] = domain
        langpacks = langpack_dict

    return groups, categories, environments, langpacks


def models_to_comps_data(groups, categories, environments, langpacks):
    """Convert Pulp model instances to rpmmd.CompsData.

    Pure conversion function that mirrors the publish loop logic.

    Args:
        groups: iterable of PackageGroup instances
        categories: iterable of PackageCategory instances
        environments: iterable of PackageEnvironment instances
        langpacks: PackageLangpacks instance or None

    Returns:
        rpmmd.CompsData instance ready for serialization to XML
    """
    comps = rpmmd.CompsData()
    comps.groups = [g.to_comps_group() for g in groups]
    comps.categories = [c.to_comps_category() for c in categories]
    comps.environments = [e.to_comps_environment() for e in environments]
    if langpacks is not None:
        comps.langpacks = [
            rpmmd.CompsLangpack(name=name, install=install)
            for name, install in langpacks.matches.items()
        ]
    return comps
