"""Tests for the core_data application."""

import pytest
from core_data.models import (
    Experiment,
    ExperimentObservedObject,
    ObservedObject,
    Project,
    ProjectMembership,
    ProjectRole,
    uuid7_value,
)
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import Client


def test_project_string_representation() -> None:
    """Project instances are represented by their code."""
    project = Project(project_code="DEAL-CORE")

    assert str(project) == "DEAL-CORE"


def test_observed_object_string_representation() -> None:
    """Observed objects are represented by their code."""
    observed_object = ObservedObject(observed_object_code="OBJ-001")

    assert str(observed_object) == "OBJ-001"


def test_uuid7_value_returns_standard_uuid() -> None:
    """UUID defaults are compatible with Django UUIDField validation."""
    value = uuid7_value()

    assert value.version == 7


@pytest.mark.django_db
def test_project_membership_string_representation() -> None:
    """Memberships expose project, user and role in their string form."""
    user = User.objects.create_user(username="alice")
    project = Project.objects.create(
        project_code="DEAL-001",
        project_primary_owner=user,
    )
    membership = ProjectMembership.objects.create(
        project_membership_project=project,
        project_membership_user=user,
        project_membership_role=ProjectRole.OWNER,
    )

    assert str(membership) == "DEAL-001 - alice - owner"


@pytest.mark.django_db
def test_project_membership_rejects_removing_last_owner() -> None:
    """A project must keep at least one active owner."""
    user = User.objects.create_user(username="owner")
    project = Project.objects.create(
        project_code="DEAL-002",
        project_primary_owner=user,
    )
    membership = ProjectMembership.objects.create(
        project_membership_project=project,
        project_membership_user=user,
        project_membership_role=ProjectRole.OWNER,
    )

    membership.project_membership_role = ProjectRole.VIEWER

    with pytest.raises(ValidationError):
        membership.full_clean()


@pytest.mark.django_db
def test_project_owners_qs_returns_active_owners() -> None:
    """Project owners query excludes inactive or non-owner memberships."""
    owner = User.objects.create_user(username="owner")
    viewer = User.objects.create_user(username="viewer")
    project = Project.objects.create(
        project_code="DEAL-003",
        project_primary_owner=owner,
    )
    ProjectMembership.objects.create(
        project_membership_project=project,
        project_membership_user=owner,
        project_membership_role=ProjectRole.OWNER,
    )
    ProjectMembership.objects.create(
        project_membership_project=project,
        project_membership_user=viewer,
        project_membership_role=ProjectRole.VIEWER,
    )

    assert list(project.project_owners_qs()) == [owner]


@pytest.mark.django_db
def test_experiment_links_string_representations() -> None:
    """Experiments and experiment-object links have stable string output."""
    user = User.objects.create_user(username="scientist")
    project = Project.objects.create(
        project_code="DEAL-004",
        project_primary_owner=user,
    )
    observed_object = ObservedObject.objects.create(
        observed_object_code="OBJ-004",
    )
    experiment = Experiment.objects.create(experiment_project=project)
    link = ExperimentObservedObject.objects.create(
        experiment_observed_object_experiment=experiment,
        experiment_observed_object_observed_object=observed_object,
    )

    assert str(experiment) == str(experiment.experiment_id)
    assert str(link) == (
        f"{experiment.experiment_id} - {observed_object.observed_object_id}"
    )


def test_health_live() -> None:
    """The liveness endpoint returns a cheap OK response."""
    response = Client().get("/health/live/")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_ready(db) -> None:
    """The readiness endpoint checks database access."""
    del db
    response = Client().get("/health/ready/")

    assert response.status_code == 200
    assert response.json()["database"] == "available"


@pytest.mark.parametrize(
    "path",
    ["/health/live/", "/health/ready/", "/metrics/"],
)
def test_observability_endpoints_reject_unsafe_methods(path: str) -> None:
    """Read-only observability endpoints reject unsafe HTTP methods."""
    response = Client().post(path)

    assert response.status_code == 405
    assert response.headers["Allow"] == "GET, HEAD"


@pytest.mark.django_db
def test_metrics_exposes_prometheus_counts() -> None:
    """Metrics endpoint exposes core domain counters."""
    user = User.objects.create_user(username="metrics-owner")
    Project.objects.create(
        project_code="DEAL-METRICS",
        project_primary_owner=user,
    )
    ObservedObject.objects.create(observed_object_code="OBJ-METRICS")

    response = Client().get("/metrics/")
    text = response.content.decode()

    assert response.status_code == 200
    assert "dealdata_core_projects_total 1" in text
    assert "dealdata_core_observed_objects_total 1" in text
