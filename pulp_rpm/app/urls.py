from django.conf.urls import url

from .viewsets import CopyViewSet, ModularUploadViewSet


urlpatterns = [
    url(r'^pulp/api/v3/rpm/copy/$', CopyViewSet.as_view({'post': 'create'})),
    url(r'^pulp/api/v3/modularity/upload/$', ModularUploadViewSet.as_view({'post': 'create'}))
]
