from django.conf.urls import url

from .. import views

urlpatterns = [
    url(
        r'^register/?$',
        views.UserRegister.as_view(),
        name='register',
    ),
    url(
        r'^resend-confirmation-email/?$',
        views.ResendConfirmationEmail.as_view(),
        name='resend_confirmation_email',
    ),
]
