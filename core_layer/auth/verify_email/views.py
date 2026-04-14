"""Views for email verification workflows."""

import uuid

from asgiref.sync import sync_to_async
from auth.helpers import send_verification_email
from auth.models import Profile
from auth.views import AuthView
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect

EMAIL_NOT_CONFIGURED_MESSAGE = (
    "Email settings are not configured. Unable to send verification email."
)
INVALID_VERIFICATION_MESSAGE = "Invalid verification link, please try again"
EMAIL_VERIFIED_MESSAGE = "Email verified successfully"
PROFILE_NOT_FOUND_MESSAGE = "Unable to find a profile for that email."
EMAIL_NOT_FOUND_MESSAGE = "Email not found in session"
VERIFICATION_EMAIL_SENT_MESSAGE = "Verification email sent successfully"
VERIFICATION_EMAIL_RESENT_MESSAGE = "Resend verification email successfully"


class VerifyEmailTokenView(AuthView):
    """
    Verify a user's email address using a token.

    GET /verify-email/<token>:
    - Finds the Profile with `email_token == token`.
    - Sets `is_verified = True` and clears `email_token`.
    - Shows a success message.
    - Redirects to the login page.

    Error handling:
    - If the token is invalid, shows an error message and redirects to the
      verify email page.
    """

    async def get(self, request, token):
        """
        Handle token verification.

        Args:
            request: Django HttpRequest.
            token: Verification token extracted from the URL.

        Returns:
            An HTTP redirect response.

        """
        profile = await Profile.objects.filter(email_token=token).afirst()
        if not profile:
            await sync_to_async(messages.error)(
                request,
                INVALID_VERIFICATION_MESSAGE,
            )
            return redirect("verify-email-page")

        profile.is_verified = True
        profile.email_token = ""
        await profile.asave()

        if not request.user.is_authenticated:
            await sync_to_async(messages.success)(
                request,
                EMAIL_VERIFIED_MESSAGE,
            )

        return redirect("login")


class VerifyEmailView(AuthView):
    """
    Display the verify email page.

    This is typically a page where users are informed that they must verify
    their email address and where they can trigger a resend of the
    verification email.
    """

    async def get(self, request):
        """
        Render the verify email page.

        Args:
            request: Django HttpRequest.

        Returns:
            The response returned by the parent AuthView's GET handler.

        """
        return await sync_to_async(super().get)(request)


class SendVerificationView(AuthView):
    """
    Generate and send a verification email.

    GET /send-verification:
    - Determines the target email.
    - Generates a new UUID token and saves it into Profile.email_token.
    - Sends the verification email.
    - Displays a success or error message.
    - Redirects back to the verify email page.
    """

    async def get(self, request):
        """
        Send a verification email to the user.

        Args:
            request: Django HttpRequest.

        Returns:
            An HTTP redirect response to the verify email page.

        """
        email, success_message, error_message = await self.get_email_and_message(
            request,
        )

        if error_message:
            await sync_to_async(messages.error)(request, error_message)
            return redirect("verify-email-page")

        if not email:
            await sync_to_async(messages.error)(
                request,
                EMAIL_NOT_FOUND_MESSAGE,
            )
            return redirect("verify-email-page")

        verification_uuid = str(uuid.uuid4())
        user_profile = await Profile.objects.filter(email=email).afirst()
        if not user_profile:
            await sync_to_async(messages.error)(
                request,
                PROFILE_NOT_FOUND_MESSAGE,
            )
            return redirect("verify-email-page")

        user_profile.email_token = verification_uuid
        await user_profile.asave()
        await send_verification_email(email, verification_uuid)
        await sync_to_async(messages.success)(request, success_message)

        return redirect("verify-email-page")

    async def get_email_and_message(self, request):
        """
        Resolve the recipient email and the message to display.

        Rules:
        - If authenticated, use the email from the user's profile.
        - If not authenticated, use `request.session["email"]` if present.
        - If email settings are missing, return an error message.

        Args:
            request: Django HttpRequest.

        Returns:
            A tuple `(email, success_message, error_message)` where:
            - `email` is a string or None
            - `success_message` is a string or None
            - `error_message` is a string or None

        """
        if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
            return None, None, EMAIL_NOT_CONFIGURED_MESSAGE

        if request.user.is_authenticated:
            profile = await Profile.objects.filter(user=request.user).afirst()
            email = profile.email if profile else None
            return email, VERIFICATION_EMAIL_SENT_MESSAGE, None

        email = request.session.get("email")
        return email, VERIFICATION_EMAIL_RESENT_MESSAGE, None
