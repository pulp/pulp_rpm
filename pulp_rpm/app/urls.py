from django.conf.urls import url

from .viewsets import OneShotUploadView


urlpatterns = [
    url(r'rpm/upload/$', OneShotUploadView.as_view())
]
