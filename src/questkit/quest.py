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
_DATE_FIELDS = ("created", "status_changed", "modified", "due")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Where a newly-introduced key belongs. Only for fields whose position carries
# meaning; everything else appends.
_INSERT_AFTER = {"status_changed": "created"}


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
        return cls.from_text(path, path.read_text(encoding="utf-8"))

    @classmethod
    def from_text(cls, path: Path, text: str) -> Quest:
        """Parse already-read file content -- the same parsing `load()` does,
        split out for a caller reading a version other than what's on disk
        (e.g. `git show HEAD:<path>`, in `hooks.py`'s status-transition
        backfill and `commit_cmd.py`'s message-building)."""
        raw_yaml, body = _split_frontmatter(text, path)
        frontmatter = _yaml.load(raw_yaml)
        if frontmatter is None:
            frontmatter = CommentedMap()
        return cls(path=path, frontmatter=frontmatter, body=body)

    def reorder(self, schema_config) -> None:
        """Reorder frontmatter to the schema's `field_order`.

        Not folded into `render()`: rendering must stay schema-agnostic so the
        pre-commit hooks and `Quest.load(...).save()` keep working on a file
        whose log cannot be resolved. Callers that *have* a schema (the
        `format` command, `new`) call this first.
        """
        ordered = CommentedMap()
        for key in sorted(self.frontmatter.keys(), key=schema_config.order_key):
            ordered[key] = self.frontmatter[key]
        self.frontmatter = ordered

    def render(self) -> str:
        """The exact file content `save()` would write, without writing it.

        Split out from `save()` so `quest format --check` and
        `quest migrate --dry-run` can ask "what would change" using the same
        code path that answers "what changed". Anything short of running the
        real normalization passes and ruamel's own dump would drift from
        `save()` and turn `--check` into a guess.

        Note this normalizes `self.frontmatter` in place, as `save()` always
        has -- the passes are idempotent, so calling it twice is harmless.
        """
        _normalize_list_styles(self.frontmatter)
        _normalize_date_fields(self.frontmatter)
        _normalize_quote_styles(self.frontmatter)
        buf = io.StringIO()
        _yaml.dump(self.frontmatter, buf)
        body = self.body.strip("\n")
        # Always one blank line before EOF: the body ends in `\n\n`.
        return f"---\n{buf.getvalue()}---\n\n{body}\n\n"

    def save(self) -> bool:
        """Normalize and write. Returns True only if the file's bytes changed.

        The comparison lives here rather than in each caller for a reason:
        `format_cmd` and `hooks.format_main` both used to read the file, save
        unconditionally, then re-read to find out whether anything happened --
        so the third caller was going to get it wrong too. Writing
        unconditionally also has three real costs. An mtime-based quiescence
        gate becomes unusable, which is what the designated committer polls
        for; a `git: auto` log accumulates empty commits; and Syncthing
        propagates files whose content never changed, which on a fleet with 15
        `.git` directories is how conflict litter starts.
        """
        content = self.render()
        if self.path.exists() and self.path.read_text(encoding="utf-8") == content:
            return False
        self.path.write_text(content, encoding="utf-8")
        return True

    def append_log(self, message: str, when: str) -> None:
        """Append `- YYYY-MM-DD: message` to the body's `## Log` section (QST-46rdv).

        Creates the section at the end of the body when missing -- `--log`
        must work on any quest, not just ones seeded from the packaged
        template. Appending anywhere but the end of the existing section
        would put the newest entry out of chronological reading order.
        """
        self.body = _append_log_entry(self.body, when, message)

    def get(self, key, default=None):
        return self.frontmatter.get(key, default)

    def set(self, key, value) -> None:
        """Set a field, placing a *newly introduced* key at its conventional position.

        Appending would be valid YAML and wrong for a human reader:
        `created`, `status_changed` and `modified` read as a timeline, so a
        `status_changed` landing after `blocked_by` is noise. Found on the
        real corpus -- the rule first lived in `set_cmd`, so `quest migrate`,
        the command that introduces the field to 122 files, did not have it.
        One rule, every writer.

        QST-j68u5 generalizes this into a schema-declared `field_order`; this
        is the minimum that keeps the file readable until then.
        """
        if key in self.frontmatter:
            self.frontmatter[key] = value
            return

        anchor = _INSERT_AFTER.get(key)
        keys = list(self.frontmatter.keys())
        if anchor is None or anchor not in keys:
            self.frontmatter[key] = value
            return
        self.frontmatter.insert(keys.index(anchor) + 1, key, value)


_LOG_HEADING_RE = re.compile(r"^##[ \t]+Log[ \t]*$", re.MULTILINE)
_HEADING_RE = re.compile(r"^##[ \t]+\S", re.MULTILINE)


