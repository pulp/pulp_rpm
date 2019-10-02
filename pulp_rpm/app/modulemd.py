import json
import os
import tempfile

from pulpcore.app.models import CreatedResource
from pulpcore.app.models.content import Artifact, ContentArtifact
from pulpcore.app.models.repository import RepositoryVersion
from pulp_rpm.app.constants import PULP_MODULE_ATTR, PULP_MODULEDEFAULTS_ATTR
from pulp_rpm.app.models import Modulemd, ModulemdDefaults

import gi
gi.require_version('Modulemd', '2.0')
from gi.repository import Modulemd as mmdlib  # noqa: E402


def _create_snippet(snippet_string):
    """
    Create snippet of modulemd[-defaults] as artifact.

    Args:
        snippet_string (string):
            Snippet with modulemd[-defaults] yaml

    Returns:
        Snippet as unsaved Artifact object

    """
    tmp_file = tempfile.NamedTemporaryFile(dir=os.getcwd(), delete=False)
    with open(tmp_file.name, 'w') as snippet:
        snippet.write(snippet_string)
    return Artifact.init_and_validate(tmp_file.name)


def parse_modulemd(module_names, module_index):
    """
    Get modulemd NSVCA, artifacts, dependencies.

    Args:
        module_names (list):
            list of modulemd names
        module_index (mmdlib.ModuleIndex):
            libmodulemd index object

    """
    ret = list()
    for module in module_names:
        for s in module_index.get_module(module).get_all_streams():
            modulemd = dict()
            modulemd[PULP_MODULE_ATTR.NAME] = s.props.module_name
            modulemd[PULP_MODULE_ATTR.STREAM] = s.props.stream_name
            modulemd[PULP_MODULE_ATTR.VERSION] = s.props.version
            modulemd[PULP_MODULE_ATTR.CONTEXT] = s.props.context
            modulemd[PULP_MODULE_ATTR.ARCH] = s.props.arch
            modulemd[PULP_MODULE_ATTR.ARTIFACTS] = json.dumps(s.get_rpm_artifacts())

            dependencies_list = s.get_dependencies()
            dependencies = dict()
            for dep in dependencies_list:
                d_list = dep.get_runtime_modules()
                for dependency in d_list:
                    dependencies[dependency] = dep.get_runtime_streams(dependency)
            modulemd[PULP_MODULE_ATTR.DEPENDENCIES] = json.dumps(dependencies)
            # create yaml snippet for this modulemd stream
            temp_index = mmdlib.ModuleIndex.new()
            temp_index.add_module_stream(s)
            artifact = _create_snippet(temp_index.dump_to_string())
            modulemd["artifact"] = artifact
            ret.append(modulemd)
    return ret


def parse_defaults(module_index):
    """
    Get modulemd-defaults.

    Args:
        module_index (mmdlib.ModuleIndex):
            libmodulemd index object

    Returns:
        list of modulemd-defaults as dict

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
            artifact = _create_snippet(temp_index.dump_to_string())
            ret.append({
                PULP_MODULEDEFAULTS_ATTR.MODULE: modulemd.get_module_name(),
                PULP_MODULEDEFAULTS_ATTR.STREAM: default_stream,
                PULP_MODULEDEFAULTS_ATTR.PROFILES: json.dumps(default_profile),
                PULP_MODULEDEFAULTS_ATTR.DIGEST: artifact.sha256,
                'artifact': artifact
            })
    return ret


def upload_modulemd(yaml_string, repository):
    """
    Parse modulemd and modulemd-defaults from uploaded file.

    Args:
        yaml_string (string):
            content of modules.yaml
        repository (pulpcore.app.models.Repository):
            repository object

    """
    if repository:
        content_to_add = list()

    uploaded_index = mmdlib.ModuleIndex.new()
    uploaded_index.update_from_string(yaml_string, True)

    modulemd_names = uploaded_index.get_module_names()
    modulemd_dict = parse_modulemd(modulemd_names, uploaded_index)

    for modulemd in modulemd_dict:
        artifact = modulemd.pop('artifact')
        if len(Modulemd.objects.filter(**modulemd)):
            continue
        module = Modulemd(**modulemd)
        module.save()

        if len(Artifact.objects.filter(sha256=artifact.sha256)):
            artifact = Artifact.objects.get(sha256=artifact.sha256)
        artifact.save()

        relative_path = '{}{}{}{}{}snippet'.format(
            modulemd[PULP_MODULE_ATTR.NAME], modulemd[PULP_MODULE_ATTR.STREAM],
            modulemd[PULP_MODULE_ATTR.VERSION], modulemd[PULP_MODULE_ATTR.CONTEXT],
            modulemd[PULP_MODULE_ATTR.ARCH]
        )

        ca = ContentArtifact.objects.create(
            artifact=artifact,
            relative_path=relative_path,
            content=module
        )
        ca.save()
        resource_artifact = CreatedResource(content_object=module)
        resource_modulemd = CreatedResource(content_object=artifact)
        resource_artifact.save()
        resource_modulemd.save()

        if repository:
            content_to_add.append(module.pk)

    modulemd_defaults_all = parse_defaults(uploaded_index)
    for default in modulemd_defaults_all:
        artifact = default.pop('artifact')
        if len(ModulemdDefaults.objects.filter(**default)):
            continue
        module_default = ModulemdDefaults(**default)
        module_default.save()

        if len(Artifact.objects.filter(sha256=artifact.sha256)):
            artifact = Artifact.objects.get(sha256=artifact.sha256)
        artifact.save()
        relative_path = '{}{}snippet'.format(
            default[PULP_MODULEDEFAULTS_ATTR.MODULE],
            default[PULP_MODULEDEFAULTS_ATTR.STREAM]
        )
        ca = ContentArtifact.objects.create(
            artifact=artifact,
            relative_path=relative_path,
            content=module_default
        )
        ca.save()
        resource_artifact = CreatedResource(content_object=module_default)
        resource_default = CreatedResource(content_object=artifact)
        resource_artifact.save()
        resource_default.save()

        if repository:
            content_to_add.append(module_default.pk)

    if repository and content_to_add:
        with RepositoryVersion.create(repository) as new_repository_version:
            new_repository_version.add_content(Modulemd.objects.filter(pk__in=content_to_add))
            new_repository_version.add_content(
                ModulemdDefaults.objects.filter(pk__in=content_to_add)
            )
