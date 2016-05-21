from django.conf.urls import url

from .. import views

urlpatterns = [
    url(
        r'^users/?$',
        views.UserList.as_view(),
        name='user_list'
    ),
    url(
        r'^users/(?P<pk>\d+)/?$',
        views.UserDetail.as_view(),
        name='user_detail'
    ),
]
