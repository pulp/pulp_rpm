from django_filters import CharFilter
from drf_spectacular.utils import extend_schema
from pulpcore.plugin.models import PulpTemporaryFile
from pulpcore.plugin.serializers import AsyncOperationResponseSerializer
from pulpcore.plugin.tasking import dispatch
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
            {
                "action": ["set_label", "unset_label"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_domain_perms:core.manage_content_labels",
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
        # validation decides if we want to sign and set that in the context space
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.context["sign_package"] is False:
            return super().create(request)

        # signing case
        request.data.pop("file")
        validated_data = serializer.validated_data
        temp_uploaded_file = validated_data["file"]
        signing_service_pk = validated_data["repository"].package_signing_service.pk
        signing_fingerprint = validated_data["repository"].package_signing_fingerprint

        # dispatch signing task
        pulp_temp_file = PulpTemporaryFile(file=temp_uploaded_file.temporary_file_path())
        pulp_temp_file.save()
        task_args = {
            "app_label": self.queryset.model._meta.app_label,
            "serializer_name": serializer.__class__.__name__,
            "signing_service_pk": signing_service_pk,
            "signing_fingerprint": signing_fingerprint,
            "temporary_file_pk": pulp_temp_file.pk,
        }
        task_payload = {k: v for k, v in request.data.items()}
        task_exclusive = [
            serializer.validated_data.get("upload"),
            serializer.validated_data.get("repository"),
        ]
        task = dispatch(
            rpm_tasks.signing.sign_and_create,
            exclusive_resources=task_exclusive,
            args=tuple(task_args.values()),
            kwargs={
                "data": task_payload,
                "context": self.get_deferred_context(request),
            },
        )
        return OperationPostponedResponse(task, request)
