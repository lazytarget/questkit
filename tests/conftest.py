"""Shared fixtures for building quest logs, schemas and quests in a tmp_path.

Every test file before this one rolled its own setup: `monkeypatch.chdir` +
`main(["init"])`, then `main(["new", ...])` for each quest, then scraping the
created id back out of stdout. That works for a single log with CLI-shaped
quests, and stops working as soon as a test needs a *precise* corpus -- a
quest missing `status_changed`, a log whose schema overrides `statuses:`, three
logs under one root with one of them broken.

So the fixtures here are deliberately two-layered:

- `write_quest` / `make_log` / `write_schema` build files **directly**, so a
  test can state exactly the corpus it means, including states the CLI would
  refuse to create. This is what the migration, computed-field and multi-log
  tests need.
- `quest_log` / `run` drive the **CLI**, for the tests whose subject is the
  command surface rather than the data.

Reaching for the direct writers when the subject is really the CLI is how you
get a test that passes against a corpus no user could ever produce, so prefer
`run` unless the setup genuinely needs otherwise.
"""

from __future__ import annotations

import io
import textwrap
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from questkit.cli import main

_yaml = YAML()
_yaml.indent(mapping=2, sequence=4, offset=2)
_yaml.width = 4096

# A quest that satisfies today's `validate_quest` hard rules, so a test that
# cares about one field can override just that field and still start from a
# valid file rather than from a pile of unrelated validation errors.
_QUEST_DEFAULTS = {
    "title": "A quest",
    "description": "A quest that exists for a test to look at.",
    "created": date(2026, 1, 1),
    "modified": date(2026, 1, 1),
    "type": "task",
    "status": "todo",
    "priority": "medium",
    "tags": ["test"],
}

_DEFAULT_BODY = "## Description\n\nA quest."


class _Absent:
    """Sentinel for 'omit this field entirely', distinct from a None value.

    `write_quest(log, "QST-x", status_changed=absent)` is the null-safety case
    for `idle`; `status_changed=None` would write an explicit null, which is a
    different file and a different test.
    """

    def __repr__(self) -> str:
        return "ABSENT"


_ABSENT = _Absent()


@dataclass
class Result:
    """The outcome of one CLI invocation: exit code plus captured streams."""

    code: int
    out: str
    err: str

    @property
    def lines(self) -> list[str]:
        return [line for line in self.out.splitlines() if line.strip()]

    def __repr__(self) -> str:  # pragma: no cover - debugging aid on assert failure
        return f"Result(code={self.code}, out={self.out!r}, err={self.err!r})"


@pytest.fixture
def run():
    """Invoke the CLI in-process and capture both streams.

    In-process rather than `subprocess`: it keeps tracebacks real, lets
    `monkeypatch` reach the code under test, and runs fast enough that a
    test can afford a dozen invocations. The cost is that `main`'s top-level
    `except` boundary is exercised for real, which is the behavior we want to
    assert on anyway.
    """

    def _run(*argv: str) -> Result:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(argv))
        return Result(code=code, out=out.getvalue(), err=err.getvalue())

    return _run


@pytest.fixture
def write_quest():
    """Write a quest file directly, bypassing `quest new` and its defaults.

    Frontmatter keys are written in the order given after the id, so a test
    about `field_order` can set up a deliberately wrong order. Pass
    `body=None` for the minimal body, or a string for an exact one --
    readiness and brief tests need real `## Spec` / `## Acceptance Criteria`
    sections.
    """

    def _write(log: Path, quest_id: str, *, slug: str = "a-quest", body: str | None = None, **fields) -> Path:
        frontmatter: dict = {"id": quest_id}
        merged = {**_QUEST_DEFAULTS, **fields}
        for key, value in merged.items():
            if value is _ABSENT:
                continue
            frontmatter[key] = value
        frontmatter.setdefault("aliases", [quest_id])

        buf = io.StringIO()
        _yaml.dump(frontmatter, buf)
        text = f"---\n{buf.getvalue()}---\n\n{(body or _DEFAULT_BODY).strip()}\n"

        path = log / f"{quest_id}--{slug}.md"
        path.write_text(text, encoding="utf-8")
        return path

    return _write


