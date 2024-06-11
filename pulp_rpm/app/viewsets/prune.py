from drf_spectacular.utils import extend_schema
from django.conf import settings
from rest_framework.viewsets import ViewSet

from pulpcore.plugin.viewsets import TaskGroupOperationResponse
from pulpcore.plugin.models import TaskGroup
from pulpcore.plugin.serializers import TaskGroupOperationResponseSerializer
from pulp_rpm.app.serializers import PrunePackagesSerializer
from pulp_rpm.app.tasks import prune_packages
from pulpcore.plugin.tasking import dispatch


class PrunePackagesViewSet(ViewSet):
    """
    Viewset for prune-old-Packages endpoint.
    """

    serializer_class = PrunePackagesSerializer

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["prune_packages"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_repository_model_or_domain_or_obj_perms:rpm.modify_content_rpmrepository",
                    "has_repository_model_or_domain_or_obj_perms:rpm.view_rpmrepository",
                ],
            },
        ],
    }

    @extend_schema(
        description="Trigger an asynchronous old-Package-prune operation.",
        responses={202: TaskGroupOperationResponseSerializer},
    )
    def prune_packages(self, request):
        """
        Triggers an asynchronous old-Package-purge operation.

        This returns a task-group that contains a "master" task that dispatches one task
        per repo being pruned. This allows repositories to become available for other
        processing as soon as their task completes, rather than having to wait for *all*
        repositories to be pruned.
        """
        serializer = PrunePackagesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        repos = serializer.validated_data.get("repo_hrefs", [])
        repos_to_prune_pks = []
        for repo in repos:
            repos_to_prune_pks.append(repo.pk)

        uri = "/api/v3/rpm/prune/"
        if settings.DOMAIN_ENABLED:
            uri = f"/{request.pulp_domain.name}{uri}"
        exclusive_resources = [uri, f"pdrn:{request.pulp_domain.pulp_id}:rpm:prune"]

        task_group = TaskGroup.objects.create(description="Prune old Packages.")

        dispatch(
            prune_packages,
            exclusive_resources=exclusive_resources,
            task_group=task_group,
            kwargs={
                "repo_pks": repos_to_prune_pks,
                "keep_days": serializer.validated_data["keep_days"],
                "dry_run": serializer.validated_data["dry_run"],
            },
        )
        return TaskGroupOperationResponse(task_group, request)
