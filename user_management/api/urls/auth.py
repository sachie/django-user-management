from django.conf.urls import url
from .. import views

urlpatterns = [
    url(r'^auth/?$', views.GetAuthToken.as_view(), name='auth'),
]
