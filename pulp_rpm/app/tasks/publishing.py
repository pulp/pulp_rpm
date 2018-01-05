import logging

from gettext import gettext as _

from celery import shared_task

from pulpcore.plugin.models import (
    RepositoryVersion,
    # Publication,
    # PublishedArtifact,
    # PublishedMetadata,
    # RemoteArtifact,
)

from pulpcore.plugin.tasking import UserFacingTask  # , WorkingDirectory

from pulp_rpm.app.models import RpmPublisher

log = logging.getLogger(__name__)


@shared_task(base=UserFacingTask)
def publish(publisher_pk, repository_version_pk):
    """
    Use provided publisher to create a Publication based on a RepositoryVersion.

    Args:
        publisher_pk (str): Use the publish settings provided by this publisher.
        repository_version_pk (str): Create a publication from this repository version.
    """
    publisher = RpmPublisher.objects.get(pk=publisher_pk)
    repository_version = RepositoryVersion.objects.get(pk=repository_version_pk)

    log.info(
        _('Publishing: repository=%(repository)s, version=%(version)d, publisher=%(publisher)s'),
        {
            'repository': repository_version.repository.name,
            'version': repository_version.number,
            'publisher': publisher.name,
        })

    # implement publish here
