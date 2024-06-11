from django.conf import settings
from django.urls import path

from .viewsets import CopyViewSet, CompsXmlViewSet, PrunePackagesViewSet

if settings.DOMAIN_ENABLED:
    V3_API_ROOT = settings.V3_DOMAIN_API_ROOT_NO_FRONT_SLASH
else:
    V3_API_ROOT = settings.V3_API_ROOT_NO_FRONT_SLASH

urlpatterns = [
    path(f"{V3_API_ROOT}rpm/copy/", CopyViewSet.as_view({"post": "create"})),
    path(f"{V3_API_ROOT}rpm/comps/", CompsXmlViewSet.as_view({"post": "create"})),
    path(f"{V3_API_ROOT}rpm/prune/", PrunePackagesViewSet.as_view({"post": "prune_packages"})),
]
