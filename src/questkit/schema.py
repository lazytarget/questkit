"""Controlled vocabularies and validation rules for quest frontmatter."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from ruamel.yaml import YAML

from . import macros, query
from .utils import slugify

# Vocabularies are **ordered tuples, not sets**, and that is load-bearing.
# `list_cmd` sorts by declaration order, so `--sort priority:asc` has to mean
# critical-first rather than alphabetical -- as a set it returned `critical,
# deferred, high, low, medium`, which would rank a `deferred` quest second in
# the `next` view. Membership checks stay O(n) on n <= 10, which is free.
TYPES = ("feature", "task", "bug", "epic", "chore")
TIERS = ("spark", "brief", "blueprint")

# `done` sits second-to-last on purpose: `terminal_statuses` defaults to the
# tail of this list, so the two agree by construction rather than by discipline.
STATUSES = ("draft", "todo", "in-progress", "parked", "done", "scrapped")
TERMINAL_STATUSES = ("done", "scrapped")

PRIORITIES = ("critical", "high", "medium", "low", "deferred")
EFFORTS = ("xs", "s", "m", "l", "xl")

# Property names Obsidian's own Properties panel adds without asking --
# `cssclasses`/`cssclass`, `permalink`, `publish`, `cover`, `image`. In the
# family log, where nobody can read a terminal, a stray one of these would
# otherwise be a permanent strict-mode validation error. Permitted but
# unmanaged: `quest schema quest` lists them so their status is discoverable.
OBSIDIAN_RESERVED_FIELDS = ("cssclasses", "cssclass", "permalink", "publish", "cover", "image")

# A schema may not declare an enum value or custom field colliding with one of
# these. `--where blocked=true` and `--where status=blocked` would otherwise be
# two different questions one word apart, and a quest could satisfy either
# without the other. Enforced at config load, which is what makes `blocked`
# leaving the status enum permanent rather than a tidy-up someone reverses.
COMPUTED_FIELD_NAMES = ("blocked", "blocks", "idle", "age", "archived")

# Which vocabulary each sortable field draws its order from.
_FIELD_VOCABULARIES = {
    "type": "types",
    "status": "statuses",
    "tier": "tiers",
    "priority": "priorities",
    "effort": "efforts",
}

# The explicit head of the frontmatter order; everything else sorts
# alphabetically after it. **One rule, not three.** A three-group scheme
# (ordered natives -> alphabetical natives -> alphabetical custom) needs
# questkit to know which fields are "native", and that boundary is itself
# schema-defined -- so the same quest would sort differently in two logs and
# `quest mv` would silently reorder frontmatter.
FIELD_ORDER = (
    "id",
    "title",
    "description",
    "project",
    "type",
    "status",
    "priority",
    "tags",
    "created",
    "status_changed",
    "modified",
)

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
    "archived",
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
    "archived": {
        "type": "bool",
        "required": False,
        "doc": (
            "whether this quest should still be in front of you. Orthogonal to `status`: "
            "archiving answers a retention question, scrapping answers what happened to the "
            "work, and a `done` quest in a wound-up project is archived and not scrapped. "
            "Affects listing, never id resolution."
        ),
    },
}

DEFAULT_STATUS = "draft"
DEFAULT_TYPE = "task"
DEFAULT_PRIORITY = "medium"


class SchemaExtendsError(Exception):
    """Raised when a `schema.extends` chain is circular or points at a missing file."""


@dataclass(frozen=True)
class ReadinessRule:
    """One entry in a schema's `readiness:` list.

    `require` is one of three shapes: `{"where": "<expr>"}` (the `--where`
    grammar verbatim -- one expression language, not two), `{"sections":
    [...]}` (any-of a set of body headings), or `{"checklist": "<heading>",
    "min": N}` (count of checked/unchecked items under a heading). `when`, if
    present, is a `--where` expression gating whether the rule applies at all
    -- it is how "AFK implies spec + criteria" becomes configuration instead
    of a hardcoded branch.
    """

    require: dict
    message: str
    when: str | None = None


# The four rules every fresh `pip install questkit` ships with. The inverse
# (minimal core, rigor opted into) was rejected: it would print a checkmark
# for a quest with no spec and no criteria, making the flagship command look
# useless on day one. "A spec and acceptance criteria make work handoff-ready"
# is not an opinion about a domain -- it is what handoff-ready means.
DEFAULT_READINESS = (
    ReadinessRule(require={"where": "description:exists"}, message="no description"),
    ReadinessRule(require={"where": "status!=draft"}, message="still a draft -- not groomed"),
    ReadinessRule(
        require={"sections": ["## Spec", "## Design"]}, message="no spec or design section"
    ),
    ReadinessRule(
        require={"checklist": "## Acceptance Criteria", "min": 1},
        message="no acceptance criteria",
    ),
)


@dataclass(frozen=True)
class View:
    """One entry in a schema's `views:` map -- a prefill over `quest list`.

    Every field a view sets is a **default**, not a lock: `run()` in
    `list_cmd` drops a view's own `where` clause for any field the caller
    already targeted explicitly, and an explicit `--sort`/`--limit` overrides
    the view's outright. `where` holds raw `--where` expression strings (the
    same grammar everywhere else), not pre-parsed tuples, so a view is just
    data until something applies it.
    """

    where: tuple = ()
    sort: str | None = None
    limit: int | None = None


# The four views every fresh `pip install questkit` ships with, exposed as
# bare subcommands (`quest next`, `quest stale`, `quest blocked`) plus the one
# every plain `quest list` uses implicitly (`default`). `views.default` is
# what finally removes list_cmd's own hardcoded status list: a schema that
# overrides `statuses:` declares its own `views.default` in the same file,
# rather than a second config key that could disagree with the first.
DEFAULT_VIEWS = {
    "default": View(where=("status=todo,in-progress",)),
    "next": View(where=("blocked=false",), sort="priority:asc,effort:asc,idle:desc", limit=1),
    "stale": View(where=("idle>14",), sort="idle:desc"),
    "blocked": View(where=("blocked=true",), sort="blocks:desc"),
}


class SchemaConfigError(Exception):
    """Raised when a `schema:` block is internally inconsistent.

    Loud at config load rather than degrading, because every case this covers
    would otherwise produce a *confidently wrong* answer: an `OPEN` column
    silently equal to `total`, a `blocked` field that is always false, or two
    query expressions one word apart meaning different things.
    """


@dataclass(frozen=True)
class FieldSpec:
    """A custom frontmatter field defined in a log's `.questkit.yaml` schema block."""

    name: str
    type: str = "string"
    required: bool = False
    values: tuple = ()  # only meaningful for type: enum; ordered, so it sorts
    default: object = None

    @property
    def has_static_default(self) -> bool:
        """A default with no macro in it -- the same value for every quest.

        Paired with `required: true` this is validation theater: a mandatory
        field nobody ever thinks about. It stays legal, because a *computed*
        default that genuinely varies carries real information.
        """
        return isinstance(self.default, str) and not macros.has_macro(self.default)


