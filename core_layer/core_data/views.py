"""Views for the core_data application."""

from django.http import JsonResponse


def health_live(request):
    """Return a cheap liveness response."""
    del request
    return JsonResponse({"status": "ok", "service": "core"})
