import logging

from gettext import gettext as _

from celery import shared_task

from pulpcore.plugin.models import Repository  # , RepositoryVersion
from pulpcore.plugin.tasking import UserFacingTask  # , WorkingDirectory

from pulp_rpm.app.models import RpmImporter


log = logging.getLogger(__name__)


@shared_task(base=UserFacingTask)
def synchronize(importer_pk, repository_pk):
    """
    Create a new version of the repository that is synchronized with the remote
    as specified by the importer.

    Args:
        importer_pk (str): The importer PK.
        repository_pk (str): The repository PK.

    Raises:
        ValueError: When feed_url is empty.
    """
    importer = RpmImporter.objects.get(pk=importer_pk)
    repository = Repository.objects.get(pk=repository_pk)
    # base_version = RepositoryVersion.latest(repository)

    if not importer.feed_url:
        raise ValueError(_('An importer must have a feed_url specified to synchronize.'))

    log.info(
        _('Synchronizing: repository=%(r)s importer=%(p)s'),
        {
            'r': repository.name,
            'p': importer.name
        })

    # implement sync here
