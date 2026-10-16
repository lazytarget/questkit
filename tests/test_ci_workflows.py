"""Guards for QST-tf4wc: CI lives in `.github/workflows`, covers the supported
Python range, and publishing goes to the Gitea registry only (GitHub / PyPI
publishing is deferred to 0.9.0)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def _load(name: str) -> dict:
    data = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    # PyYAML reads the bare key `on` as boolean True.
    data["on"] = data.pop(True, data.get("on"))
    return data


def _run_lines(workflow: dict) -> str:
    return "\n".join(
        step.get("run", "") for job in workflow["jobs"].values() for step in job["steps"]
    )


def test_no_workflow_lives_under_gitea():
    assert not (ROOT / ".gitea" / "workflows").exists()


def test_ci_runs_on_push_and_pull_request():
    triggers = _load("ci.yml")["on"]
    assert "push" in triggers
    assert "pull_request" in triggers


def test_ci_matrix_covers_the_supported_python_range():
    matrix = _load("ci.yml")["jobs"]["test"]["strategy"]["matrix"]["python-version"]
    assert matrix == ["3.11", "3.12", "3.13"]
    requires = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.11"' in requires


def test_ci_runs_tests_lint_types_and_the_quest_log_checks():
    commands = _run_lines(_load("ci.yml"))
    for expected in ("pytest", "ruff check", "mypy", "quest validate", "quest format --check"):
        assert expected in commands


def test_publish_triggers_on_version_tags_and_targets_the_gitea_registry():
    workflow = _load("publish.yml")
    assert workflow["on"]["push"]["tags"] == ["v*"]
    text = (WORKFLOWS / "publish.yml").read_text(encoding="utf-8")
    assert "GITEA_PYPI_URL" in text
    assert "upload.pypi.org" not in text
    assert "pypa/gh-action-pypi-publish" not in text
