"""Views for the core_data application."""

from django.db import connections
from django.http import HttpResponse, JsonResponse

from .models import Experiment, ObservedObject, Project


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


def metrics(request):
    """Return minimal Prometheus metrics for the core service."""
    del request
    body = "\n".join(
        [
            "# HELP dealdata_core_projects_total Stored projects.",
            "# TYPE dealdata_core_projects_total gauge",
            f"dealdata_core_projects_total {Project.objects.count()}",
            "# HELP dealdata_core_observed_objects_total Stored observed objects.",
            "# TYPE dealdata_core_observed_objects_total gauge",
            f"dealdata_core_observed_objects_total {ObservedObject.objects.count()}",
            "# HELP dealdata_core_experiments_total Stored experiments.",
            "# TYPE dealdata_core_experiments_total gauge",
            f"dealdata_core_experiments_total {Experiment.objects.count()}",
            "",
        ],
    )
    return HttpResponse(body, content_type="text/plain; version=0.0.4")
