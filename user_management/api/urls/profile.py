from django.conf.urls import patterns, url

from .. import views


urlpatterns = [
    url(
        r'^profile/?$',
        views.ProfileDetail.as_view(),
        name='profile_detail',
    ),
    url(
        r'^profile/password/?$',
        views.PasswordChange.as_view(),
        name='password_change',
    ),
]