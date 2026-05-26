"""Redirect helpers for authentication flows."""

from django.utils.http import url_has_allowed_host_and_scheme


def get_safe_next_url(request) -> str:
    """Return a same-host post-login redirect target or an empty string."""
    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return ""
