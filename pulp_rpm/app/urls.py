from django.urls import path

from .viewsets import CopyViewSet

urlpatterns = [path("pulp/api/v3/rpm/copy/", CopyViewSet.as_view({"post": "create"}))]
