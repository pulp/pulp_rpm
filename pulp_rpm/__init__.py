import pkg_resources

__version__ = pkg_resources.get_distribution("pulp_rpm").version


default_app_config = 'pulp_rpm.app.PulpRpmPluginAppConfig'
