"""The Quest file model: YAML frontmatter + Markdown body, round-tripped."""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

_yaml = YAML()
_yaml.preserve_quotes = True
_yaml.indent(mapping=2, sequence=4, offset=2)
_yaml.width = 4096  # keep fields like `description` on one line -- greppability matters more
# than 80-column wrapping for a frontmatter file.


class QuestFileError(Exception):
    """Raised when a quest file's frontmatter cannot be parsed."""


@dataclass
class Quest:
    """A single quest: its file path, parsed frontmatter, and Markdown body."""

    path: Path
    frontmatter: CommentedMap
    body: str

    @classmethod
    def load(cls, path: Path) -> Quest:
        text = path.read_text(encoding="utf-8")
        raw_yaml, body = _split_frontmatter(text, path)
        frontmatter = _yaml.load(raw_yaml)
        if frontmatter is None:
            frontmatter = CommentedMap()
        return cls(path=path, frontmatter=frontmatter, body=body)

    def save(self) -> None:
        buf = io.StringIO()
        _yaml.dump(self.frontmatter, buf)
        body = self.body.strip("\n")
        content = f"---\n{buf.getvalue()}---\n\n{body}\n"
        self.path.write_text(content, encoding="utf-8")

    def get(self, key, default=None):
        return self.frontmatter.get(key, default)

    def set(self, key, value) -> None:
        self.frontmatter[key] = value


def _split_frontmatter(text: str, path: Path) -> tuple[str, str]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise QuestFileError(f"{path}: missing YAML frontmatter block")

    end_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end_index = index
            break
    if end_index is None:
        raise QuestFileError(f"{path}: frontmatter block is never closed")

    raw_yaml = "".join(lines[1:end_index])
    body = "".join(lines[end_index + 1 :])
    return raw_yaml, body.lstrip("\n")


def find_by_id(quests_dir: Path, quest_id: str) -> Path | None:
    """Find a quest file by id, matching either `ID--slug.md` or bare `ID.md`."""
    matches = sorted(quests_dir.glob(f"{quest_id}*.md"))
    return matches[0] if matches else None
