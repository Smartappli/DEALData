"""Views for user registration workflows."""

import uuid

from asgiref.sync import sync_to_async
from auth.helpers import send_verification_email
from auth.models import Profile
from auth.views import AuthView
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import Group, User
from django.shortcuts import redirect

EMAIL_NOT_CONFIGURED_MESSAGE = (
    "Email settings are not configured. Unable to send verification email."
)
VERIFICATION_EMAIL_SENT_MESSAGE = "Verification email sent successfully"
MISSING_FIELDS_MESSAGE = "Please fill in all required fields."
USER_ALREADY_EXISTS_MESSAGE = "User already exists. Try logging in."
EMAIL_ALREADY_EXISTS_MESSAGE = "Email already exists."
USERNAME_ALREADY_EXISTS_MESSAGE = "Username already exists."
DEFAULT_GROUP_NAME = "client"


class RegisterView(AuthView):
    """Handle user registration and email verification setup."""

    async def get(self, request):
        """
        Display the registration page.

        Args:
            request: Django HTTP request.

        Returns:
            An HTTP redirect response or the rendered registration page.

        """
        if request.user.is_authenticated:
            return redirect("index")

        return await sync_to_async(super().get)(request)

    async def post(self, request):
        """
        Create a new user account and send a verification email.

        Args:
            request: Django HTTP request.

        Returns:
            An HTTP redirect response.

        """
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")

        if not (username and email and password):
            await sync_to_async(messages.error)(
                request,
                MISSING_FIELDS_MESSAGE,
            )
            return redirect("register")

        if await User.objects.filter(username=username, email=email).aexists():
            await sync_to_async(messages.error)(
                request,
                USER_ALREADY_EXISTS_MESSAGE,
            )
            return redirect("register")

        if await User.objects.filter(email=email).aexists():
            await sync_to_async(messages.error)(
                request,
                EMAIL_ALREADY_EXISTS_MESSAGE,
            )
            return redirect("register")

        if await User.objects.filter(username=username).aexists():
            await sync_to_async(messages.error)(
                request,
                USERNAME_ALREADY_EXISTS_MESSAGE,
            )
            return redirect("register")

        created_user = await User.objects.acreate_user(
            username=username,
            email=email,
            password=password,
        )

        user_group, _created_group = await Group.objects.aget_or_create(
            name=DEFAULT_GROUP_NAME,
        )
        await sync_to_async(created_user.groups.add)(user_group)

        verification_token = str(uuid.uuid4())

        user_profile, _created_profile = await Profile.objects.aget_or_create(
            user=created_user,
        )
        user_profile.email_token = verification_token
        user_profile.email = email
        await user_profile.asave()

        await send_verification_email(email, verification_token)

        if settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD:
            await sync_to_async(messages.success)(
                request,
                VERIFICATION_EMAIL_SENT_MESSAGE,
            )
        else:
            await sync_to_async(messages.error)(
                request,
                EMAIL_NOT_CONFIGURED_MESSAGE,
            )

        request.session["email"] = email
        return redirect("verify-email-page")
