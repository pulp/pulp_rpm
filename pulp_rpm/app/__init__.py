from pulpcore.plugin import PulpPluginAppConfig


class PulpRpmPluginAppConfig(PulpPluginAppConfig):
    """
    Entry point for pulp_rpm plugin.
    """

    name = "pulp_rpm.app"
    label = "rpm"
    version = "3.28.0.dev"
    python_package_name = "pulp-rpm"
    domain_compatible = True

    def ready(self):
        # include drf-spectacular Extension module
        import pulp_rpm.app.schema.extensions  # noqa: E402, F401

        super().ready()
