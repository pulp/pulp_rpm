from django_filters import CharFilter

from pulpcore.plugin.viewsets import (
    ContentFilter,
    SingleArtifactContentUploadViewSet,
)

from pulp_rpm.app.models import (
    Modulemd,
    ModulemdDefaults,
    ModulemdObsolete,
)
from pulp_rpm.app.serializers import (
    ModulemdDefaultsSerializer,
    ModulemdSerializer,
    ModulemdObsoleteSerializer,
)


class ModulemdFilter(ContentFilter):
    """
    FilterSet for Modulemd.
    """

    sha256 = CharFilter(field_name="_artifacts__sha256")

    class Meta:
        model = Modulemd
        fields = {
            "name": ["exact", "in"],
            "stream": ["exact", "in"],
        }


class ModulemdViewSet(SingleArtifactContentUploadViewSet):
    """
    ViewSet for Modulemd.
    """

    endpoint_name = "modulemds"
    queryset = Modulemd.objects.all()
    serializer_class = ModulemdSerializer
    filterset_class = ModulemdFilter


class ModulemdDefaultsFilter(ContentFilter):
    """
    FilterSet for ModulemdDefaults.
    """

    sha256 = CharFilter(field_name="_artifacts__sha256")

    class Meta:
        model = ModulemdDefaults
        fields = {
            "module": ["exact", "in"],
            "stream": ["exact", "in"],
        }


class ModulemdDefaultsViewSet(SingleArtifactContentUploadViewSet):
    """
    ViewSet for Modulemd.
    """

    endpoint_name = "modulemd_defaults"
    queryset = ModulemdDefaults.objects.all()
    serializer_class = ModulemdDefaultsSerializer
    filterset_class = ModulemdDefaultsFilter


class ModulemdObsoleteViewSet(SingleArtifactContentUploadViewSet):
    """
    ViewSet for Modulemd.
    """

    endpoint_name = "modulemd_obsoletes"
    queryset = ModulemdObsolete.objects.all()
    serializer_class = ModulemdObsoleteSerializer
