from django_filters import CharFilter
from pulpcore.app import tasks as base_tasks
from pulpcore.app.response import OperationPostponedResponse
from pulpcore.plugin.files import PulpTemporaryUploadedFile
from pulpcore.plugin.viewsets import ContentFilter, SingleArtifactContentUploadViewSet
from pulpcore.tasking.tasks import dispatch

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

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # common task params
        task_args = {
            "app_label": self.queryset.model._meta.app_label,
            "serializer_name": serializer.__class__.__name__,
        }

        # handle signing, if required
        sign_package = serializer.validated_data.get("sign_package")
        pulp_tmp_file = serializer.validated_data.get("file")
        if sign_package is True and pulp_tmp_file:
            repo = serializer.validated_data["repository"]

            task_fn = rpm_tasks.uploading.sign_and_create
            task_args["temporary_file_path"] = pulp_tmp_file.temporary_file_path()
            task_args["signing_service_pk"] = repo.package_signing_service.pk
            task_exclusive = [
                item
                for item in (serializer.validated_data.get(key) for key in ("upload", "repository"))
                if item
            ]
            task_payload = {
                k: v for k, v in request.data.items() if k not in ("file", "sign_package")
            }
        else:
            task_fn = base_tasks.base.general_create
            task_exclusive = [
                item
                for item in (serializer.validated_data.get(key) for key in ("upload", "repository"))
                if item
            ]
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
