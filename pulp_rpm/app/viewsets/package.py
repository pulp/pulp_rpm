from django_filters import CharFilter

from pulpcore.plugin.viewsets import (
    ContentFilter,
    SingleArtifactContentUploadViewSet,
)

from pulp_rpm.app.models import (
    Package,
)
from pulp_rpm.app.serializers import (
    MinimalPackageSerializer,
    PackageSerializer,
)


class PackageFilter(ContentFilter):
    """
    FilterSet for Package.
    """

    sha256 = CharFilter(field_name="_artifacts__sha256")

    class Meta:
        model = Package
        fields = {
            "name": ["exact", "in", "ne"],
            "epoch": ["exact", "in", "ne"],
            "version": ["exact", "in", "ne"],
            "release": ["exact", "in", "ne"],
            "arch": ["exact", "in", "ne"],
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
