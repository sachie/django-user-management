from django.conf.urls import url
from .. import views

urlpatterns = [
    url(r'^login/?$', views.GetAuthToken.as_view(), name='auth'),
    url(r'^logout/?$', views.DeleteAuthToken.as_view(), name='auth'),
]
