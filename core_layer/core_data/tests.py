"""Tests for the core_data application."""

from core_data.models import ObservedObject, Project


def test_project_string_representation() -> None:
    """Project instances are represented by their code."""
    project = Project(project_code="DEAL-CORE")

    assert str(project) == "DEAL-CORE"


def test_observed_object_string_representation() -> None:
    """Observed objects are represented by their code."""
    observed_object = ObservedObject(observed_object_code="OBJ-001")

    assert str(observed_object) == "OBJ-001"
