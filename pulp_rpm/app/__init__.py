from pulpcore.plugin import PulpPluginAppConfig


class PulpRpmPluginAppConfig(PulpPluginAppConfig):
    name = 'pulp_rpm.app'
    label = 'pulp_rpm'
