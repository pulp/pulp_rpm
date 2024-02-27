from django_filters import CharFilter
from pulpcore.plugin.viewsets import ContentFilter, SingleArtifactContentUploadViewSet

from pulpcore.app.files import PulpTemporaryUploadedFile
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

    def init_content_data(self, serializer, request):
        # Handle package signing on file-upload
        sign_package = serializer.validated_data.get("sign_package")
        pulp_tmp_file = serializer.validated_data.get("file")
        if sign_package and pulp_tmp_file:
            repo = serializer.validated_data["repository"]
            repo.package_signing_service.sign(pulp_tmp_file.temporary_file_path())
            request.data["file"] = PulpTemporaryUploadedFile.from_file(pulp_tmp_file)
        return super().init_content_data(serializer, request)