@dataclass(frozen=True)
class SchemaConfig:
    """The active, merged schema for one quest log: vocabularies plus custom fields."""

    types: tuple = TYPES
    statuses: tuple = STATUSES
    tiers: tuple = TIERS
    priorities: tuple = PRIORITIES
    efforts: tuple = EFFORTS
    terminal_statuses: tuple = TERMINAL_STATUSES
    field_order: tuple = FIELD_ORDER
    strict: bool = True
    readiness: tuple = DEFAULT_READINESS
    views: dict = field(default_factory=lambda: dict(DEFAULT_VIEWS))
    fields: dict = field(default_factory=dict)  # name -> FieldSpec, custom fields only

    @property
    def declared_field_names(self) -> frozenset:
        """Every field name the CLI write path considers "real" under strict.

        Core fields plus this log's declared custom fields. Does **not**
        include the Obsidian allowlist -- that allowlist exists for files
        Obsidian wrote, not for the CLI to hand out as if they were ordinary
        fields to `--set`.
        """
        return frozenset(CORE_FIELDS) | frozenset(self.fields)

    @classmethod
    def default(cls) -> SchemaConfig:
        """The schema in effect when a log has no `schema:` block at all."""
        return cls()

    def rank_of(self, field_name: str, value) -> int | None:
        """Where `value` sits in its field's declared order, or None if unranked.

        `None` means "this field has no vocabulary" (a title, a free-text
        custom field), so the caller falls back to a string sort. An
        out-of-vocabulary value on a *ranked* field sorts last rather than
        first -- a typo must not silently outrank `critical`.
        """
        vocabulary = _FIELD_VOCABULARIES.get(field_name)
        if vocabulary is None:
            spec = self.fields.get(field_name)
            if spec is None or not spec.values:
                return None
            values = spec.values
        else:
            values = getattr(self, vocabulary)
        try:
            return values.index(str(value))
        except ValueError:
            return len(values)

    @classmethod
    def load(cls, quests_dir: Path, schema_block: dict | None) -> SchemaConfig:
        merged = _resolve_schema_extends(quests_dir, dict(schema_block or {}))
        fields = {
            name: _field_spec(name, spec or {}) for name, spec in (merged.get("fields") or {}).items()
        }
        vocabularies = {
            "types": _as_tuple(merged, "types", TYPES),
            "statuses": _as_tuple(merged, "statuses", STATUSES),
            "tiers": _as_tuple(merged, "tiers", TIERS),
            "priorities": _as_tuple(merged, "priorities", PRIORITIES),
            "efforts": _as_tuple(merged, "efforts", EFFORTS),
        }
        _reject_computed_field_collisions(vocabularies, fields)
        return cls(
            **vocabularies,
            terminal_statuses=_resolve_terminal_statuses(merged, vocabularies["statuses"]),
            field_order=_as_tuple(merged, "field_order", FIELD_ORDER),
            strict=bool(merged.get("strict", True)),
            readiness=_resolve_readiness(merged),
            views=_resolve_views(merged),
            fields=fields,
        )

    def resolved_defaults(self, log_defaults: dict) -> dict:
        """Every field default in effect, by precedence.

        `--flag` > `fields.<n>.default` > `defaults.<n>` > built-in. The
        top-level `defaults:` key is sugar writing into the same map as
        `schema.fields.<n>.default`, which is canonical -- two places to say
        the same thing is how they end up disagreeing.
        """
        resolved = dict(log_defaults)
        for name, spec in self.fields.items():
            if spec.default is not None:
                resolved[name] = spec.default
        return resolved

    def order_key(self, field_name: str) -> tuple:
        """Sort key placing `field_order` fields first, then everything alphabetically."""
        try:
            return (0, self.field_order.index(field_name), "")
        except ValueError:
            return (1, 0, field_name)


