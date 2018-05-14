from gettext import gettext as _
import logging

from pulpcore.plugin.models import (
    RepositoryVersion,
    # Publication,
    # PublishedArtifact,
    # PublishedMetadata,
    # RemoteArtifact,
)

# from pulpcore.plugin.tasking import WorkingDirectory

from pulp_rpm.app.models import RpmPublisher

log = logging.getLogger(__name__)


def publish(publisher_pk, repository_version_pk):
    """
    Use provided publisher to create a Publication based on a RepositoryVersion.

    Args:
        publisher_pk (str): Use the publish settings provided by this publisher.
        repository_version_pk (str): Create a publication from this repository version.
    """
    publisher = RpmPublisher.objects.get(pk=publisher_pk)
    repository_version = RepositoryVersion.objects.get(pk=repository_version_pk)

    log.info(_('Publishing: repository={repo}, version={version}, publisher={publisher}').format(
        repo=repository_version.repository.name,
        version=repository_version.number,
        publisher=publisher.name,
    ))

    # implement publish here
