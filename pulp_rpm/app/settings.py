"""
Check `Plugin Writer's Guide`_ for more details.

.. _Plugin Writer's Guide:
    http://docs.pulpproject.org/plugins/plugin-writer/index.html
"""

INSTALLED_APPS = ["django_readonly_field", "dynaconf_merge"]
ALLOW_AUTOMATIC_UNSAFE_ADVISORY_CONFLICT_RESOLUTION = False
DEFAULT_ULN_SERVER_BASE_URL = "https://linux-update.oracle.com/"
KEEP_CHANGELOG_LIMIT = 10