def _field_spec(name: str, spec: dict) -> FieldSpec:
    field_type = spec.get("type", "string")
    values = tuple(str(v) for v in (spec.get("values") or ()))
    if field_type == "enum" and not values:
        raise SchemaConfigError(
            f"field '{name}' declares type: enum but no values:. An enum with no "
            "vocabulary validates nothing."
        )
    if values and field_type != "enum":
        raise SchemaConfigError(
            f"field '{name}' declares values: but type: {field_type} -- values: is only "
            "meaningful for type: enum"
        )
    return FieldSpec(
        name=name,
        type=field_type,
        required=bool(spec.get("required", False)),
        values=values,
        default=spec.get("default"),
    )


def _as_tuple(merged: dict, key: str, fallback: tuple) -> tuple:
    if key not in merged:
        return fallback
    return tuple(str(value) for value in merged[key])


def _reject_computed_field_collisions(vocabularies: dict, fields: dict) -> None:
    reserved = set(COMPUTED_FIELD_NAMES)
    for name, values in vocabularies.items():
        for value in values:
            if value in reserved:
                raise SchemaConfigError(
                    f"'{name}' declares '{value}', which collides with the computed field "
                    f"'{value}'. Computed field names are reserved "
                    f"({', '.join(COMPUTED_FIELD_NAMES)}): a status value and a computed "
                    "field cannot share a name, or --where would have two meanings for it."
                )
    for name in fields:
        if name in reserved:
            raise SchemaConfigError(
                f"custom field '{name}' collides with the computed field '{name}'. "
                f"Computed field names are reserved ({', '.join(COMPUTED_FIELD_NAMES)})."
            )


def _resolve_readiness(merged: dict) -> tuple:
    """`readiness:` fully replaces the default list, like every other sibling key.

    A merge-by-key scheme would need a name-based identity for rules that
    have none; full replacement is what the rest of this file already does
    for `statuses`/`fields`/etc., so a `household` schema overriding the list
    down to one rule is one YAML list, not a diff against four unwritten ones.
    """
    if "readiness" not in merged:
        return DEFAULT_READINESS
    rules = []
    for entry in merged["readiness"] or []:
        require = entry.get("require")
        message = entry.get("message")
        if not require or not message:
            raise SchemaConfigError(
                f"readiness rule {entry!r} needs both 'require' and 'message'"
            )
        rules.append(ReadinessRule(require=require, message=message, when=entry.get("when")))
    return tuple(rules)


