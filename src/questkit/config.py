"""Per-log configuration: `.questkit.yaml` inside a quests/ directory."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ruamel.yaml import YAML

from . import schema

CONFIG_FILENAME = ".questkit.yaml"
CONFIG_VERSION = 1

_DEFAULT_FIELD_DEFAULTS = {"type": "task", "status": "draft", "priority": "medium"}
_IGNORE_INCLUDE_PREFIX = "#include "

_yaml = YAML()
_yaml.preserve_quotes = True
_yaml.indent(mapping=2, sequence=4, offset=2)
_yaml.width = 4096


class ConfigVersionError(Exception):
    """Raised when a `.questkit.yaml` declares a version this questkit can't read."""


class IgnoreConfigError(Exception):
    """Raised when an `ignore:` entry's `#include` chain is circular or unresolvable."""


@dataclass
class QuestLogConfig:
    """Configuration for a single quest log (a `quests/` directory)."""

    version: int = CONFIG_VERSION
    pattern: str = "QST-*.md"
    prefix: str = "QST-"
    id_length: int = 5
    git: str = "manual"  # "auto" | "manual"
    project: str | None = None
    defaults: dict = field(default_factory=lambda: dict(_DEFAULT_FIELD_DEFAULTS))
    ignore: list = field(default_factory=list)  # raw entries, may include '#include <path>'
    schema: schema.SchemaConfig = field(default_factory=schema.SchemaConfig.default)
    tracked: list | None = None  # None = the default set, derived from `pattern`

    @classmethod
    def load(cls, quests_dir: Path) -> QuestLogConfig:
        config_path = quests_dir / CONFIG_FILENAME
        with config_path.open("r", encoding="utf-8") as handle:
            data = _yaml.load(handle) or {}

        version = data.get("version", CONFIG_VERSION)
        if version != CONFIG_VERSION:
            raise ConfigVersionError(
                f"{config_path}: config version {version} is not supported by this "
                f"questkit (expected {CONFIG_VERSION}). Upgrade questkit or migrate "
                "the config."
            )

        return cls(
            version=version,
            pattern=data.get("pattern", cls.pattern),
            prefix=data.get("prefix", cls.prefix),
            id_length=data.get("id_length", cls.id_length),
            git=data.get("git", cls.git),
            project=data.get("project"),
            defaults={**_DEFAULT_FIELD_DEFAULTS, **(data.get("defaults") or {})},
            ignore=list(data.get("ignore") or []),
            schema=schema.SchemaConfig.load(quests_dir, _schema_block(data.get("schema"))),
            tracked=list(data["tracked"]) if "tracked" in data else None,
        )

    def resolved_ignores(self, quests_dir: Path) -> list[str]:
        """This log's `ignore:` entries, with any `#include <path>` directives expanded."""
        return _resolve_ignore_entries(self.ignore, base_dir=quests_dir)

    def resolved_tracked(self) -> list[str]:
        """The pathspec `quest commit` stages and commits, in effect.

        Deliberately excludes `_validation.md` -- it's derived state whose
        transport is Syncthing, not git; a designated-committer machine
        would otherwise commit its own transient findings on every run.
        """
        if self.tracked is not None:
            return list(self.tracked)
        return [self.pattern, CONFIG_FILENAME, ".gitignore", "_template.md", "quests.base"]

    def save(self, quests_dir: Path) -> None:
        config_path = quests_dir / CONFIG_FILENAME
        data = {
            "version": self.version,
            "pattern": self.pattern,
            "prefix": self.prefix,
            "id_length": self.id_length,
            "git": self.git,
            "defaults": dict(self.defaults),
        }
        if self.project:
            data["project"] = self.project
        with config_path.open("w", encoding="utf-8") as handle:
            handle.write("---\n")
            _yaml.dump(data, handle)


def _schema_block(value) -> dict | None:
    """`schema: development` is shorthand for `schema: {extends: development}`.

    The common case by far -- four logs sharing one named schema and adding
    nothing -- so it should not require a nested block whose only key is
    `extends`.
    """
    if isinstance(value, str):
        return {"extends": value}
    return value


def config_exists(quests_dir: Path) -> bool:
    """Whether `quests_dir` is already a quest log (has a `.questkit.yaml`)."""
    return (quests_dir / CONFIG_FILENAME).is_file()


def _resolve_ignore_entries(
    entries: list, base_dir: Path, _visited: frozenset = frozenset()
) -> list[str]:
    """Expand `#include <path>` entries in an `ignore:` list, recursively.

    Mirrors the Realm's own `syncthing.yaml` / `#include` convention (see
    `99-system/scripts/scaffold_syncthing.py`'s `resolve_stignore`): an entry
    starting with `#include ` (path relative to `base_dir`) pulls in another
    file's lines as further patterns -- comments (`//` or bare `#`) are
    skipped, everything else is a literal directory-name/glob pattern. A
    circular or missing include target is a loud error, not a silent skip.
    """
    patterns: list[str] = []
    for raw in entries:
        stripped = str(raw).strip()
        if not stripped:
            continue
        if stripped.startswith(_IGNORE_INCLUDE_PREFIX):
            target = (base_dir / stripped[len(_IGNORE_INCLUDE_PREFIX) :].strip()).expanduser().resolve()
            if target in _visited:
                raise IgnoreConfigError(f"circular ignore '#include' chain at {target}")
            if not target.is_file():
                raise IgnoreConfigError(f"ignore '#include {stripped[len(_IGNORE_INCLUDE_PREFIX):]}' -> {target} not found")
            target_lines = target.read_text(encoding="utf-8").splitlines()
            patterns.extend(_resolve_ignore_entries(target_lines, target.parent, _visited | {target}))
        elif stripped.startswith("//") or stripped.startswith("#"):
            continue  # comment
        else:
            patterns.append(stripped)
    return patterns
