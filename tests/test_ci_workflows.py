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


def test_ci_runs_tests_lint_types_and_validates_the_quest_log():
    commands = _run_lines(_load("ci.yml"))
    for expected in ("pytest", "ruff check", "mypy", "quest validate"):
        assert expected in commands


def test_ci_does_not_require_the_whole_quest_log_to_be_format_clean():
    """Quest files are re-formatted by the pre-commit hook when they are next
    touched, so a whole-log `quest format --check` would fail on every file that
    has not been touched since the format changed."""
    assert "quest format --check" not in _run_lines(_load("ci.yml"))


def test_pip_caching_names_its_dependency_file():
    """actions/setup-python's `cache: pip` fails the job when no requirements.txt
    exists unless it is told which file to hash."""
    for job in _load("ci.yml")["jobs"].values():
        for step in job["steps"]:
            if step.get("with", {}).get("cache") == "pip":
                assert step["with"]["cache-dependency-path"] == "pyproject.toml"


def test_ci_scans_the_history_for_secrets_on_github():
    job = _load("ci.yml")["jobs"]["secrets"]
    assert "github.com" in job["if"]
    assert any("gitleaks" in step.get("uses", "") for step in job["steps"])
    assert job["steps"][0]["with"]["fetch-depth"] == 0


def test_publish_triggers_on_version_tags_and_targets_the_private_registry():
    workflow = _load("publish.yml")
    assert workflow["on"]["push"]["tags"] == ["v*"]
    text = (WORKFLOWS / "publish.yml").read_text(encoding="utf-8")
    assert "PYPI_REGISTRY_URL" in text
    assert "upload.pypi.org" not in text
    assert "pypa/gh-action-pypi-publish" not in text


def test_publish_avoids_what_gitea_actions_does_not_support():
    """Gitea reserves the GITEA_/GITHUB_ prefixes for secrets and variables, and
    does not support v4 of the artifact actions."""
    text = (WORKFLOWS / "publish.yml").read_text(encoding="utf-8")
    assert "secrets.GITEA_" not in text and "vars.GITEA_" not in text
    assert "upload-artifact" not in text and "download-artifact" not in text


def test_publish_can_be_dry_run_with_a_dev_version():
    workflow = _load("publish.yml")
    assert "workflow_dispatch" in workflow["on"]
    steps = workflow["jobs"]["publish"]["steps"]
    dev = next(s for s in steps if "dev version" in s.get("name", ""))
    tag = next(s for s in steps if "Tag matches" in s.get("name", ""))
    assert "ref_type != 'tag'" in dev["if"] and ".dev" in dev["run"]
    assert "ref_type == 'tag'" in tag["if"]


def test_publish_is_skipped_where_no_registry_is_configured():
    job = _load("publish.yml")["jobs"]["publish"]
    assert "vars.PYPI_REGISTRY_URL" in job["if"]


def _hook_config() -> dict:
    return yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))


def test_quest_hooks_do_not_run_on_push():
    """A hook with no `stages` runs at every installed stage. The quest hooks
    rewrite and stage files, which on `git push` re-dirties quest files that were
    deliberately left alone, so they must be limited to the commit stage."""
    assert _hook_config()["default_stages"] == ["pre-commit"]


def test_the_push_scan_declares_the_push_stage():
    hooks = {h["id"]: h for r in _hook_config()["repos"] for h in r["hooks"]}
    assert hooks["sensitive-scan-push"]["stages"] == ["pre-push"]
