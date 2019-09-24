from django.conf.urls import url

from .viewsets import CopyViewSet, OneShotUploadViewSet


urlpatterns = [
    url(r'^pulp/api/v3/rpm/upload/$', OneShotUploadViewSet.as_view({'post': 'create'})),
    url(r'^pulp/api/v3/rpm/copy/$', CopyViewSet.as_view({'post': 'create'}))
]
