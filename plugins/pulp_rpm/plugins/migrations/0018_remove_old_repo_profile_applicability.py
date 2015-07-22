"""
There is a bug[1] related to errata applicability where extra errata were being
applied. While newly generated errata applicability will not have this bug, the
older incorrect cached data needs to be removed.

[1] https://bugzilla.redhat.com/show_bug.cgi?id=1171280

"""
import logging

from pulp.server.db import connection


_logger = logging.getLogger(__name__)


def migrate(*args, **kwargs):
    """
    Remove the repo_profile_applicability collection.

    :param args:   Unused
    :type  args:   list
    :param kwargs: Unused
    :type  kwargs: dict
    """
    rpa_collection = connection.get_collection('repo_profile_applicability')
    rpa_collection.drop()
