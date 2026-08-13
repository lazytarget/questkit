"""Per-log configuration: `.questkit.yaml` inside a quests/ directory."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ruamel.yaml import YAML

CONFIG_FILENAME = ".questkit.yaml"
CONFIG_VERSION = 1

_DEFAULT_FIELD_DEFAULTS = {"type": "task", "status": "draft", "priority": "medium"}

_yaml = YAML()
_yaml.preserve_quotes = True
_yaml.indent(mapping=2, sequence=4, offset=2)
_yaml.width = 4096


class ConfigVersionError(Exception):
    """Raised when a `.questkit.yaml` declares a version this questkit can't read."""


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
        )

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
            _yaml.dump(data, handle)


def config_exists(quests_dir: Path) -> bool:
    """Whether `quests_dir` is already a quest log (has a `.questkit.yaml`)."""
    return (quests_dir / CONFIG_FILENAME).is_file()
