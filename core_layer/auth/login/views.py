"""Views for authentication login workflows."""

from asgiref.sync import sync_to_async
from auth.views import AuthView
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import aauthenticate, alogin
from django.contrib.auth.models import User
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme

MISSING_CREDENTIALS_MESSAGE = "Please enter your username and password."
INVALID_EMAIL_MESSAGE = "Please enter a valid email."
INVALID_USERNAME_MESSAGE = "Please enter a valid username."


class LoginView(AuthView):
    """Handle user login requests."""

    async def get(self, request):
        """
        Display the login page for unauthenticated users.

        Args:
            request: Django HTTP request.

        Returns:
            An HTTP redirect response or the rendered login page.

        """
        is_auth = await sync_to_async(lambda: request.user.is_authenticated)()
        if is_auth:
            return redirect("index")

        return await sync_to_async(super().get)(request)

    async def post(self, request):
        """
        Authenticate the user and start a session.

        Args:
            request: Django HTTP request.

        Returns:
            An HTTP redirect response.

        """
        username = request.POST.get("email-username")
        password = request.POST.get("password")

        if not (username and password):
            await sync_to_async(messages.error)(
                request,
                MISSING_CREDENTIALS_MESSAGE,
            )
            return redirect("login")

        if "@" in username:
            user_email = await User.objects.filter(email=username).afirst()
            if user_email is None:
                await sync_to_async(messages.error)(
                    request,
                    INVALID_EMAIL_MESSAGE,
                )
                return redirect("login")
            username = user_email.username

        user_email = await User.objects.filter(username=username).afirst()
        if user_email is None:
            await sync_to_async(messages.error)(
                request,
                INVALID_USERNAME_MESSAGE,
            )
            return redirect("login")

        authenticated_user = await aauthenticate(
            request,
            username=username,
            password=password,
        )
        if authenticated_user is not None:
            await alogin(request, authenticated_user)

            next_url = request.POST.get("next", "")
            if next_url and url_has_allowed_host_and_scheme(
                url=next_url,
                allowed_hosts={
                    request.get_host(),
                    *getattr(settings, "ALLOWED_HOSTS", []),
                },
                require_https=not settings.DEBUG,
            ):
                return redirect(next_url)

            return redirect("index")

        await sync_to_async(messages.error)(
            request,
            INVALID_USERNAME_MESSAGE,
        )
        return redirect("login")
