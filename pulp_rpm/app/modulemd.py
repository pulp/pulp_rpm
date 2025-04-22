import createrepo_c as cr
import hashlib
import logging
import os
import tempfile
import yaml
import collections

from jsonschema import Draft7Validator
from gettext import gettext as _  # noqa:F401

from pulp_rpm.app.models import Modulemd, Package
from pulp_rpm.app.constants import (
    PULP_MODULEDEFAULTS_ATTR,
    PULP_MODULEOBSOLETES_ATTR,
    PULP_MODULE_ATTR,
    YAML_MODULEMD_OBSOLETES_REQUIRED_ATTR,
    YAML_MODULEMD_DEFAULTS_REQUIRED_ATTR,
)
from pulp_rpm.app.schema import MODULEMD_SCHEMA

log = logging.getLogger(__name__)


def resolve_module_packages(version, previous_version):
    """
    Decide which packages to add/remove based on modular data.

    Args:
        version (pulpcore.app.models.RepositoryVersion): current incomplete repository version
        previous_version (pulpcore.app.models.RepositoryVersion) :  previous version of the same
                                                                    repository to compare to

    """

    def modules_packages(modules):
        packages = set()
        for module in modules:
            packages.update(module.packages.all().only("pk"))
        return packages

    modulemd_pulp_type = Modulemd.get_pulp_type()
    current_modules = Modulemd.objects.filter(
        pk__in=version.content.filter(pulp_type=modulemd_pulp_type)
    )
    current_module_packages = modules_packages(current_modules)

    if previous_version:
        previous_modules = Modulemd.objects.filter(
            pk__in=previous_version.content.filter(pulp_type=modulemd_pulp_type)
        )
        added_modules = current_modules.difference(previous_modules)
        removed_modules = previous_modules.difference(current_modules)
        removed_module_packages = modules_packages(removed_modules)
        packages_to_remove = removed_module_packages.difference(current_module_packages)
        version.remove_content(Package.objects.filter(pk__in=packages_to_remove))
    else:
        added_modules = current_modules

    added_module_packages = modules_packages(added_modules)
    packages_to_add = added_module_packages.difference(current_module_packages)
    version.add_content(Package.objects.filter(pk__in=packages_to_add))


def split_modulemd_file(file: str):
    """
    Helper method to preserve original formatting of modulemd.

    Args:
        file: Absolute path to file
    """
    with tempfile.TemporaryDirectory(dir=".") as tf:
        decompressed_path = os.path.join(tf, "modulemd.yaml")
        cr.decompress_file(file, decompressed_path, cr.AUTO_DETECT_COMPRESSION)
        with open(decompressed_path) as modulemd_file:
            for doc in modulemd_file.read().split("---"):
                # strip any spaces or newlines from either side, strip the document end marking,
                # then strip again so we have only the document text w/o newlines
                stripped = doc.strip().rstrip("...").rstrip()
                if stripped:
                    # add the document begin/end markers backs
                    normalized = "---\n{}\n...".format(stripped)
                    yield normalized


def check_mandatory_module_fields(module, required_fields):
    """
    Check mandatory fields on module dict.
    """
    data = module["data"]
    for field in required_fields:
        if field not in data.keys():
            raise ValueError(
                _("Mandatory field {} is missing in {}.".format(field, module["document"]))
            )


def create_modulemd(modulemd, snippet):
    """
    Create dict with modulemd data to be saved to DB.
    """
    new_module = dict()
    new_module[PULP_MODULE_ATTR.NAME] = modulemd["data"].get("name")
    new_module[PULP_MODULE_ATTR.STREAM] = str(modulemd["data"].get("stream"))
    new_module[PULP_MODULE_ATTR.VERSION] = str(modulemd["data"].get("version"))
    new_module[PULP_MODULE_ATTR.STATIC_CONTEXT] = modulemd["data"].get("static_context")
    new_module[PULP_MODULE_ATTR.CONTEXT] = modulemd["data"].get("context")
    new_module[PULP_MODULE_ATTR.ARCH] = modulemd["data"].get("arch")
    new_module[PULP_MODULE_ATTR.ARTIFACTS] = modulemd["data"].get("artifacts", {}).get("rpms", [])
    new_module[PULP_MODULE_ATTR.DESCRIPTION] = modulemd["data"].get("description")
    new_module[PULP_MODULE_ATTR.DEPENDENCIES] = modulemd["data"].get("dependencies", [])

    # keep data formatted the same as it was with previous parsing implementation
    unprocessed_profiles = modulemd["data"].get("profiles", {})
    profiles = {}
    if unprocessed_profiles:
        for name, data in unprocessed_profiles.items():
            rpms = data.get("rpms")
            if not rpms:
                msg = (
                    "Got unexpected data for module {}-{}-{}-{}-{}: "
                    "profiles failed to parse properly"
                ).format(
                    new_module[PULP_MODULE_ATTR.NAME],
                    new_module[PULP_MODULE_ATTR.STREAM],
                    new_module[PULP_MODULE_ATTR.VERSION],
                    new_module[PULP_MODULE_ATTR.CONTEXT],
                    new_module[PULP_MODULE_ATTR.ARCH],
                )
                log.warning(msg)
            else:
                profiles[name] = rpms

    new_module[PULP_MODULE_ATTR.PROFILES] = profiles
    new_module["snippet"] = snippet
    new_module["digest"] = hashlib.sha256(snippet.encode()).hexdigest()

    return new_module


