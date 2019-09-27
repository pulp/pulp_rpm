from django.conf.urls import url

from .viewsets import CopyViewSet


urlpatterns = [
    url(r'^pulp/api/v3/rpm/copy/$', CopyViewSet.as_view({'post': 'create'}))
]
