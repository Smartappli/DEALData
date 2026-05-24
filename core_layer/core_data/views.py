"""Views for the core_data application."""

from django.db import connections
from django.http import JsonResponse


def health_live(request):
    """Return a cheap liveness response."""
    del request
    return JsonResponse({"status": "ok", "service": "core"})


def health_ready(request):
    """Return readiness after checking the default database connection."""
    del request
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:
        return JsonResponse(
            {
                "status": "error",
                "service": "core",
                "database": "unavailable",
                "detail": str(exc),
            },
            status=503,
        )
    return JsonResponse(
        {"status": "ok", "service": "core", "database": "available"},
    )
