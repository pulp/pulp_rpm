import hashlib
from datetime import datetime

from pulp_rpm.app.models import Modulemd, Package
from pulp_rpm.app.constants import PULP_MODULE_ATTR, PULP_MODULEDEFAULTS_ATTR

import gi

gi.require_version("Modulemd", "2.0")
from gi.repository import Modulemd as mmdlib  # noqa: E402


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
            packages.update(module.packages.all())
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


def parse_modulemd(module_names, module_index):
    """
    Get modulemd NSVCA, artifacts, dependencies.

    Args:
        module_names (list):
            list of modulemd names
        module_index (mmdlib.ModuleIndex):
            libmodulemd index object

    Returns:
        list of modulemd as dict

    """
    ret = list()
    for module in module_names:
        for stream in module_index.get_module(module).get_all_streams():
            modulemd = dict()
            modulemd[PULP_MODULE_ATTR.NAME] = stream.props.module_name
            modulemd[PULP_MODULE_ATTR.STREAM] = stream.props.stream_name
            modulemd[PULP_MODULE_ATTR.VERSION] = str(stream.props.version)
            modulemd[PULP_MODULE_ATTR.STATIC_CONTEXT] = stream.props.static_context
            modulemd[PULP_MODULE_ATTR.CONTEXT] = stream.props.context
            modulemd[PULP_MODULE_ATTR.ARCH] = stream.props.arch
            modulemd[PULP_MODULE_ATTR.ARTIFACTS] = stream.get_rpm_artifacts()
            modulemd[PULP_MODULE_ATTR.DESCRIPTION] = stream.get_description()

            modulemd[PULP_MODULE_ATTR.PROFILES] = {}
            for profile in stream.get_profile_names():
                stream_profile = stream.get_profile(profile)
                modulemd[PULP_MODULE_ATTR.PROFILES][profile] = stream_profile.get_rpms()

            dependencies_list = stream.get_dependencies()
            dependencies = list()
            for dep in dependencies_list:
                depmodule_list = dep.get_runtime_modules()
                platform_deps = dict()
                for depmod in depmodule_list:
                    platform_deps[depmod] = dep.get_runtime_streams(depmod)
                dependencies.append(platform_deps)
            modulemd[PULP_MODULE_ATTR.DEPENDENCIES] = dependencies
            # create yaml snippet for this modulemd stream
            temp_index = mmdlib.ModuleIndex.new()
            temp_index.add_module_stream(stream)
            modulemd["snippet"] = temp_index.dump_to_string()
            ret.append(modulemd)
    return ret


def parse_defaults(module_index):
    """
    Get modulemd_defaults.

    Args:
        module_index (mmdlib.ModuleIndex):
            libmodulemd index object

    Returns:
        list of modulemd_defaults as dict

    """
    ret = list()
    modulemd_defaults = module_index.get_default_streams().keys()
    for module in modulemd_defaults:
        modulemd = module_index.get_module(module)
        defaults = modulemd.get_defaults()
        if defaults:
            default_stream = defaults.get_default_stream()
            default_profile = defaults.get_default_profiles_for_stream(default_stream)
            # create modulemd-default snippet
            temp_index = mmdlib.ModuleIndex.new()
            temp_index.add_defaults(defaults)
            snippet = temp_index.dump_to_string()
            ret.append(
                {
                    PULP_MODULEDEFAULTS_ATTR.MODULE: modulemd.get_module_name(),
                    PULP_MODULEDEFAULTS_ATTR.STREAM: default_stream,
                    PULP_MODULEDEFAULTS_ATTR.PROFILES: default_profile,
                    PULP_MODULEDEFAULTS_ATTR.DIGEST: hashlib.sha256(snippet.encode()).hexdigest(),
                    "snippet": snippet,
                }
            )
    return ret


def parse_obsoletes(module_names, module_index):
    """
    Get modulemd obsoletes.

    Args:
        module_names (list):
            list of modulemd names
        module_index (mmdlib.ModuleIndex):
            libmodulemd index object

    Returns:
        list of modulemd obsoletes as dict

    """
    ret = list()
    for module in module_names:
        modulemd = module_index.get_module(module)
        for obsolete in modulemd.get_obsoletes():
            new_obsolete = dict()
            # parsed as in documentation
            # https://fedora-modularity.github.io/libmodulemd/latest/modulemd-2.0-Modulemd.Obsoletes.html#ModulemdObsoletes--modified
            new_obsolete["modified"] = datetime.strptime(str(obsolete.props.modified), "%Y%m%d%H%M")
            new_obsolete["module_name"] = obsolete.props.module_name
            new_obsolete["module_stream"] = obsolete.props.module_stream
            new_obsolete["message"] = obsolete.props.message
            new_obsolete["override_previous"] = obsolete.props.override_previous
            new_obsolete["module_context"] = obsolete.props.module_context
            # EOL date is '0' if not specified instead None
            try:
                new_obsolete["eol_date"] = datetime.strptime(
                    str(obsolete.props.eol_date), "%Y%m%d%H%M"
                )
            except ValueError:
                new_obsolete["eol_date"] = None
            new_obsolete["obsoleted_by_module_name"] = obsolete.props.obsoleted_by_module_name
            new_obsolete["obsoleted_by_module_stream"] = obsolete.props.obsoleted_by_module_stream
            # Create a snippet
            temp_module_index = mmdlib.ModuleIndex.new()
            temp_module_index.add_obsoletes(obsolete)
            new_obsolete["snippet"] = temp_module_index.dump_to_string()
            ret.append(new_obsolete)
    return ret
