from django_filters import CharFilter
from drf_spectacular.utils import extend_schema
from pulpcore.plugin.serializers import AsyncOperationResponseSerializer
from pulpcore.plugin.tasking import dispatch, general_create
from pulpcore.plugin.viewsets import (
    ContentFilter,
    OperationPostponedResponse,
    SingleArtifactContentUploadViewSet,
)

from pulp_rpm.app import tasks as rpm_tasks
from pulp_rpm.app.models import Package
from pulp_rpm.app.serializers import MinimalPackageSerializer, PackageSerializer


class PackageFilter(ContentFilter):
    """
    FilterSet for Package.
    """

    sha256 = CharFilter(field_name="_artifacts__sha256")
    filename = CharFilter(field_name="content_artifact__relative_path")

    class Meta:
        model = Package
        fields = {
            "name": ["exact", "in", "ne", "contains", "startswith"],
            "epoch": ["exact", "in", "ne"],
            "version": ["exact", "in", "ne"],
            "release": ["exact", "in", "ne", "contains", "startswith"],
            "arch": ["exact", "in", "ne", "contains", "startswith"],
            "pkgId": ["exact", "in"],
            "checksum_type": ["exact", "in", "ne"],
        }


class PackageViewSet(SingleArtifactContentUploadViewSet):
    """
    A ViewSet for Package.

    Define endpoint name which will appear in the API endpoint for this content type.
    For example::
        http://pulp.example.com/pulp/api/v3/content/rpm/packages/

    Also specify queryset and serializer for Package.
    """

    endpoint_name = "packages"
    queryset = Package.objects.prefetch_related("_artifacts")
    serializer_class = PackageSerializer
    minimal_serializer_class = MinimalPackageSerializer
    filterset_class = PackageFilter

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list", "retrieve"],
                "principal": "authenticated",
                "effect": "allow",
            },
            {
                "action": ["create"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_required_repo_perms_on_upload:rpm.modify_content_rpmrepository",
                    "has_required_repo_perms_on_upload:rpm.view_rpmrepository",
                ],
            },
        ],
        "queryset_scoping": {"function": "scope_queryset"},
    }

    @extend_schema(
        description="Trigger an asynchronous task to create an RPM package,"
        "optionally create new repository version.",
        responses={202: AsyncOperationResponseSerializer},
    )
    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # common task params
        task_args = {
            "app_label": self.queryset.model._meta.app_label,
            "serializer_name": serializer.__class__.__name__,
        }
        task_exclusive = [
            item
            for item in (serializer.validated_data.get(key) for key in ("upload", "repository"))
            if item
        ]

        # handle signing, if required
        sign_package = serializer.validated_data.pop("sign_package")
        if sign_package is True:
            task_fn = rpm_tasks.signing.sign_and_create
            # 'repository' is being popped because the 'validated_data' will create
            # an intermediary Artifact to be send to the task. The task will
            # create a new signed Artifact, so the intermediate should be orphan-cleaned-up
            associated_repo = serializer.validated_data.pop("repository")
            task_args["signing_service_pk"] = associated_repo.package_signing_service.pk
        else:
            task_fn = general_create

        task_payload = self.init_content_data(serializer, request)
        task = dispatch(
            task_fn,
            exclusive_resources=task_exclusive,
            args=tuple(task_args.values()),
            kwargs={
                "data": task_payload,
                "context": self.get_deferred_context(request),
            },
        )
        return OperationPostponedResponse(task, request)
