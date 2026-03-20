"""
Check `Plugin Writer's Guide`_ for more details.

.. _Plugin Writer's Guide:
    http://docs.pulpproject.org/plugins/plugin-writer/index.html
"""

from datetime import timedelta

DRF_ACCESS_POLICY = {
    "dynaconf_merge_unique": True,
    "reusable_conditions": ["pulp_rpm.app.access_policy"],
}
INSTALLED_APPS = ["django_readonly_field", "dynaconf_merge"]
ALLOW_AUTOMATIC_UNSAFE_ADVISORY_CONFLICT_RESOLUTION = False
DEFAULT_ULN_SERVER_BASE_URL = "https://linux-update.oracle.com/"
KEEP_CHANGELOG_LIMIT = 10
SOLVER_DEBUG_LOGS = True
RPM_METADATA_USE_REPO_PACKAGE_TIME = False
NOCACHE_LIST = ["repomd.xml", "repomd.xml.asc", "repomd.xml.key"]
PRUNE_WORKERS_MAX = 5

# The time in seconds that a non-latest distribution's publication will serve
# as fallback in content requests
RPM_PUBLICATION_CACHE_DURATION = int(timedelta(days=3).total_seconds())

# workaround for: https://github.com/pulp/pulp_rpm/issues/4125
SPECTACULAR_SETTINGS__OAS_VERSION = "3.0.1"
MAX_PACKAGE_SIGNING_WORKERS = 5