@pytest.fixture
def absent():
    return _ABSENT


@pytest.fixture
def make_log():
    """Create a quest log directory with a `.questkit.yaml`, without the CLI.

    `schema` and any extra config keys go in verbatim, so a test can declare
    a log that today's `QuestLogConfig` does not yet know how to read -- which
    is exactly the red state a new config key starts from.
    """

    def _make(
        root: Path,
        name: str = "quests",
        *,
        project: str | None = None,
        git: str = "manual",
        schema: dict | None = None,
        **config,
    ) -> Path:
        log = root / name if name == "quests" else root / name / "quests"
        log.mkdir(parents=True, exist_ok=True)

        data: dict = {
            "version": 1,
            "pattern": "QST-*.md",
            "prefix": "QST-",
            "id_length": 5,
            "git": git,
        }
        if project is not None:
            data["project"] = project
        elif name != "quests":
            data["project"] = name
        if schema is not None:
            data["schema"] = schema
        data.update(config)

        buf = io.StringIO()
        _yaml.dump(data, buf)
        (log / ".questkit.yaml").write_text(f"---\n{buf.getvalue()}", encoding="utf-8")
        return log

    return _make


@pytest.fixture
def write_schema():
    """Write a standalone schema YAML file, for `extends:` and named-schema tests."""

    def _write(directory: Path, name: str, body: str | dict) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{name}.yaml"
        if isinstance(body, dict):
            buf = io.StringIO()
            _yaml.dump(body, buf)
            path.write_text(buf.getvalue(), encoding="utf-8")
        else:
            path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
        return path

    return _write


@pytest.fixture
def quest_log(tmp_path, monkeypatch):
    """A single CLI-created log at `tmp_path/quests`, with cwd inside it.

    `QUEST_LOG` and `QST_ROOT` are cleared: both are read from the real
    environment, and a developer who exports either would otherwise see
    tests resolve against their own vault.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("QUEST_LOG", raising=False)
    monkeypatch.delenv("QST_ROOT", raising=False)
    assert main(["init"]) == 0
    return tmp_path / "quests"


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """cwd inside an empty tmp_path with the questkit env vars cleared.

    For tests that must control log creation themselves -- `quest init`'s own
    tests, multi-log sweeps, and anything asserting on a "no quest log found"
    error.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("QUEST_LOG", raising=False)
    monkeypatch.delenv("QST_ROOT", raising=False)
    return tmp_path


@pytest.fixture
def multi_log(isolated, make_log, write_quest, monkeypatch):
    """Three logs under one sweep root, with `QST_ROOT` pointed at it.

    Shaped after the real Realm: distinct project names, a mix of `git`
    modes, and quests spread across statuses so a default-filter or
    grouping assertion has something to bite on. Returns the log paths by
    project name.
    """
    alpha = make_log(isolated, "alpha", git="manual")
    beta = make_log(isolated, "beta", git="auto")
    gamma = make_log(isolated, "gamma", git="manual")

    write_quest(alpha, "QST-a1aaa", title="Alpha one", status="todo", priority="high")
    write_quest(alpha, "QST-a2aaa", title="Alpha two", status="completed", priority="low")
    write_quest(beta, "QST-b1bbb", title="Beta one", status="in-progress", priority="critical")
    write_quest(gamma, "QST-g1ggg", title="Gamma one", status="todo", priority="medium")
    write_quest(gamma, "QST-g2ggg", title="Gamma two", status="draft", priority="medium")

    monkeypatch.setenv("QST_ROOT", str(isolated))
    return {"root": isolated, "alpha": alpha, "beta": beta, "gamma": gamma}
