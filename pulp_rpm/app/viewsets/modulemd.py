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
            "version": ["exact", "in"],
            "context": ["exact", "in"],
            "arch": ["exact", "in"],
        }


class ModulemdViewSet(SingleArtifactContentUploadViewSet):
    """
    ViewSet for Modulemd.
    """

    endpoint_name = "modulemds"
    queryset = Modulemd.objects.all()
    serializer_class = ModulemdSerializer
    filterset_class = ModulemdFilter

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


class ModulemdObsoleteViewSet(SingleArtifactContentUploadViewSet):
    """
    ViewSet for Modulemd.
    """

    endpoint_name = "modulemd_obsoletes"
    queryset = ModulemdObsolete.objects.all()
    serializer_class = ModulemdObsoleteSerializer

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
