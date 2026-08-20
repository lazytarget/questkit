"""Controlled vocabularies and validation rules for quest frontmatter."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ruamel.yaml import YAML

from .utils import slugify

TYPES = frozenset({"feature", "task", "bug", "epic", "milestone", "chore"})
TIERS = frozenset({"spark", "brief", "blueprint"})
STATUSES = frozenset(
    {"draft", "todo", "in-progress", "blocked", "parked", "completed", "scrapped"}
)
PRIORITIES = frozenset({"critical", "high", "medium", "low", "deferred"})
EFFORTS = frozenset({"xs", "s", "m", "l", "xl"})
AGENTIC_MODES = frozenset({"afk", "hitl"})

_yaml = YAML()

# Checked for presence only; enum membership is checked separately below.
_SCALAR_REQUIRED_FIELDS = ("id", "title", "created", "modified", "type", "status", "priority")

# Every frontmatter field questkit itself understands, required or not. Distinct
# from _SCALAR_REQUIRED_FIELDS, which is only the presence check: `due` and
# `owner` are core fields that happen to be optional. Consumers need the full
# vocabulary to tell a core field from a custom one or a typo -- `quest migrate`
# uses it to tell `--backfill x=created` (a field reference) from
# `--backfill x=peter` (a literal). QST-j68u5's `field_order` builds on this.
CORE_FIELDS = (
    "id",
    "title",
    "description",
    "project",
    "type",
    "tier",
    "status",
    "priority",
    "effort",
    "owner",
    "tags",
    "created",
    "status_changed",
    "modified",
    "due",
    "blocked_by",
    "aliases",
    "agentic",
)

# What each core field is, for `quest schema quest <field>`. An agent reading
# the schema cold needs to know that `status_changed` is not just another date:
# it is the one that survives the bump hook. QST-j68u5 extends this to every
# core field as part of `field_order`.
CORE_FIELD_SPECS = {
    "created": {"type": "date", "required": True, "doc": "the day the quest was captured"},
    "status_changed": {
        "type": "date",
        "required": False,
        "doc": (
            "the day `status` last changed. Written only on a real transition, so it "
            "measures staleness where `modified` cannot -- `modified` is bumped by the "
            "quest-bump-modified hook on every commit. Absent means never changed: "
            "consumers fall back to `created`."
        ),
    },
    "modified": {
        "type": "date",
        "required": True,
        "doc": "the day the file last changed, including formatting-only commits",
    },
    "due": {"type": "date", "required": False, "doc": "an external deadline, if any"},
}

DEFAULT_STATUS = "draft"
DEFAULT_TYPE = "task"
DEFAULT_PRIORITY = "medium"


class SchemaExtendsError(Exception):
    """Raised when a `schema.extends` chain is circular or points at a missing file."""


@dataclass(frozen=True)
class FieldSpec:
    """A custom frontmatter field defined in a log's `.questkit.yaml` schema block."""

    name: str
    type: str = "string"
    required: bool = False


@dataclass(frozen=True)
class SchemaConfig:
    """The active, merged schema for one quest log: vocabularies plus custom fields."""

    types: frozenset = TYPES
    statuses: frozenset = STATUSES
    tiers: frozenset = TIERS
    priorities: frozenset = PRIORITIES
    efforts: frozenset = EFFORTS
    fields: dict = field(default_factory=dict)  # name -> FieldSpec, custom fields only

    @classmethod
    def default(cls) -> SchemaConfig:
        """The schema in effect when a log has no `schema:` block at all."""
        return cls()

    @classmethod
    def load(cls, quests_dir: Path, schema_block: dict | None) -> SchemaConfig:
        merged = _resolve_schema_extends(quests_dir, dict(schema_block or {}))
        fields = {
            name: FieldSpec(
                name=name,
                type=(spec or {}).get("type", "string"),
                required=bool((spec or {}).get("required", False)),
            )
            for name, spec in (merged.get("fields") or {}).items()
        }
        return cls(
            types=frozenset(merged["types"]) if "types" in merged else TYPES,
            statuses=frozenset(merged["statuses"]) if "statuses" in merged else STATUSES,
            tiers=frozenset(merged["tiers"]) if "tiers" in merged else TIERS,
            priorities=frozenset(merged["priorities"]) if "priorities" in merged else PRIORITIES,
            efforts=frozenset(merged["efforts"]) if "efforts" in merged else EFFORTS,
            fields=fields,
        )


def _resolve_schema_extends(
    quests_dir: Path, schema_block: dict, _visited: frozenset = frozenset()
) -> dict:
    """Recursively resolve `extends`; sibling keys fully replace the parent's.

    The file an `extends` points at (resolved relative to `quests_dir`) is
    itself treated as a schema document -- it may declare its own `extends`,
    chaining further. No deep-merging of lists: a child's `statuses` entirely
    replaces the parent's, it doesn't union with it.
    """
    extends = schema_block.get("extends")
    merged: dict = {}
    if extends:
        parent_path = (quests_dir / extends).expanduser().resolve()
        if parent_path in _visited:
            raise SchemaExtendsError(f"circular schema 'extends' chain at {parent_path}")
        if not parent_path.is_file():
            raise SchemaExtendsError(f"schema extends '{extends}' -> {parent_path} not found")
        parent_data = _yaml.load(parent_path.read_text(encoding="utf-8")) or {}
        merged = _resolve_schema_extends(parent_path.parent, parent_data, _visited | {parent_path})
    for key, value in schema_block.items():
        if key == "extends":
            continue
        merged[key] = value
    return merged


class ValidationError:
    """A single problem found while validating a quest file."""

    def __init__(self, path, message: str) -> None:
        self.path = path
        self.message = message

    def __repr__(self) -> str:
        return f"ValidationError({self.path!r}, {self.message!r})"

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


def validate_quest(quest, schema_config: SchemaConfig | None = None) -> list[ValidationError]:
    """Validate a Quest's frontmatter and body against the questkit schema.

    `schema_config` defaults to `SchemaConfig.default()` (today's hardcoded
    vocabularies, no custom fields) so existing callers that validate against
    the built-in rules keep working unchanged.
    """
    schema_config = schema_config or SchemaConfig.default()
    errors: list[ValidationError] = []
    fm = quest.frontmatter

    for name in _SCALAR_REQUIRED_FIELDS:
        if _blank(fm.get(name)):
            errors.append(ValidationError(quest.path, f"missing required field '{name}'"))

    if fm.get("tags") is None:
        errors.append(ValidationError(quest.path, "missing required field 'tags'"))

    if fm.get("status") != "draft" and _blank(fm.get("description")):
        errors.append(ValidationError(quest.path, "missing required field 'description'"))

    errors.extend(_check_enum(quest.path, fm, "type", schema_config.types))
    errors.extend(_check_enum(quest.path, fm, "tier", schema_config.tiers))
    errors.extend(_check_enum(quest.path, fm, "status", schema_config.statuses))
    errors.extend(_check_enum(quest.path, fm, "priority", schema_config.priorities))
    errors.extend(_check_enum(quest.path, fm, "effort", schema_config.efforts))

    for field_name, spec in schema_config.fields.items():
        if spec.required and _blank(fm.get(field_name)):
            errors.append(
                ValidationError(quest.path, f"missing required custom field '{field_name}'")
            )

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