def _resolve_views(merged: dict) -> dict:
    """`views:` fully replaces the default map, like `readiness:` and every
    other sibling key -- a schema overriding `statuses:` declares its own
    `views.default` in the same file rather than leaving three built-ins
    silently stale."""
    if "views" not in merged:
        return dict(DEFAULT_VIEWS)
    views = {}
    for name, spec in (merged["views"] or {}).items():
        spec = spec or {}
        views[name] = View(
            where=tuple(str(w) for w in (spec.get("where") or ())),
            sort=spec.get("sort"),
            limit=spec.get("limit"),
        )
    return views


def evaluate_readiness(quest, schema_config: SchemaConfig) -> list[str]:
    """Every readiness rule this quest fails, in declared order.

    Advisory by design: this is what makes it safe for *configuration* to
    define these rules at all. `quest validate` never calls this -- it
    answers "is this file well-formed and are its references real", a
    different question from "is this good enough to hand to someone".
    """
    failures = []
    for rule in schema_config.readiness:
        if rule.when is not None and not _readiness_where(quest, rule.when):
            continue
        if not _readiness_satisfied(quest, rule.require):
            failures.append(rule.message)
    return failures


def _readiness_where(quest, expr: str) -> bool:
    field_name, op, value = query.parse_where(expr)
    return query.matches(quest.frontmatter, field_name, op, value)


def _readiness_satisfied(quest, require: dict) -> bool:
    if "where" in require:
        return _readiness_where(quest, require["where"])
    if "sections" in require:
        body_lower = quest.body.lower()
        return any(section.lower() in body_lower for section in require["sections"])
    if "checklist" in require:
        heading = require["checklist"]
        minimum = require.get("min", 1)
        return _count_checklist_items(quest.body, heading) >= minimum
    raise SchemaConfigError(f"readiness rule has an unrecognized require: {require}")


def _count_checklist_items(body: str, heading: str) -> int:
    """Checked/unchecked list items under one heading, stopping at the next `## `."""
    heading_lower = heading.strip().lower()
    counting = False
    count = 0
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.lower() == heading_lower:
            counting = True
            continue
        if not counting:
            continue
        if stripped.startswith("## "):
            break
        if stripped[:5].lower() in ("- [ ]", "- [x]"):
            count += 1
    return count


def _resolve_terminal_statuses(merged: dict, statuses: tuple) -> tuple:
    """Which statuses mean "finished", for the four consumers that need to know.

    `quest logs`' OPEN column, the `blocked` computation, `stale`'s exclusion
    set, and what `quest done` writes. Ordered, because `quest done` writes the
    first entry.

    Defaults to the built-in pair intersected with whatever the log declared,
    so a log that renamed only *part* of the vocabulary needs no declaration.
    A log where no default survives and nothing is declared is a hard error:
    degrading would give `quest logs` an OPEN column silently equal to total.
    """
    declared = merged.get("terminal_statuses")
    if declared is not None:
        resolved = tuple(str(value) for value in declared)
        unknown = [value for value in resolved if value not in statuses]
        if unknown:
            raise SchemaConfigError(
                f"terminal_statuses declares {unknown}, which are not in statuses "
                f"({', '.join(statuses)})"
            )
        return resolved

    surviving = tuple(value for value in TERMINAL_STATUSES if value in statuses)
    if not surviving:
        raise SchemaConfigError(
            f"statuses ({', '.join(statuses)}) overrides the default vocabulary and keeps "
            f"none of {list(TERMINAL_STATUSES)}, so questkit cannot tell which statuses mean "
            "'finished'. Declare terminal_statuses explicitly."
        )
    return surviving


SCHEMA_PATH_ENV = "QST_SCHEMA_PATH"

# Where a *named* schema (`extends: development`) is looked up, relative to an
# ancestor of the log. Deliberately under `99-system/`, not the Realm root:
# `99-system/syncthing.yaml` has no folder for `.`, so the root is a local
# composition of independently-synced folders rather than a synced entity. A
# schema file there would resolve on one machine and fail silently on every
# other -- the worst possible failure shape. Generalizes: any questkit artifact
# that must reach every device belongs under `99-system/`.
REALM_SCHEMA_DIR = ("99-system", "questkit", "schemas")


