"""`quest validate` — check quests in a log against the schema."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from .. import schema
from ..config import CONFIG_FILENAME, ConfigVersionError, QuestLogConfig, config_exists
from ..discovery import QuestLogNotFoundError, resolve_by_name_or_path, resolve_log
from ..quest import Quest, QuestFileError, find_by_id

_WIKILINK_ID_RE = re.compile(r"\[\[(QST-[0-9a-z]{5})")
_FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")


def run(args: argparse.Namespace) -> int:
    quests_dir = resolve_log(explicit=args.in_dir)
    if not config_exists(quests_dir):
        print(f"[quest validate] {quests_dir}: no {CONFIG_FILENAME} found")
        return 1

    try:
        config = QuestLogConfig.load(quests_dir)
    except ConfigVersionError as exc:
        print(f"[quest validate] {exc}")
        return 1

    _warn_validation_theater(config)

    checked = 0
    total_errors = 0
    total_notes = 0
    report_sections: list[str] = []
    for path in sorted(quests_dir.glob(config.pattern)):
        checked += 1
        try:
            quest = Quest.load(path)
        except QuestFileError as exc:
            print(f"[!] {exc}")
            total_errors += 1
            report_sections.append(f"## {path}\n\n- error: {exc}\n")
            continue

        errors = schema.validate_quest(quest, config.schema)
        errors.extend(_project_drift(quest, config))
        ref_errors, ref_notes = _check_references(quest, quests_dir)
        errors.extend(ref_errors)
        # Notes are a separate channel, not a severity flag on an error: they
        # never count toward the exit code, so anything routed here is
        # something a commit must not be blocked on. Slug drift is one such
        # check; a qualified `blocked_by` reference to a log absent from this
        # device is another -- see `_check_qualified_ref`.
        notes = schema.check_slug_drift(quest) + ref_notes

        total_errors += len(errors)
        total_notes += len(notes)

        shown = errors + (notes if args.notes else [])
        if shown:
            print(f"[!] {path}")
            for error in errors:
                print(f"      error: {error.message}")
            if args.notes:
                for note in notes:
                    print(f"      note: {note.message}")
        if errors or notes:
            lines = [f"- error: {e.message}" for e in errors] + [f"- note: {n.message}" for n in notes]
            report_sections.append(f"## {path}\n\n" + "\n".join(lines) + "\n")

    print(f"[quest validate] {_summary(checked, total_errors, total_notes)}")

    if getattr(args, "report", None):
        _write_report(Path(args.report), checked, total_errors, total_notes, report_sections)

    return 1 if total_errors else 0


def _write_report(report_path: Path, checked: int, errors: int, notes: int, sections: list[str]) -> None:
    """Write findings as a Markdown note, deleting it when the log is clean.

    Derived state, transported by Syncthing rather than git -- `quest
    commit`'s default `tracked:` set deliberately excludes it -- and left
    stale forever if nobody deletes it once the log is fixed.
    """
    if not errors and not notes:
        report_path.unlink(missing_ok=True)
        return
    header = f"# Validation report\n\n{_summary(checked, errors, notes)}\n\n"
    report_path.write_text(header + "\n".join(sections), encoding="utf-8")


def _warn_validation_theater(config: QuestLogConfig) -> None:
    """Flag `required: true` paired with a *static* default.

    A mandatory field that always gets the same value is a field nobody ever
    thinks about -- the check can never fail, so it enforces nothing. It stays
    legal rather than becoming an error, because a *computed* default that
    genuinely varies (`{{ env.USER }}` on `owner`) carries real information,
    and the config cannot tell the author's intent apart from the outside.
    """
    for name, spec in sorted(config.schema.fields.items()):
        if spec.required and spec.has_static_default:
            print(
                f"[quest validate] warning: field '{name}' is required with the static "
                f"default '{spec.default}', so the requirement can never fail -- "
                "validation theater. Use a macro default, or drop `required`.",
                file=sys.stderr,
            )


def _summary(checked: int, errors: int, notes: int) -> str:
    """Report both counts, so a clean-but-noted log does not read as failing.

    The old summary said "N error(s)" and nothing else, so a log with one
    drifted filename and no real problem looked broken.
    """
    if not errors and not notes:
        return f"{checked} quest(s) checked, no errors"
    return f"{checked} quest(s) checked, {errors} error(s), {notes} note(s)"


def _project_drift(quest, config: QuestLogConfig) -> list[schema.ValidationError]:
    if not config.project:
        return []
    quest_project = quest.get("project")
    if quest_project and quest_project != config.project:
        return [
            schema.ValidationError(
                quest.path,
                f"project '{quest_project}' disagrees with this log's declared project "
                f"'{config.project}' (drift)",
            )
        ]
    return []


def _check_references(
    quest, quests_dir: Path
) -> tuple[list[schema.ValidationError], list[schema.ValidationError]]:
    """`blocked_by` ids and body wikilinks must resolve; qualified ids may resolve elsewhere.

    A bare id always means "this log" and is checked here unchanged. A
    `project/QST-xxxxx` id declares its own scope -- see
    `_check_qualified_ref`. Body wikilinks stay local-only: a cross-log
    `[[QST-...]]` cannot resolve across Obsidian vault boundaries, so a
    cross-log body reference is written as prose instead, which
    `_WIKILINK_ID_RE` does not match.
    """
    errors: list[schema.ValidationError] = []
    notes: list[schema.ValidationError] = []
    own_id = quest.get("id")

    for ref in quest.frontmatter.get("blocked_by") or []:
        if "/" in ref:
            error, note = _check_qualified_ref(quest, quests_dir, ref)
            if error:
                errors.append(error)
            if note:
                notes.append(note)
            continue
        if find_by_id(quests_dir, ref) is None:
            errors.append(
                schema.ValidationError(
                    quest.path, f"blocked_by references '{ref}', not found in this log"
                )
            )

    # Code spans/blocks are illustrative, not live links -- e.g. a doc
    # showing `` [[QST-x7k2m]] `` as a syntax example, not a real reference.
    prose = _INLINE_CODE_RE.sub("", _FENCED_CODE_RE.sub("", quest.body))

    seen: set[str] = set()
    for match in _WIKILINK_ID_RE.finditer(prose):
        ref_id = match.group(1)
        if ref_id == own_id or ref_id in seen:
            continue
        seen.add(ref_id)
        if find_by_id(quests_dir, ref_id) is None:
            errors.append(
                schema.ValidationError(
                    quest.path, f"backlink references '{ref_id}', not found in this log"
                )
            )

    return errors, notes


def _check_qualified_ref(
    quest, quests_dir: Path, ref: str
) -> tuple[schema.ValidationError | None, schema.ValidationError | None]:
    """Resolve one `project/QST-xxxxx` reference: (error, note), at most one set.

    Whether the named log is missing because it genuinely doesn't exist or
    because this device simply hasn't synced it is indistinguishable from
    here -- both look like "the sweep found nothing named that" -- so both
    downgrade to a note rather than a hard error. That is the whole point of
    a qualified reference declaring its own scope: the same file must
    validate identically on every device.
    """
    project, _, ref_id = ref.rpartition("/")
    try:
        logs = resolve_by_name_or_path(project, start=quests_dir)
    except QuestLogNotFoundError as exc:
        return None, schema.ValidationError(
            quest.path, f"blocked_by references '{ref}', but {exc}"
        )
    if find_by_id(logs[0], ref_id) is None:
        return (
            schema.ValidationError(
                quest.path, f"blocked_by references '{ref}', not found in log '{project}'"
            ),
            None,
        )
    return None, None
