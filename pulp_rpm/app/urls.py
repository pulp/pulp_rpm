from django.conf.urls import url

from .viewsets import CopyViewSet, OneShotUploadViewSet


urlpatterns = [
    url(r"rpm/upload/$", OneShotUploadViewSet.as_view({"post": "create"})),
    url(r"rpm/copy/$", CopyViewSet.as_view({"post": "create"})),
]
