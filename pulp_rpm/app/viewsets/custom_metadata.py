from pulpcore.plugin.viewsets import ReadOnlyContentViewSet

from pulp_rpm.app.models import RepoMetadataFile
from pulp_rpm.app.serializers import RepoMetadataFileSerializer


class RepoMetadataFileViewSet(ReadOnlyContentViewSet):
    """
    RepoMetadataFile Viewset.
    """

    endpoint_name = "repo_metadata_files"
    queryset = RepoMetadataFile.objects.all()
    serializer_class = RepoMetadataFileSerializer

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list", "retrieve"],
                "principal": "authenticated",
                "effect": "allow",
            },
        ],
        "queryset_scoping": {"function": "scope_queryset"},
    }
