import json

from pulp_rpm.app.models import ModulemdDefaults
from pulp_rpm.app.serializers import ModulemdDefaultsSerializer

import gi
gi.require_version('Modulemd', '2.0')
from gi.repository import Modulemd as mmdlib  # noqa: E402


def _get_modules(file, module_index):
    """Get modulemd names."""
    module_str = file.open().read().decode()
    ret, fails = module_index.update_from_string(module_str, True)
    if ret:
        return module_index.get_module_names()
    else:
        return list()


def create_modulemd_defaults(artifact, artifact_url):
    """Parse and create modulemd-defaults if not exists."""
    defaults_index = mmdlib.ModuleIndex.new()
    modulemds = _get_modules(artifact.file, defaults_index)
    for modulemd in modulemds:
        module = defaults_index.get_module(modulemd)
        default = module.get_defaults()
        modulemd_default = dict()
        if default:
            modulemd_default['module'] = modulemd
            streams = default.get_streams_with_default_profiles()
            streams_dict = dict()
            for stream in streams:
                streams_dict[stream] = default.get_default_profiles_for_stream(stream)
            modulemd_default['streams'] = json.dumps(streams)
            modulemd_default['profiles'] = json.dumps(streams_dict)
            modulemd_default['_artifact'] = artifact_url
            modulemd_default['_relative_path'] = artifact.file.name
            exists = ModulemdDefaults.objects.filter(
                module=modulemd_default['module'],
                streams=modulemd_default['streams'],
                profiles=modulemd_default['profiles']
            )
            if not len(exists):
                serializer = ModulemdDefaultsSerializer(data=modulemd_default)
                serializer.is_valid(raise_exception=True)
                serializer.save()
