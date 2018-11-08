import bson

from pulp_rpm.plugins.db import models


METADATA_FILE_NAME = 'modules'


Modulemd = None


def load():
    """
    Load the gobject module and import the Modulemd (libmodulemd) lib.

    The gobject module and underlying C lib is not fork-safe and
    must be loaded after the WSGI process has forked.
    """
    import gi
    global Modulemd
    lib = 'Modulemd'
    gi.require_version(lib, '1.0')
    Modulemd = getattr(__import__('gi.repository', fromlist=[lib]), lib)


def process_modulemd_document(module):
    """
    Process a parsed modules.yaml modulemd document into a model instance.

    :param module: Modulemd metadata document object.
    :type module: gi.repository.Modulemd.Module
    :return: Modulemd model object.
    :rtype: pulp_rpm.plugins.db.models.Modulemd
    """
    load()
    modulemd_document = {
        'name': module.peek_name(),
        'stream': module.peek_stream(),
        'version': module.peek_version(),
        'context': module.peek_context(),
        'arch': module.peek_arch() or 'noarch',
        'summary': module.peek_summary(),
        'description': module.peek_description(),
        'profiles': _get_profiles(module),
        'artifacts': module.peek_rpm_artifacts().get(),
        'dependencies': _get_dependencies(module),
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
    load()
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
    load()
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
    load()
    profile_defaults = {}
    for stream, defaults in module.peek_profile_defaults().items():
        profile_defaults[stream] = defaults.get()
    return bson.BSON.encode(profile_defaults)


def _get_dependencies(module):
    """
    Parse dependencies of given modulemd document

    :param module: Modulemd metadata document object.
    :type module: gi.repository.Modulemd.Module
    :return: list of dictionaries, where for each dictionary, key is a module name and value
             is a list of streams
    :rtype: list
    """
    load()
    res = []
    deps = module.get_dependencies()
    for dep in deps:
        d = {}
        for k, v in dep.get_requires().iteritems():
            d[k] = v.get()
            res.append(d)
    return res


def from_file(path):
    """
    Parse profiles of given modulemd document

    :param path: An optional path to the modules.yaml file
    :type path: str
    :return: 2 lists of Modulemd.Module and Modulemd.Defaults
    :rtype: tuple
    """
    load()
    modulemd = []
    defaults = []
    modules = Modulemd.objects_from_file(path)
    for module in modules:
        if isinstance(module, Modulemd.Module):
            modulemd.append(module)
        elif isinstance(module, Modulemd.Defaults):
            defaults.append(module)
    return modulemd, defaults
