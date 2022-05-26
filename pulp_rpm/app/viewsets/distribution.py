from pulpcore.plugin.viewsets import (
    ReadOnlyContentViewSet,
)

from pulp_rpm.app.models import (
    DistributionTree,
)
from pulp_rpm.app.serializers import (
    DistributionTreeSerializer,
)


class DistributionTreeViewSet(ReadOnlyContentViewSet):
    """
    Distribution Tree Viewset.

    """

    endpoint_name = "distribution_trees"
    queryset = DistributionTree.objects.all()
    serializer_class = DistributionTreeSerializer

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
