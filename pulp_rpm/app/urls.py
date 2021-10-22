from django.urls import path

from .viewsets import CopyViewSet, CompsXmlViewSet

urlpatterns = [
    path("pulp/api/v3/rpm/copy/", CopyViewSet.as_view({"post": "create"})),
    path("pulp/api/v3/rpm/comps/", CompsXmlViewSet.as_view({"post": "create"})),
]
