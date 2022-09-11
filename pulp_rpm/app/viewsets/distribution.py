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
