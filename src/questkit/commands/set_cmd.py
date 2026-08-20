"""`quest set` — update one or more frontmatter fields on a quest."""

from __future__ import annotations

import argparse

from ..config import QuestLogConfig
from ..discovery import resolve_mutation_target
from ..gitutil import auto_commit
from ..quest import Quest
from ..timeutil import today


def run(args: argparse.Namespace) -> int:
    found = resolve_mutation_target(args.id, explicit_in=args.in_dir)
    if found is None:
        print(f"[quest] no quest matching id '{args.id}' found")
        return 1
    quests_dir, path = found

    quest = Quest.load(path)
    changed: list[str] = []
    for assignment in args.assignments:
        if "=" not in assignment:
            print(f"[quest] ignoring malformed assignment '{assignment}' (expected field=value)")
            continue
        key, _, value = assignment.partition("=")
        key = key.strip()
        new_value = _coerce(key, value.strip())
        # Compare the *coerced* value: `tags=a,b` becomes a list, so comparing
        # the raw string would report a change on every re-assertion.
        if _same(quest.frontmatter.get(key), new_value):
            continue
        quest.set(key, new_value)
        changed.append(key)

    if not changed:
        print(f"[quest] {path}: no change")
        return 0

    # Only a real transition stamps `status_changed` -- and only if the caller
    # did not set it explicitly in the same invocation. An agent re-asserting a
    # status it already holds took the `_same` path above and never gets here,
    # which is the whole point: `modified` is laundered by the bump hook on
    # every commit, so a status timestamp that moved on every write would
    # measure nothing.
    if "status" in changed and "status_changed" not in changed:
        quest.set("status_changed", today())

    quest.frontmatter["modified"] = today()
    quest.save()
    print(str(path))

    config = QuestLogConfig.load(quests_dir)
    if config.git == "auto":
        auto_commit(quests_dir, path, f"quest({quests_dir.name}): update {quest.get('id')}")

    return 0


def _same(current, new_value) -> bool:
    """Whether an assignment is a no-op.

    Compared via `str()` on scalars because frontmatter values come back
    typed: `created`/`modified` normalize to real `date` objects on save, so a
    `date(2026, 8, 20) != "2026-08-20"` comparison would call every date
    assignment a change and rewrite the file. Lists compare element-wise for
    the same reason -- `tags` round-trips as a ruamel `CommentedSeq`, which is
    not `==` to a plain list of the same strings in every ruamel version.
    """
    if isinstance(new_value, list):
        if not isinstance(current, list):
            return False
        return [str(v) for v in current] == [str(v) for v in new_value]
    if current is None:
        return False
    return str(current) == str(new_value)


def _coerce(key, value):
    if key == "tags":
        return [v.strip() for v in value.split(",") if v.strip()]
    return value
