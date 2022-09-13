from django.conf import settings
from django.urls import path

from .viewsets import CopyViewSet, CompsXmlViewSet


if hasattr(settings, "V3_API_ROOT_NO_FRONT_SLASH"):
    V3_API_ROOT = settings.V3_API_ROOT_NO_FRONT_SLASH
else:
    V3_API_ROOT = "pulp/api/v3/"

urlpatterns = [
    path(f"{V3_API_ROOT}rpm/copy/", CopyViewSet.as_view({"post": "create"})),
    path(f"{V3_API_ROOT}rpm/comps/", CompsXmlViewSet.as_view({"post": "create"})),
]
