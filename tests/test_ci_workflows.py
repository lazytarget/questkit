"""Guards for QST-tf4wc: CI lives in `.github/workflows`, covers the supported
Python range, and each registry has its own publish workflow: `publish-gitea.yml`
for the private Gitea registry and `publish-pypi.yml` for PyPI. Both live in the
same directory and both runners read it, so each is guarded to run only on the
host it is meant for."""

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


GITHUB = "https://github.com"


def _text(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def _steps(job: dict) -> list:
    return job["steps"]


# --- publish-gitea.yml: the private Gitea registry ---------------------------------


def test_the_old_publish_workflow_name_is_gone():
    assert not (WORKFLOWS / "publish.yml").exists()
    assert (WORKFLOWS / "publish-gitea.yml").exists()


def test_gitea_publish_runs_on_version_tags_and_by_hand():
    on = _load("publish-gitea.yml")["on"]
    assert on["push"]["tags"] == ["v*"]
    assert "workflow_dispatch" in on


def test_gitea_publish_targets_the_private_registry_and_never_pypi():
    text = _text("publish-gitea.yml")
    assert "PYPI_REGISTRY_URL" in text
    assert "upload.pypi.org" not in text
    assert "pypa/gh-action-pypi-publish" not in text
    assert "PYPI_API_TOKEN" not in text


def test_gitea_publish_avoids_what_gitea_actions_does_not_support():
    """Gitea reserves the GITEA_/GITHUB_ prefixes for secrets and variables, and
    does not support v4 of the artifact actions."""
    text = _text("publish-gitea.yml")
    assert "secrets.GITEA_" not in text and "vars.GITEA_" not in text
    assert "upload-artifact" not in text and "download-artifact" not in text


def test_gitea_manual_runs_publish_a_dev_version_only():
    steps = _steps(_load("publish-gitea.yml")["jobs"]["publish"])
    dev = next(s for s in steps if "dev version" in s.get("name", ""))
    tag = next(s for s in steps if "Tag matches" in s.get("name", ""))
    assert "ref_type != 'tag'" in dev["if"] and ".dev" in dev["run"]
    assert "ref_type == 'tag'" in tag["if"]


def test_gitea_publish_needs_a_configured_registry_and_never_runs_on_github():
    """Skipped where no registry is configured, and also on github.com even if
    someone sets the variable there."""
    condition = _load("publish-gitea.yml")["jobs"]["publish"]["if"]
    assert "vars.PYPI_REGISTRY_URL" in condition
    assert f"github.server_url != '{GITHUB}'" in condition


# --- publish-pypi.yml: PyPI, from GitHub only --------------------------------------


def test_pypi_publish_runs_on_version_tags_and_by_hand():
    on = _load("publish-pypi.yml")["on"]
    assert on["push"]["tags"] == ["v*"]
    publish = on["workflow_dispatch"]["inputs"]["publish"]
    assert publish["type"] == "boolean"
    assert publish["default"] is False, "a manual run must be a dry run unless asked"


def test_every_pypi_job_runs_on_github_only():
    """The Gitea runner reads this directory too. Its artifact actions are v3-only,
    so a PyPI job there could only fail, and must never see PyPI credentials."""
    for name, job in _load("publish-pypi.yml")["jobs"].items():
        assert f"github.server_url == '{GITHUB}'" in job["if"], name


def test_pypi_publishing_is_trusted_publishing_with_no_secret_at_all():
    """PyPI only accepts attestations (the provenance shown on the project page)
    from trusted publishing, and the action ignores that path when a password is
    passed. So there must be no token anywhere in this workflow."""
    text = _text("publish-pypi.yml")
    assert "secrets." not in text
    assert "PYPI_API_TOKEN" not in text
    assert "twine upload" not in text
    for job in _load("publish-pypi.yml")["jobs"].values():
        for step in _steps(job):
            assert "password" not in step.get("with", {}), step
            assert not any(k.startswith("TWINE_") for k in step.get("env", {})), step


def test_only_the_publish_job_can_request_an_identity_token_and_it_sits_behind_the_pypi_environment():
    jobs = _load("publish-pypi.yml")["jobs"]
    assert jobs["publish"]["environment"]["name"] == "pypi"
    assert jobs["publish"]["permissions"] == {"id-token": "write"}
    assert "environment" not in jobs["build"]
    assert "permissions" not in jobs["build"], "the build runs project code and inherits read-only contents"
    assert "id-token" not in str(_load("publish-pypi.yml")["permissions"])


def test_the_publish_job_runs_no_project_code():
    """It can mint an identity token, so it only downloads the built files and uploads them."""
    publish = _load("publish-pypi.yml")["jobs"]["publish"]
    assert publish["needs"] == "build"
    for step in _steps(publish):
        assert "actions/checkout" not in step.get("uses", "")
        run = step.get("run", "")
        assert "python -m build" not in run and "pip install -e" not in run


def test_pypi_publishes_only_from_a_tag_and_a_manual_run_must_ask_for_it():
    condition = _load("publish-pypi.yml")["jobs"]["publish"]["if"]
    assert "github.ref_type == 'tag'" in condition
    assert "github.event_name == 'push'" in condition
    assert "inputs.publish" in condition


def test_pypi_build_checks_the_tag_against_the_package_version():
    steps = _steps(_load("publish-pypi.yml")["jobs"]["build"])
    check = next(s for s in steps if "Tag matches" in s.get("name", ""))
    assert "ref_type == 'tag'" in check["if"]
    assert "pyproject.toml" in check["run"]


def test_pypi_upload_uses_the_official_action_so_attestations_are_generated():
    steps = _steps(_load("publish-pypi.yml")["jobs"]["publish"])
    upload = next(s for s in steps if "pypa/gh-action-pypi-publish" in s.get("uses", ""))
    assert upload["uses"] == "pypa/gh-action-pypi-publish@release/v1"
    assert "with" not in upload or "password" not in upload["with"]
    assert upload.get("with", {}).get("attestations", True) is not False


def test_the_publish_job_links_to_the_pypi_project_page():
    env = _load("publish-pypi.yml")["jobs"]["publish"]["environment"]
    assert env["url"] == "https://pypi.org/p/questkit"


def test_pypi_publishes_do_not_overlap():
    assert _load("publish-pypi.yml")["concurrency"]["cancel-in-progress"] is False


# --- the two workflows must never publish to each other's registry ----------------


def test_each_registry_has_its_own_credentials_and_neither_crosses_over():
    gitea, pypi = _text("publish-gitea.yml"), _text("publish-pypi.yml")
    assert "PYPI_API_TOKEN" not in gitea
    assert "PYPI_REGISTRY" not in pypi


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
