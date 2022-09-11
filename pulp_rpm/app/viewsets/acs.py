import os

from django.utils.timezone import now
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404

from pulpcore.plugin.models import AlternateContentSourcePath, TaskGroup
from pulpcore.plugin.tasking import dispatch
from pulpcore.plugin.serializers import (
    TaskGroupOperationResponseSerializer,
)
from pulpcore.plugin.viewsets import (
    AlternateContentSourceViewSet,
    TaskGroupOperationResponse,
)

from pulp_rpm.app import tasks
from pulp_rpm.app.constants import SYNC_POLICIES
from pulp_rpm.app.models import (
    RpmAlternateContentSource,
    RpmRepository,
)
from pulp_rpm.app.serializers import (
    RpmAlternateContentSourceSerializer,
    RpmRepositorySyncURLSerializer,
)


class RpmAlternateContentSourceViewSet(AlternateContentSourceViewSet):
    """
    ViewSet for ACS.
    """

    endpoint_name = "rpm"
    queryset = RpmAlternateContentSource.objects.all()
    serializer_class = RpmAlternateContentSourceSerializer

    @extend_schema(
        description="Trigger an asynchronous task to create Alternate Content Source content.",
        responses={202: TaskGroupOperationResponseSerializer},
        request=None,
    )
    @action(methods=["post"], detail=True)
    def refresh(self, request, pk):
        """
        Refresh ACS metadata.
        """
        acs = get_object_or_404(RpmAlternateContentSource, pk=pk)
        acs_paths = AlternateContentSourcePath.objects.filter(alternate_content_source=pk)
        task_group = TaskGroup.objects.create(
            description=f"Refreshing {acs_paths.count()} alternate content source path(s)."
        )

        # Get required defaults for sync operation
        optimize = RpmRepositorySyncURLSerializer().data["optimize"]
        skip_types = RpmRepositorySyncURLSerializer().data["skip_types"]

        for acs_path in acs_paths:
            # Create or get repository for the path
            repo_data = {
                "name": f"{acs.name}--{acs_path.pk}--repository",
                "retain_repo_versions": 1,
                "user_hidden": True,
            }
            repo, created = RpmRepository.objects.get_or_create(**repo_data)
            if created:
                acs_path.repository = repo
                acs_path.save()
            acs_url = (
                os.path.join(acs.remote.url, acs_path.path) if acs_path.path else acs.remote.url
            )

            # Dispatching ACS path to own task and assign it to common TaskGroup
            dispatch(
                tasks.synchronize,
                shared_resources=[acs.remote, acs],
                task_group=task_group,
                kwargs={
                    "remote_pk": str(acs.remote.pk),
                    "repository_pk": str(acs_path.repository.pk),
                    "sync_policy": SYNC_POLICIES.MIRROR_CONTENT_ONLY,
                    "skip_types": skip_types,
                    "optimize": optimize,
                    "url": acs_url,
                },
            )

        # Update TaskGroup that all child task are dispatched
        task_group.finish()

        acs.last_refreshed = now()
        acs.save()

        return TaskGroupOperationResponse(task_group, request)
