from django.conf.urls import url
from django.views.decorators.csrf import csrf_exempt

from .. import views

urlpatterns = [
    url(
        (
            r'^auth/password_reset/confirm/(?P<uidb64>[0-9A-Za-z_\-]+)/'
            r'(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})/?$'
        ),
        csrf_exempt(views.PasswordReset.as_view()),
        name='password_reset_confirm',
    ),
    url(
        r'^auth/password_reset/?$',
        views.PasswordResetEmail.as_view(),
        name='password_reset',
    ),
]
