from django.conf import settings
from django.urls import path, include

from .viewsets import CopyViewSet, CompsXmlViewSet, PrunePackagesViewSet

if settings.DOMAIN_ENABLED:
    V3_API_ROOT = settings.V3_DOMAIN_API_ROOT_NO_FRONT_SLASH
else:
    V3_API_ROOT = settings.V3_API_ROOT_NO_FRONT_SLASH

additional_apis = [
    path("copy/", CopyViewSet.as_view({"post": "create"})),
    path("comps/", CompsXmlViewSet.as_view({"post": "create"})),
    path("prune/", PrunePackagesViewSet.as_view({"post": "prune_packages"})),
]

urlpatterns = [
    path(f"{V3_API_ROOT}rpm/", include(additional_apis)),
]

if getattr(settings, "ENABLE_V4_API", False):
    V4_API_ROOT = settings.V4_DOMAIN_API_ROOT_NO_FRONT_SLASH

    additional_apis = [
        path("copy/", CopyViewSet.as_view({"post": "create"}), name="rpm-copy"),
        path("comps/", CompsXmlViewSet.as_view({"post": "create"}), name="rpm-comps"),
        path("prune/", PrunePackagesViewSet.as_view({"post": "prune_packages"}), name="rpm-prune"),
    ]

    urlpatterns.append(
        path(f"{V4_API_ROOT}rpm/", include((additional_apis, "rpm"), namespace="v4"))
    )
