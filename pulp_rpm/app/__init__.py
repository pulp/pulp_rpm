from pulpcore.plugin import PulpPluginAppConfig


class PulpRpmPluginAppConfig(PulpPluginAppConfig):
    """
    Entry point for pulp_rpm plugin.
    """

    name = "pulp_rpm.app"
    label = "rpm"
    version = "3.30.2.dev"
    python_package_name = "pulp-rpm"
    domain_compatible = True
