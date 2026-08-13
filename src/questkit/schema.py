"""Controlled vocabularies and validation rules for quest frontmatter."""

from __future__ import annotations

from .utils import slugify

TYPES = frozenset({"feature", "task", "bug", "epic", "milestone", "chore"})
TIERS = frozenset({"spark", "brief", "blueprint"})
STATUSES = frozenset(
    {"draft", "todo", "in-progress", "blocked", "parked", "completed", "scrapped"}
)
PRIORITIES = frozenset({"critical", "high", "medium", "low", "deferred"})
EFFORTS = frozenset({"xs", "s", "m", "l", "xl"})
AGENTIC_MODES = frozenset({"afk", "hitl"})

# Checked for presence only; enum membership is checked separately below.
_SCALAR_REQUIRED_FIELDS = ("id", "title", "created", "modified", "type", "status", "priority")

DEFAULT_STATUS = "draft"
DEFAULT_TYPE = "task"
DEFAULT_PRIORITY = "medium"


class ValidationError:
    """A single problem found while validating a quest file."""

    def __init__(self, path, message: str) -> None:
        self.path = path
        self.message = message

    def __repr__(self) -> str:
        return f"ValidationError({self.path!r}, {self.message!r})"

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


def validate_quest(quest) -> list[ValidationError]:
    """Validate a Quest's frontmatter and body against the questkit schema."""
    errors: list[ValidationError] = []
    fm = quest.frontmatter

    for name in _SCALAR_REQUIRED_FIELDS:
        if _blank(fm.get(name)):
            errors.append(ValidationError(quest.path, f"missing required field '{name}'"))

    if fm.get("tags") is None:
        errors.append(ValidationError(quest.path, "missing required field 'tags'"))

    if fm.get("status") != "draft" and _blank(fm.get("description")):
        errors.append(ValidationError(quest.path, "missing required field 'description'"))

    errors.extend(_check_enum(quest.path, fm, "type", TYPES))
    errors.extend(_check_enum(quest.path, fm, "tier", TIERS))
    errors.extend(_check_enum(quest.path, fm, "status", STATUSES))
    errors.extend(_check_enum(quest.path, fm, "priority", PRIORITIES))
    errors.extend(_check_enum(quest.path, fm, "effort", EFFORTS))

    agentic = fm.get("agentic")
    if agentic is not None:
        if agentic not in AGENTIC_MODES:
            errors.append(
                ValidationError(quest.path, f"agentic '{agentic}' not in {sorted(AGENTIC_MODES)}")
            )
        elif agentic == "afk":
            errors.extend(_check_afk_readiness(quest))

    errors.extend(_check_identity(quest))

    return errors


def _check_identity(quest) -> list[ValidationError]:
    """Cross-check filename id vs frontmatter id, and aliases vs frontmatter id.

    Blocking: both are cheap to keep correct (quest new always gets them
    right) and a mismatch usually means something's actually wrong -- a
    careless rename, a hand-edit that dropped the self-alias. Unlike slug
    drift (see check_slug_drift), there's no legitimate reason for these to
    disagree, so this runs as part of the hard rules used by both `quest
    validate` and the pre-commit hook.
    """
    errors: list[ValidationError] = []
    file_id = quest.path.stem.partition("--")[0]

    fm_id = quest.frontmatter.get("id")
    if fm_id and fm_id != file_id:
        errors.append(
            ValidationError(
                quest.path, f"filename id '{file_id}' disagrees with frontmatter id '{fm_id}'"
            )
        )

    aliases = quest.frontmatter.get("aliases") or []
    if fm_id and fm_id not in aliases:
        errors.append(
            ValidationError(quest.path, f"aliases does not include this quest's own id '{fm_id}'")
        )

    return errors


def check_slug_drift(quest) -> list[ValidationError]:
    """Compare the filename's slug against a freshly-slugified title.

    Informational, not part of validate_quest()'s hard rules, and
    deliberately excluded from the pre-commit hook: the filename is
    immutable once created (so links never break), so drift here is
    *expected* whenever a title is edited after creation, or when a
    migration chose a different slug than mechanical slugify() would --
    it's not something a commit should be blocked on.
    """
    title = quest.frontmatter.get("title")
    file_slug = quest.path.stem.partition("--")[2]
    if not title or not file_slug:
        return []

    expected_slug = slugify(title)
    if expected_slug == file_slug:
        return []
    return [
        ValidationError(
            quest.path,
            f"filename slug '{file_slug}' disagrees with the title-derived slug "
            f"'{expected_slug}' (title may have changed since creation)",
        )
    ]


def _blank(value) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _check_enum(path, fm, name, allowed) -> list[ValidationError]:
    value = fm.get(name)
    if value is None or value in allowed:
        return []
    return [ValidationError(path, f"{name} '{value}' not in {sorted(allowed)}")]


def _check_afk_readiness(quest) -> list[ValidationError]:
    """AFK quests must carry enough substance to hand off without a live human."""
    errors: list[ValidationError] = []
    body_lower = quest.body.lower()

    has_acceptance = "## acceptance criteria" in body_lower and (
        "- [ ]" in quest.body or "- [x]" in body_lower
    )
    has_spec = "## spec" in body_lower or "## design" in body_lower

    if not has_acceptance:
        errors.append(
            ValidationError(
                quest.path,
                "agentic: afk requires a '## Acceptance Criteria' section with checklist items",
            )
        )
    if not has_spec:
        errors.append(
            ValidationError(
                quest.path,
                "agentic: afk requires a '## Spec' or '## Design' section",
            )
        )
    return errors
