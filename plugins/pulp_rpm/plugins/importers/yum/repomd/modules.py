import bson
import gi
gi.require_version('Modulemd', '1.0')  # noqa
from gi.repository import Modulemd

from pulp_rpm.plugins.db import models


def process_modulemd_document(module):
    """
    Process a parsed modules.yaml modulemd document into a model instance.

    :param module: Modulemd metadata document object.
    :type module: gi.repository.Modulemd.Module
    :return: Modulemd model object.
    :rtype: pulp_rpm.plugins.db.models.Modulemd
    """

    modulemd_document = {
        'name': module.peek_name(),
        'stream': module.peek_stream(),
        'version': module.peek_version(),
        'context': module.peek_context(),
        'arch': module.peek_arch(),
        'summary': module.peek_summary(),
        'description': module.peek_description(),
        'profiles': _get_profiles(module),
        'artifacts': module.peek_rpm_artifacts().get(),
    }

    return models.Modulemd(**modulemd_document)


def process_defaults_document(module):
    """
    Process a parsed modules.yaml modulemd-defaults document into a model instance.

    repo_id should be added during sync or upload before saving the unit.

    :param module: Modulemd-defaults metadata document object.
    :type module: gi.repository.Modulemd.Defaults
    :return: ModulemdDefaults model object.
    :rtype: pulp_rpm.plugins.db.models.ModulemdDefaults
    """
    modulemd_defaults_document = {
        'name': module.peek_module_name(),
        'repo_id': None,
        'stream': module.peek_default_stream(),
        'profiles': _get_profile_defaults(module),
    }

    return models.ModulemdDefaults(**modulemd_defaults_document)


def _get_profiles(module):
    """
    Parse profiles of given modulemd document

    :param module: Modulemd metadata document object.
    :type module: gi.repository.Modulemd.Module
    :return: key:value, where key is a profile name and value is set of packages.
    :rtype: dict
    """

    d = module.peek_profiles()
    for k, v in d.items():
        d[k] = v.peek_rpms().get()
    return d


def _get_profile_defaults(module):
    """
    Parse stream profile defaults of a given modulemd-defaults document.

    Dictionary has to be encoded due to MongoDB limitations for keys. MongoDB doesn't allow dots
    in the keys but it's a very common case for stream names.

    :param module: Modulemd-defaults metadata document object.
    :type module: gi.repository.Modulemd.Defaults
    :return: BSON encoded key:value, where key is a stream and value is a list of default profiles.
    :rtype: bson.BSON
    """
    profile_defaults = {}
    for stream, defaults in module.peek_profile_defaults().items():
        profile_defaults[stream] = defaults.get()
    return bson.BSON.encode(profile_defaults)


def from_file(metadata_file):
    """
    Parse profiles of given modulemd document

    :param metadata_file: path to the modules.yaml file
    :type metadata_file: string
    :return: 2 lists of Modulemd.Module and Modulemd.Defaults
    :rtype: list
    """

    modules = Modulemd.objects_from_file(metadata_file)
    modulemd = []
    defaults = []
    for module in modules:
        if isinstance(module, Modulemd.Module):
            modulemd.append(module)
        elif isinstance(module, Modulemd.Defaults):
            defaults.append(module)
    return modulemd, defaults
