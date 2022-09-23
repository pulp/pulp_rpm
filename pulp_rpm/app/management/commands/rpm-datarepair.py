import os.path
from gettext import gettext as _
from tempfile import TemporaryDirectory

from django.core.management import BaseCommand, CommandError

from pulpcore.plugin.models import ContentArtifact
from pulp_rpm.app.models import Modulemd, ModulemdDefaults, Package  # noqa

import gi

gi.require_version("Modulemd", "2.0")
from gi.repository import Modulemd as mmdlib  # noqa: E402


class Command(BaseCommand):
    """
    Django management command for repairing RPM metadata in the Pulp database.
    """

    help = _(__doc__)

    def add_arguments(self, parser):
        """Set up arguments."""
        parser.add_argument("issue", help=_("The github issue # of the issue to be fixed."))

    def handle(self, *args, **options):
        """Implement the command."""
        issue = options["issue"]

        if issue == "2460":
            self.repair_2460()
        elif issue == "2735":
            self.repair_2735()
        else:
            raise CommandError(_("Unknown issue: '{}'").format(issue))

    def repair_2460(self):
        """Perform data repair for issue #2460."""

        def fix_package(package):
            def fix_requirement(require):
                (name, flags, epoch, version, release, pre) = require
                if "&#38;#38;" in name:
                    fixed_name = name.replace("&#38;#38;", "&")
                    return (fixed_name, flags, epoch, version, release)
                else:
                    return require

            package.requires = [fix_requirement(require) for require in package.provides]

        # This is the only known affected package, we can update this later if we find more.
        packages = Package.objects.filter(name="bpg-algeti-fonts")

        for package in packages:
            fix_package(package)
            package.save()

    def repair_2735(self):
        """Perform data repair for issue #2735."""

        def create_default_snippet(default):
            """Recreate modulemd-default from DB data."""
            # There is only one version of Defaults (1)
            module_default = mmdlib.Defaults.new(1, default.module)
            module_default.set_default_stream(default.stream)
            for profile in default.profiles:
                module_default.add_default_profile_for_stream(default.stream, profile)

            temp_index = mmdlib.ModuleIndex.new()
            temp_index.add_defaults(module_default)
            return temp_index.dump_to_string()

        def create_module_snippet(modulemd, new_fields=True):
            """Recreate modulemd from DB data."""
            # as we don't store Modulemd document version lets default to 2 (as most used)
            module_stream = mmdlib.ModuleStream.new(2, modulemd.name, modulemd.stream)

            module_stream.set_context(modulemd.context)
            module_stream.set_arch(modulemd.arch)
            module_stream.set_summary(modulemd.name)
            module_stream.set_description(modulemd.name)
            if new_fields:
                module_stream.set_description(modulemd.description)
            module_stream.add_module_license("info missing")
            module_stream.add_content_license("info missing")
            module_stream.set_version(float(modulemd.version))

            if modulemd.static_context:
                module_stream.set_static_context()

            for rpm_artifact in modulemd.artifacts:
                module_stream.add_rpm_artifact(rpm_artifact)

            module_dependencies = list()
            for depenedency in modulemd.dependencies:

                for dep in depenedency.keys():
                    module_dep = mmdlib.Dependencies.new()
                    module_dep.set_empty_runtime_dependencies_for_module(dep)
                    for run_dep in depenedency[dep]:
                        module_dep.add_runtime_stream(dep, run_dep)
                    module_dependencies.append(module_dep)
            for dependency in module_dependencies:
                module_stream.add_dependencies(dependency)

            if new_fields:
                module_profiles = list()
                for profile in modulemd.profiles:
                    module_profile = mmdlib.Profile.new(profile)
                    module_profile.set_description(profile)
                    for profile_pkg in modulemd.profiles[profile]:
                        module_profile.add_rpm(profile_pkg)
                    module_profiles.append(module_profile)
                for profile in module_profiles:
                    module_stream.add_profile(profile)

            temp_index = mmdlib.ModuleIndex.new()
            temp_index.add_module_stream(module_stream)
            return temp_index.dump_to_string()

        def recreate_artifact(module, artifact, defaults=False):
            with TemporaryDirectory():
                ca = ContentArtifact.objects.filter(artifact=artifact).first()
                old_artifact = ca.artifact
                ca.artifact = None
                ca.save()
                old_artifact.delete()

                # import helper function here as only when modulemd has artifact
                # it has this function
                from pulp_rpm.app.modulemd import _create_snippet  # noqa

                if defaults:
                    snippet = create_default_snippet(module)
                else:
                    snippet = create_module_snippet(module, new_fields=False)
                new_artifact = _create_snippet(snippet)
                new_artifact.save()
                ca.artifact = new_artifact
                ca.save()

        # Find out if we need save snippet to DB or to artifact
        modulemd_has_snippet = hasattr(Modulemd, "snippet")
        defaults_has_snippet = hasattr(ModulemdDefaults, "snippet")

        for default in ModulemdDefaults.objects.all():
            if defaults_has_snippet and not default.snippet:
                default.snippet = create_default_snippet(default)
            else:
                artifact = default._artifacts.all().first()
                if artifact and not os.path.exists(artifact.file.path):
                    recreate_artifact(default, artifact, defaults=True)

        for modulemd in Modulemd.objects.all():
            if modulemd_has_snippet and not modulemd.snippet:
                modulemd.snippet = create_module_snippet(modulemd)
            else:
                artifact = modulemd._artifacts.all().first()
                if artifact and not os.path.exists(artifact.file.path):
                    recreate_artifact(modulemd, artifact)
