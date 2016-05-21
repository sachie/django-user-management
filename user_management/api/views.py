from django.contrib.auth import get_user_model, signals
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_text
from django.utils.http import urlsafe_base64_decode
from django.utils.translation import ugettext_lazy as _
from rest_framework import generics, response, status, views
from rest_framework.authentication import get_authorization_header
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated

from user_management.utils.views import VerifyAccountViewMixin
from . import exceptions, models, permissions, serializers, throttling

User = get_user_model()


class GetAuthToken(ObtainAuthToken):
    """
    Obtain an authentication token.

    Define a `POST` (create) method to authenticate a user using their `email` and
    `password` and return a `token` if successful.
    The `token` remains valid until `settings.AUTH_TOKEN_MAX_AGE` time has passed.
    """
    model = models.AuthToken
    throttle_classes = [
        throttling.UsernameLoginRateThrottle,
        throttling.LoginRateThrottle,
    ]
    throttle_scope = 'logins'

    def post(self, request):
        """Create auth token. Differs from DRF that it always creates new token
        but not re-using them."""
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            signals.user_logged_in.send(type(self), user=user, request=request)
            self.model.objects.filter(user=user).delete()
            token = self.model.objects.create(user=user)
            token.update_expiry()
            return response.Response({'token': token.key})

        return response.Response(
            serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DeleteAuthToken(ObtainAuthToken):
    """
    Delete authentication token.

    `DELETE` method removes the current `token` from the database.
    """
    model = models.AuthToken
    throttle_classes = [
        throttling.UsernameLoginRateThrottle,
        throttling.LoginRateThrottle,
    ]
    throttle_scope = 'logins'

    def delete(self, request, *args, **kwargs):
        """Delete auth token when `delete` request was issued."""
        # Logic repeated from DRF because one cannot easily reuse it
        auth = get_authorization_header(request).split()

        if not auth or auth[0].lower() != b'token':
            msg = 'No credentials provided.'
            return response.Response(msg, status=status.HTTP_400_BAD_REQUEST)

        if len(auth) == 1:
            msg = 'Invalid token header. No credentials provided.'
            return response.Response(msg, status=status.HTTP_400_BAD_REQUEST)
        elif len(auth) > 2:
            msg = 'Invalid token header. Token string should not contain spaces.'
            return response.Response(msg, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = self.model.objects.get(key=auth[1])
        except self.model.DoesNotExist:
            pass
        else:
            token.delete()
            signals.user_logged_out.send(
                type(self),
                user=token.user,
                request=request,
            )
        return response.Response(status=status.HTTP_204_NO_CONTENT)


class UserRegister(generics.CreateAPIView):
    """
    Register a new `User`.

    An email to validate the new account is sent if `email_verified`
    is set to `False`.
    """
    serializer_class = serializers.RegistrationSerializer
    permission_classes = [permissions.IsNotAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            return self.is_valid(serializer)
        return self.is_invalid(serializer)

    def is_invalid(self, serializer):
        return response.Response(
            data=serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    def is_valid(self, serializer):
        user = serializer.save()
        if not user.email_verified:
            user.send_validation_email()
            ok_message = _(
                'Your account has been created and an activation link sent ' +
                'to your email address. Please check your email to continue.'
            )
        else:
            ok_message = _('Your account has been created.')

        return response.Response(
            data={'data': ok_message},
            status=status.HTTP_201_CREATED,
        )


class PasswordResetEmail(generics.GenericAPIView):
    """
    Send a password reset email to a user on request.

    A user can request a password request email by providing their email address.
    If the user is not found no error is raised.
    """
    permission_classes = [permissions.IsNotAuthenticated]
    template_name = 'user_management/password_reset_email.html'
    serializer_class = serializers.PasswordResetEmailSerializer
    throttle_classes = [throttling.PasswordResetRateThrottle]
    throttle_scope = 'passwords'

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return response.Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = serializer.data['email']
        try:
            user = User.objects.get_by_natural_key(email)
        except User.DoesNotExist:
            pass
        else:
            user.send_password_reset()

        msg = _('Password reset request successful. Please check your email.')
        return response.Response(msg, status=status.HTTP_204_NO_CONTENT)


class OneTimeUseAPIMixin(object):
    """
    Use a `uid` and a `token` to allow one-time access to a view.

    Set user as a class attribute or raise an `InvalidExpiredToken`.
    """

    def initial(self, request, *args, **kwargs):
        uidb64 = kwargs['uidb64']
        uid = urlsafe_base64_decode(force_text(uidb64))

        try:
            self.user = User.objects.get(pk=uid)
        except User.DoesNotExist:
            raise exceptions.InvalidExpiredToken()

        token = kwargs['token']
        if not default_token_generator.check_token(self.user, token):
            raise exceptions.InvalidExpiredToken()

        return super(OneTimeUseAPIMixin, self).initial(
            request,
            *args,
            **kwargs
        )


class PasswordReset(OneTimeUseAPIMixin, generics.UpdateAPIView):
    """
    Reset a user's password.

    This view is generally called when a user has followed an email link to
    reset a password.

    This view will check first if the `uid` and `token` are valid.

    `PasswordReset` is called with an `UPDATE` containing the new password
    (`new_password` and `new_password2`).
    """
    permission_classes = [permissions.IsNotAuthenticated]
    model = User
    serializer_class = serializers.PasswordResetSerializer

    def get_object(self):
        return self.user


class PasswordChange(generics.UpdateAPIView):
    """
    Change a user's password.

    Give ability to `PUT` (update) a password when authenticated by submitting current
    password.
    """
    model = User
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.PasswordChangeSerializer

    def get_object(self):
        return self.request.user


class VerifyAccountView(VerifyAccountViewMixin, views.APIView):
    """
    Verify a new user's email address.  Accepts a POST request with a token in the URL.
    """
    permission_classes = [AllowAny]

    def initial(self, request, *args, **kwargs):
        self.verify_token(request, *args, **kwargs)
        return super(VerifyAccountView, self).initial(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.activate_user()
        return response.Response(
            data={'data': self.ok_message},
            status=status.HTTP_201_CREATED,
        )


class ProfileDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    Allow a user to view and edit their profile information.

    `GET`, `UPDATE` and `DELETE` current logged-in user.
    """
    model = User
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.ProfileSerializer

    def get_object(self):
        return self.request.user


class UserList(generics.ListCreateAPIView):
    """
    Return information about all users and allow creation of new users.

    Allow to `GET` a list users and to `POST` new user for admin user only.
    """
    queryset = User.objects.all()
    permission_classes = (IsAuthenticated, permissions.IsAdminOrReadOnly)
    serializer_class = serializers.UserSerializerCreate


class UserDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    Display information about a user.

    Allow admin users to update or delete user information.
    """
    queryset = User.objects.all()
    permission_classes = (IsAuthenticated, permissions.IsAdminOrReadOnly)
    serializer_class = serializers.UserSerializer


class ResendConfirmationEmail(generics.GenericAPIView):
    """
    Resend a confirmation email.

    `POST` request to resend a confirmation email for existing user. If user is
    authenticated the email sent should match.
    """
    permission_classes = [AllowAny]
    serializer_class = serializers.ResendConfirmationEmailSerializer
    throttle_classes = [throttling.ResendConfirmationEmailRateThrottle]
    throttle_scope = 'confirmations'

    def initial(self, request, *args, **kwargs):
        """Disallow users other than the user whose email is being reset."""
        email = request.data.get('email')
        if request.user.is_authenticated() and email != request.user.email:
            raise PermissionDenied()

        return super(ResendConfirmationEmail, self).initial(
            request,
            *args,
            **kwargs
        )

    def post(self, request, *args, **kwargs):
        """Validate `email` and send a request to confirm it."""
        serializer = self.serializer_class(data=request.data)

        if not serializer.is_valid():
            return response.Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.user.send_validation_email()
        msg = _('Email confirmation sent.')
        return response.Response(msg, status=status.HTTP_204_NO_CONTENT)