def create_modulemd_defaults(default, snippet):
    """
    Create dict with modulemd-defaults data to can be saved to DB.
    """
    new_default = dict()
    new_default[PULP_MODULEDEFAULTS_ATTR.MODULE] = default["data"].get("module")
    new_default[PULP_MODULEDEFAULTS_ATTR.STREAM] = str(default["data"].get("stream", ""))
    new_default[PULP_MODULEDEFAULTS_ATTR.PROFILES] = default["data"].get("profiles")
    new_default["snippet"] = snippet
    new_default[PULP_MODULEDEFAULTS_ATTR.DIGEST] = hashlib.sha256(snippet.encode()).hexdigest()

    return new_default


def create_modulemd_obsoletes(obsolete, snippet):
    """
    Create dict with modulemd-obsoletes data to can be saved to DB.
    """
    new_obsolete = dict()

    new_obsolete[PULP_MODULEOBSOLETES_ATTR.MODIFIED] = obsolete["data"].get("modified")
    new_obsolete[PULP_MODULEOBSOLETES_ATTR.MODULE] = obsolete["data"].get("module")
    new_obsolete[PULP_MODULEOBSOLETES_ATTR.STREAM] = str(obsolete["data"].get("stream"))
    new_obsolete[PULP_MODULEOBSOLETES_ATTR.MESSAGE] = obsolete["data"].get("message")
    new_obsolete[PULP_MODULEOBSOLETES_ATTR.RESET] = obsolete["data"].get("reset")
    new_obsolete[PULP_MODULEOBSOLETES_ATTR.CONTEXT] = obsolete["data"].get("context")

    if obsolete["data"].get("eol_date"):
        new_obsolete[PULP_MODULEOBSOLETES_ATTR.EOL] = obsolete["data"].get("eol_date")
    if obsolete["data"].get("obsoleted_by"):
        new_obsolete[PULP_MODULEOBSOLETES_ATTR.OBSOLETE_BY_MODULE] = obsolete["data"][
            "obsoleted_by"
        ].get("module")
        new_obsolete[PULP_MODULEOBSOLETES_ATTR.OBSOLETE_BY_STREAM] = obsolete["data"][
            "obsoleted_by"
        ].get("stream")
    new_obsolete["snippet"] = snippet

    return new_obsolete


def parse_modular(file: str):
    """
    Parse all modular metadata.

    Args:
        file: Absolute path to file
    """
    modulemd_all = []
    modulemd_defaults_all = []
    modulemd_obsoletes_all = []

    for module in split_modulemd_file(file):
        parsed_data = yaml.load(module, Loader=ModularYamlLoader)
        # here we check the modulemd document as we don't store all info, so serializers
        # are not enough then we only need to take required data from dict which is
        # parsed by pyyaml library
        if parsed_data["document"] == "modulemd":
            # the validator currently accepts formatting slightly different to the
            # spec due to the misconfiguration of some Rocky Linux 9 repositories
            # https://bugs.rockylinux.org/view.php?id=2575
            # further discussion on this issue can be found here:
            # https://github.com/pulp/pulp_rpm/issues/2998
            validator = Draft7Validator(MODULEMD_SCHEMA)
            err = []
            for error in sorted(validator.iter_errors(parsed_data["data"]), key=str):
                err.append(error.message)
            if err:
                raise ValueError(_("Provided modular data is invalid:'{}'".format(err)))
            modulemd_all.append(create_modulemd(parsed_data, module))
        elif parsed_data["document"] == "modulemd-defaults":
            check_mandatory_module_fields(parsed_data, YAML_MODULEMD_DEFAULTS_REQUIRED_ATTR)
            modulemd_defaults_all.append(create_modulemd_defaults(parsed_data, module))
        elif parsed_data["document"] == "modulemd-obsoletes":
            check_mandatory_module_fields(parsed_data, YAML_MODULEMD_OBSOLETES_REQUIRED_ATTR)
            modulemd_obsoletes_all.append(create_modulemd_obsoletes(parsed_data, module))
        else:
            logging.warning(f"Unknown modular document type found: {parsed_data.get('document')}")

    return modulemd_all, modulemd_defaults_all, modulemd_obsoletes_all


class ModularYamlLoader(yaml.SafeLoader):
    """
    Custom Loader that preserve unquoted float in specific fields (see #3285).

    Motivation (for customizing YAML parsing) is that libmodulemd also implement safe-quoting:
    https://github.com/fedora-modularity/libmodulemd/blob/main/modulemd/tests/test-modulemd-quoting.c

    This class is based on https://stackoverflow.com/a/74334992
    """

    # Field to preserve (will bypass yaml casting)
    PRESERVED_FIELDS = ("name", "stream", "version", "context", "arch")

    def construct_mapping(self, node, deep=False):
        if not isinstance(node, yaml.MappingNode):
            raise yaml.constructor.ConstructorError(
                None, None, "expected a mapping node, but found %s" % node.id, node.start_mark
            )
        mapping = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, collections.abc.Hashable):
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    "found unhashable key",
                    key_node.start_mark,
                )
            if key in ModularYamlLoader.PRESERVED_FIELDS and isinstance(
                value_node, yaml.ScalarNode
            ):
                value = value_node.value
            else:
                value = self.construct_object(value_node, deep=deep)
            mapping[key] = value
        return mapping