def _resolve_schema_extends(
    quests_dir: Path, schema_block: dict, _visited: frozenset = frozenset()
) -> dict:
    """Recursively resolve `extends`; sibling keys fully replace the parent's.

    The file an `extends` points at is itself treated as a schema document --
    it may declare its own `extends`, chaining further. No deep-merging of
    lists: a child's `statuses` entirely replaces the parent's rather than
    unioning with it.

    An `extends` value is either a **path** (relative to `quests_dir`) or a
    **name**. See `_looks_like_a_path`.
    """
    extends = schema_block.get("extends")
    merged: dict = {}
    if extends:
        parent_path = _resolve_extends_target(quests_dir, str(extends))
        if parent_path in _visited:
            raise SchemaExtendsError(f"circular schema 'extends' chain at {parent_path}")
        parent_data = _yaml.load(parent_path.read_text(encoding="utf-8")) or {}
        merged = _resolve_schema_extends(parent_path.parent, parent_data, _visited | {parent_path})
    for key, value in schema_block.items():
        if key == "extends":
            continue
        merged[key] = value
    return merged


def _looks_like_a_path(extends: str) -> bool:
    """Path vs. name, by the same shape rule `--in` uses for logs.

    Anything carrying a separator or a `.yaml`/`.yml` suffix is a path;
    anything else is a name resolved against the search path. One rule, no new
    syntax, and fully backward compatible with the path-relative `extends:`
    that shipped in v2.
    """
    return "/" in extends or "\\" in extends or extends.endswith((".yaml", ".yml"))


def _schema_search_path(quests_dir: Path) -> list[Path]:
    """Where named schemas are looked for, most specific first.

    `QST_SCHEMA_PATH` wins so a standalone (non-Realm) user, or a test, can
    point questkit somewhere else entirely without inventing a config key that
    every log would then have to repeat.
    """
    candidates: list[Path] = []
    env_value = os.environ.get(SCHEMA_PATH_ENV)
    if env_value:
        candidates.extend(
            Path(part).expanduser().resolve() for part in env_value.split(os.pathsep) if part
        )
    current = quests_dir.resolve()
    while True:
        candidates.append(current.joinpath(*REALM_SCHEMA_DIR))
        if current.parent == current:
            break
        current = current.parent
    return candidates


def _resolve_extends_target(quests_dir: Path, extends: str) -> Path:
    if _looks_like_a_path(extends):
        parent_path = (quests_dir / extends).expanduser().resolve()
        if not parent_path.is_file():
            raise SchemaExtendsError(f"schema extends '{extends}' -> {parent_path} not found")
        return parent_path

    searched: list[Path] = []
    for directory in _schema_search_path(quests_dir):
        candidate = directory / f"{extends}.yaml"
        searched.append(candidate)
        if candidate.is_file():
            return candidate
    raise SchemaExtendsError(
        f"schema extends '{extends}': no such named schema. Searched "
        f"{', '.join(str(p) for p in searched[:4])}"
        + (f" (and {len(searched) - 4} more)" if len(searched) > 4 else "")
        + f". Set {SCHEMA_PATH_ENV}, or use a path ending in .yaml for a path-relative extend."
    )


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
        if spec.type == "enum":
            errors.extend(_check_enum(quest.path, fm, field_name, spec.values))

    errors.extend(_check_undeclared_fields(quest, schema_config))
    errors.extend(_check_identity(quest))

    return errors


def _check_undeclared_fields(quest, schema_config: SchemaConfig) -> list[ValidationError]:
    """Under `strict: true`, a field this schema does not know about is an error.

    Extended from the original CLI-write-path-only scope: `agentic` leaving
    core (and `milestone` joining `development`) only means something if a
    stray field is ever actually caught, and `quest validate` under
    `strict: true` is that check. Under `strict: false` this reports nothing
    -- the write-path warning (`quest new --set`) is where that case is
    surfaced instead.
    """
    if not schema_config.strict:
        return []
    allowed = schema_config.declared_field_names | frozenset(OBSIDIAN_RESERVED_FIELDS)
    return [
        ValidationError(quest.path, f"undeclared field '{key}' (strict schema)")
        for key in quest.frontmatter
        if key not in allowed
    ]


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
    # `list(allowed)`, not `sorted(allowed)`: the declared order is the
    # meaningful one now, and sorting it back to alphabetical in the error
    # message would tell the reader the wrong thing about their own schema.
    value = fm.get(name)
    if value is None or value in allowed:
        return []
    return [ValidationError(path, f"{name} '{value}' not in {list(allowed)}")]


