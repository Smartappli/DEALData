"""Views for the core_data application."""

import logging

from django.db import DatabaseError, connections
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_safe

from .models import Experiment, ObservedObject, Project

logger = logging.getLogger(__name__)


@require_safe
def health_live(request):
    """Return a cheap liveness response."""
    del request
    return JsonResponse({"status": "ok", "service": "core"})


@require_safe
def health_ready(request):
    """Return readiness after checking the default database connection."""
    del request
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        logger.warning("Core database readiness check failed.")
        return JsonResponse(
            {
                "status": "error",
                "service": "core",
                "database": "unavailable",
                "detail": "Database connection check failed.",
            },
            status=503,
        )
    return JsonResponse(
        {"status": "ok", "service": "core", "database": "available"},
    )


@require_safe
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
