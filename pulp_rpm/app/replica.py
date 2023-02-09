from pulpcore.plugin.replica import Replicator

from pulp_glue.rpm.context import (
    PulpRpmDistributionContext,
    PulpRpmPublicationContext,
    PulpRpmRepositoryContext,
)


from pulp_rpm.app.models import RpmDistribution, RpmRemote, RpmRepository
from pulp_rpm.app.tasks import synchronize as rpm_synchronize


class RpmReplicator(Replicator):
    repository_ctx_cls = PulpRpmRepositoryContext
    distribution_ctx_cls = PulpRpmDistributionContext
    publication_ctx_cls = PulpRpmPublicationContext
    app_label = "rpm"
    remote_model_cls = RpmRemote
    repository_model_cls = RpmRepository
    distribution_model_cls = RpmDistribution
    distribution_serializer_name = "RpmDistributionSerializer"
    repository_serializer_name = "RpmRepositorySerializer"
    remote_serializer_name = "RpmRemoteSerializer"
    sync_task = rpm_synchronize

    def repository_extra_fields(self, remote):
        """Returns a dictionary where each key is a field on an RpmRemote."""
        return dict(autopublish=False)

    def sync_params(self, repository, remote):
        """Returns a dictionary where key is a parameter for the sync task."""
        return dict(
            remote_pk=remote.pk,
            repository_pk=repository.pk,
            sync_policy="mirror_complete",
            skip_types=[],
            optimize=True,
        )


REPLICATION_ORDER = [RpmReplicator]
