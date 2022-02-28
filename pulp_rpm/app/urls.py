from django.conf import settings
from django.urls import path

from .viewsets import CopyViewSet, CompsXmlViewSet

V3_API_ROOT = settings.V3_API_ROOT_NO_FRONT_SLASH

urlpatterns = [
    path(f"{V3_API_ROOT}rpm/copy/", CopyViewSet.as_view({"post": "create"})),
    path(f"{V3_API_ROOT}rpm/comps/", CompsXmlViewSet.as_view({"post": "create"})),
]
