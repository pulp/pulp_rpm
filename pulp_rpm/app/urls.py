from django.conf.urls import url

from .viewsets import CopyViewSet, OneShotUploadViewSet, ModuleOneShotUpload


urlpatterns = [
    url(r'rpm/upload/$', OneShotUploadViewSet.as_view({'post': 'create'})),
    url(r'rpm/copy/$', CopyViewSet.as_view({'post': 'create'})),
    url(r'modulemd/upload/$', ModuleOneShotUpload.as_view({'post': 'create'}))
]
