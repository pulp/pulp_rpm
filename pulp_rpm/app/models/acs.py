from logging import getLogger

from pulpcore.plugin.models import AlternateContentSource
from pulp_rpm.app.models import RpmRemote


log = getLogger(__name__)


class RpmAlternateContentSource(AlternateContentSource):
    """
    Alternate Content Source for 'RPM" content.
    """

    TYPE = "rpm"
    REMOTE_TYPES = [RpmRemote]

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
