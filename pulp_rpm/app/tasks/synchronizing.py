from gettext import gettext as _
import logging


from pulpcore.plugin.models import Repository  # , RepositoryVersion
# from pulpcore.plugin.tasking import WorkingDirectory

from pulp_rpm.app.models import RpmRemote

log = logging.getLogger(__name__)


def synchronize(remote_pk, repository_pk):
    """
    Create a new version of the repository that is synchronized with the remote
    as specified by the remote.

    Args:
        remote_pk (str): The remote PK.
        repository_pk (str): The repository PK.

    Raises:
        ValueError: When remote has no url specified.
    """
    remote = RpmRemote.objects.get(pk=remote_pk)
    repository = Repository.objects.get(pk=repository_pk)
    # base_version = RepositoryVersion.latest(repository)

    if not remote.url:
        raise ValueError(_('A remote must have a url specified to synchronize.'))

    log.info(_('Synchronizing: repository={r} remote={p}').format(
        r=repository.name, p=remote.name))
