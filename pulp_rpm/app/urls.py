from django.conf import settings
from django.urls import path

from pulpcore.plugin.find_url import find_api_root

from .viewsets import CompsXmlViewSet, CopyViewSet, PrunePackagesViewSet

if getattr(settings, "ENABLE_V4_API", None):
    VERSION = "<str:version>"
else:
    VERSION = "v3"

_, API_ROOT = find_api_root(lstrip=True, version=VERSION)
urlpatterns = [
    path(f"{API_ROOT}rpm/copy/", CopyViewSet.as_view({"post": "create"})),
    path(f"{API_ROOT}rpm/comps/", CompsXmlViewSet.as_view({"post": "create"})),
    path(f"{API_ROOT}rpm/prune/", PrunePackagesViewSet.as_view({"post": "prune_packages"})),
]
