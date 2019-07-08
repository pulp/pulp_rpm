import gzip
import json
import tempfile

from django.db.utils import IntegrityError
from pulpcore.app.models.content import Artifact
from pulpcore.plugin.models import CreatedResource
from pulp_rpm.app.constants import PULP_MODULE_ATTR, MODULEMD_MODULE_ATTR
from pulp_rpm.app.models import Modulemd, ModulemdDefaults
from pulp_rpm.app.serializers import ModulemdSerializer, ModulemdDefaultsSerializer

import gi
gi.require_version('Modulemd', '2.0')
from gi.repository import Modulemd as mmdlib  # noqa: E402


def _create_snippet(snippet_string):
    """Create snippet of modulemd[-defaults] as artifact."""
    tmp_file = tempfile.NamedTemporaryFile()
    with open(tmp_file.name, 'w') as f:
        f.write(snippet_string)
    artifact = Artifact.init_and_validate(tmp_file.name)
    try:
        artifact.save()
        return artifact
    except IntegrityError:
        artifact = Artifact.objects.get(sha256=artifact.sha256)
        return artifact


def _get_modulemd_names(modulemd_yaml, module_index):
    """Get modulemd names."""
    ret, fails = module_index.update_from_string(modulemd_yaml, True)
    if ret:
        return module_index.get_module_names()
    else:
        return list()


def _parse_modulemd(modules, module_index):
    """Get modulemd NSVCA, artifacts, dependencies."""
    ret = list()
    for module in modules:
        m = module_index.get_module(module)
        for s in m.get_all_streams():
            tmp = dict()
            tmp[PULP_MODULE_ATTR.NAME] = s.props.module_name
            tmp[PULP_MODULE_ATTR.STREAM] = s.props.stream_name
            tmp[PULP_MODULE_ATTR.VERSION] = s.props.version
            tmp[PULP_MODULE_ATTR.CONTEXT] = s.props.context
            tmp[PULP_MODULE_ATTR.ARCH] = s.props.arch
            tmp[PULP_MODULE_ATTR.ARTIFACTS] = json.dumps(s.get_rpm_artifacts())

            deps_list = s.get_dependencies()
            deps = dict()
            for dep in deps_list:
                d_list = dep.get_runtime_modules()
                for dependency in d_list:
                    deps[dependency] = dep.get_runtime_streams(dependency)
            tmp[PULP_MODULE_ATTR.DEPENDENCIES] = json.dumps(deps)
            # create yaml snippet for this modulemd stream
            temp_index = mmdlib.ModuleIndex.new()
            temp_index.add_module_stream(s)
            artifact = _create_snippet(temp_index.dump_to_string())
            tmp["_artifact"] = "/pulp/api/v3/artifacts/{}/".format(artifact.pk)
            tmp["_relative_path"] = artifact.file.name
            ret.append(tmp)
    return ret


def _parse_defaults(module_index):
    """Get modulemd-defaults."""
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
            artifact = _create_snippet(temp_index.dump_to_string())
            ret.append({
                'module': modulemd.get_module_name(),
                'stream': default_stream,
                'profiles': json.dumps(default_profile),
                'digest': artifact.sha1,
                '_artifact': "/pulp/api/v3/artifacts/{}/".format(artifact.pk),
                '_relative_path': artifact.file.name
            })
    return ret


def create_modulemd(modulemd_artifact, filename):
    """Parse and create modulemd and modulemd-defaults."""
    if filename.endswith('.gz'):
        modulemd_yaml = gzip.decompress(modulemd_artifact.file.read()).decode()
    else:
        modulemd_yaml = modulemd_artifact.file.read().decode()
    Artifact.objects.get(pk=modulemd_artifact.pk).delete()
    # modulemd
    module_index = mmdlib.ModuleIndex.new()
    modulemds = _get_modulemd_names(modulemd_yaml, module_index)
    for modulemd in _parse_modulemd(modulemds, module_index):
        exists = Modulemd.objects.filter(
            name=modulemd[MODULEMD_MODULE_ATTR.NAME],
            version=modulemd[MODULEMD_MODULE_ATTR.VERSION],
            stream=modulemd[MODULEMD_MODULE_ATTR.STREAM],
            context=modulemd[MODULEMD_MODULE_ATTR.CONTEXT],
            arch=modulemd[MODULEMD_MODULE_ATTR.ARCH]
        )
        if len(exists) > 0:
            continue
        serializer = ModulemdSerializer(data=modulemd)
        serializer.is_valid(raise_exception=True)
        modulemd_resource = serializer.save()
        resource = CreatedResource(content_object=modulemd_resource)
        resource.save()
    # modulemd-defaults
    defaults = _parse_defaults(module_index)
    for modulemd_default in defaults:
        exists = ModulemdDefaults.objects.filter(
            module=modulemd_default['module'],
            stream=modulemd_default['stream'],
            profiles=modulemd_default['profiles']
        )
        if len(exists) > 0:
            continue
        serializer = ModulemdDefaultsSerializer(data=modulemd_default)
        serializer.is_valid(raise_exception=True)
        modulemd_default_resource = serializer.save()
        resource = CreatedResource(content_object=modulemd_default_resource)
        resource.save()