def _append_log_entry(body: str, when: str, message: str) -> str:
    """Append `- when: message` to `body`'s `## Log` section, creating it if absent."""
    bullet = f"- {when}: {message}"
    heading = _LOG_HEADING_RE.search(body)
    if heading is None:
        stripped = body.rstrip("\n")
        sep = "\n\n" if stripped else ""
        return f"{stripped}{sep}## Log\n\n{bullet}\n"

    section_start = heading.end()
    next_heading = _HEADING_RE.search(body, section_start)
    section_end = next_heading.start() if next_heading else len(body)
    section = body[section_start:section_end].rstrip("\n")

    new_section = f"{section}\n{bullet}\n" if section.strip() else f"\n\n{bullet}\n"
    tail = body[section_end:]
    if next_heading and not new_section.endswith("\n\n"):
        new_section += "\n"
    return body[:section_start] + new_section + tail


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


def effective_status_changed(frontmatter) -> str | None:
    """`status_changed`, falling back to `created` when it is absent or blank.

    Null-safe by design rather than by backfill: the field is optional, and
    every consumer (`idle`, `stale`, `quest brief`) has to answer for a quest
    that predates it. Returning `created` is the honest answer -- a quest
    whose status has never been recorded as changing has not moved since it
    was created.

    Deliberately not `modified`: that field is bumped by the pre-commit hook
    on every commit, so falling back to it would reintroduce the exact
    laundering `status_changed` exists to prevent.
    """
    for key in ("status_changed", "created"):
        value = frontmatter.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return None


def load_frontmatter_only(path: Path) -> CommentedMap:
    """Parse just a quest file's frontmatter block, without its body.

    `quest list`'s common case (QST-vy4vt/QST-bo3xs) never touches the body
    text at all -- `--where`/`--select`/`--sort` on `body`, `criteria_done`
    or `criteria_total` are the only things that need it. Stopping at the
    closing `---` line, rather than reading the whole file the way
    `Quest.load` does, means a query that never references the body pays
    nothing for a quest with a huge one.
    """
    with path.open("r", encoding="utf-8") as handle:
        first = handle.readline()
        if first.strip() != "---":
            raise QuestFileError(f"{path}: missing YAML frontmatter block")
        raw_lines: list[str] = []
        closed = False
        for line in handle:
            if line.strip() == "---":
                closed = True
                break
            raw_lines.append(line)
    if not closed:
        raise QuestFileError(f"{path}: frontmatter block is never closed")
    frontmatter = _yaml.load("".join(raw_lines))
    return frontmatter if frontmatter is not None else CommentedMap()


def find_by_id(quests_dir: Path, quest_id: str) -> Path | None:
    """Find a quest file by id, matching either `ID--slug.md` or bare `ID.md`.

    Excludes Syncthing conflict copies (QST-oe92z): `ID*.md` alone also
    matches `ID--slug.sync-conflict-TIMESTAMP-DEVICE.md`, since Syncthing
    inserts the marker *before* the extension rather than after the glob's
    reach. Left unfiltered, id resolution would only "work" by accident of
    `.md` sorting before `.sync-conflict-...`.
    """
    matches = sorted(
        p for p in quests_dir.glob(f"{quest_id}*.md") if not is_sync_conflict_copy(p.name)
    )
    return matches[0] if matches else None


# Syncthing inserts this marker before the extension on a conflicting write:
# `ID--slug.md` -> `ID--slug.sync-conflict-20260814-120000-ABCDEFG.md`. Any
# glob shaped like `ID*.md` or `QST-*.md` matches a conflict copy too (`*`
# doesn't stop at a literal `.`), so every enumeration site needs the same
# exclusion -- see `glob_quests` and `find_by_id` above.
SYNC_CONFLICT_MARKER = ".sync-conflict-"


def is_sync_conflict_copy(name: str) -> bool:
    """Whether a filename is a Syncthing conflict copy."""
    return SYNC_CONFLICT_MARKER in name


def glob_quests(quests_dir: Path, pattern: str) -> list[Path]:
    """Every file matching `pattern` in `quests_dir`, sorted, conflict copies excluded.

    The one enumeration point every command should glob through (`list`,
    `validate`, `logs`, `deps`, `migrate`, `archive`, `brief`, `format`) --
    a bare `quests_dir.glob(config.pattern)` picks up Syncthing conflict
    copies as phantom/duplicate quests (QST-oe92z).
    """
    return sorted(p for p in quests_dir.glob(pattern) if not is_sync_conflict_copy(p.name))


def count_sync_conflicts(quests_dir: Path, pattern: str) -> int:
    """How many conflict copies of quest files exist in `quests_dir`, matching `pattern`."""
    return sum(1 for p in quests_dir.glob(pattern) if is_sync_conflict_copy(p.name))
