"""The Quest file model: YAML frontmatter + Markdown body, round-tripped."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.scalarstring import DoubleQuotedScalarString, SingleQuotedScalarString

_yaml = YAML()
_yaml.preserve_quotes = True
_yaml.indent(mapping=2, sequence=4, offset=2)
_yaml.width = 4096  # keep fields like `description` on one line -- greppability matters more
# than 80-column wrapping for a frontmatter file.

# Fields whose value is a plain YYYY-MM-DD date, per the frontmatter schema.
_DATE_FIELDS = ("created", "modified", "due")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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
        _normalize_list_styles(self.frontmatter)
        _normalize_date_fields(self.frontmatter)
        _normalize_quote_styles(self.frontmatter)
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


def _normalize_list_styles(mapping: CommentedMap) -> None:
    """Flow style (`[]`) only for an empty list, block style (one per line) otherwise.

    Matches Obsidian's own frontmatter writer, which always expands a
    non-empty array to one item per line -- even a single-item `aliases:
    [QST-x7k2m]` becomes block style the moment Obsidian touches the file.
    Matching that here means the two tools converge on one style instead of
    alternating it back and forth every time the file changes hands.
    Applied on every save, so hand-edited or Obsidian-touched files
    self-correct the next time any quest command (or the bump-modified
    hook) touches them.
    """
    for key in list(mapping.keys()):
        value = mapping[key]
        if not isinstance(value, list):
            continue
        seq = value if isinstance(value, CommentedSeq) else CommentedSeq(value)
        if len(seq) == 0:
            seq.fa.set_flow_style()
        else:
            seq.fa.set_block_style()
        mapping[key] = seq


def _normalize_date_fields(mapping: CommentedMap) -> None:
    """`created`/`modified`/`due` become real `date` objects when they look like one.

    A real `date` value always dumps as a bare `2026-08-13` -- ruamel only
    adds quotes around a *string* that happens to look like a date, to stop
    it from silently turning into a date on the next load. Obsidian's own
    writer never adds that quoting in the first place, so without this a
    CLI-touched file and an Obsidian-touched file would fight over quoting
    the same field forever. Applied on every save, so a string value
    (freshly typed, or preserved from a previously-quoted file) converts the
    moment any quest command or the bump-modified hook next touches it.
    """
    for key in _DATE_FIELDS:
        value = mapping.get(key)
        if isinstance(value, str) and _ISO_DATE_RE.match(value):
            mapping[key] = date.fromisoformat(value)


def _normalize_quote_styles(mapping: CommentedMap) -> None:
    """Any single-quoted scalar becomes double-quoted, recursively into lists.

    Obsidian double-quotes any string that needs quoting at all; ruamel's
    own default, left to itself, is single-quotes. Converging both tools on
    double quotes (rather than leaving whichever one wrote the file last in
    charge) is what stops the quote style from flipping back and forth.
    """
    for key in list(mapping.keys()):
        mapping[key] = _double_quote(mapping[key])


def _double_quote(value):
    if isinstance(value, SingleQuotedScalarString):
        return DoubleQuotedScalarString(str(value))
    if isinstance(value, CommentedSeq):
        for index, item in enumerate(value):
            value[index] = _double_quote(item)
    return value


def find_by_id(quests_dir: Path, quest_id: str) -> Path | None:
    """Find a quest file by id, matching either `ID--slug.md` or bare `ID.md`."""
    matches = sorted(quests_dir.glob(f"{quest_id}*.md"))
    return matches[0] if matches else None
