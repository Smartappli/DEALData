"""Views for forgot-password workflows."""

import uuid
from datetime import timedelta

from asgiref.sync import sync_to_async
from auth.helpers import send_password_reset_email
from auth.models import Profile
from auth.views import AuthView
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.shortcuts import redirect
from django.utils import timezone

MISSING_EMAIL_MESSAGE = "Please enter your email address."
RESET_LINK_SENT_MESSAGE = (
    "If an account exists for that email, a reset link has been sent."
)
EMAIL_NOT_CONFIGURED_MESSAGE = (
    "Email settings are not configured. Unable to send verification email."
)
RESET_TOKEN_EXPIRATION_HOURS = 24


class ForgetPasswordView(AuthView):
    """Handle password reset requests initiated by email."""

    async def get(self, request):
        """
        Display the forgot-password page.

        Args:
            request: Django HTTP request.

        Returns:
            An HTTP redirect response or the rendered forgot-password page.

        """
        if request.user.is_authenticated:
            return redirect("index")

        return await sync_to_async(super().get)(request)

    async def post(self, request):
        """
        Generate and send a password reset link when possible.

        Args:
            request: Django HTTP request.

        Returns:
            An HTTP redirect response.

        """
        email = request.POST.get("email")
        if not email:
            await sync_to_async(messages.error)(
                request,
                MISSING_EMAIL_MESSAGE,
            )
            return redirect("forgot-password")

        user = await User.objects.filter(email=email).afirst()
        reset_token = str(uuid.uuid4())
        expiration_time = timezone.now() + timedelta(
            hours=RESET_TOKEN_EXPIRATION_HOURS,
        )

        if user:
            user_profile, _created_profile = await Profile.objects.aget_or_create(
                user=user,
            )
            user_profile.forget_password_token = reset_token
            user_profile.forget_password_token_expires_at = expiration_time
            await user_profile.asave()

            await send_password_reset_email(email, reset_token)

        if settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD:
            await sync_to_async(messages.success)(
                request,
                RESET_LINK_SENT_MESSAGE,
            )
        else:
            await sync_to_async(messages.error)(
                request,
                EMAIL_NOT_CONFIGURED_MESSAGE,
            )

        return redirect("forgot-password")
