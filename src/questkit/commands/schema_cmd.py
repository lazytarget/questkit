"""`quest schema` — introspect a log's active schema, so agents don't have to
guess or hallucinate valid enum values or custom-field shapes."""

from __future__ import annotations

import argparse
import json

from .. import schema
from ..config import QuestLogConfig
from ..discovery import resolve_log

# Singular CLI spelling (`quest schema quest status`) -> the plural SchemaConfig
# attribute it reads from.
_ARRAY_ALIASES = {
    "type": "types",
    "status": "statuses",
    "tier": "tiers",
    "priority": "priorities",
    "effort": "efforts",
}


def run(args: argparse.Namespace) -> int:
    quests_dir = resolve_log(explicit=args.in_dir)
    schema_config = QuestLogConfig.load(quests_dir).schema

    # `list(...)`, not `sorted(...)`: declaration order *is* the sort order
    # now, so an alphabetised listing would tell an agent reading the schema
    # cold that `deferred` outranks `high`.
    full = {
        "types": list(schema_config.types),
        "statuses": list(schema_config.statuses),
        "tiers": list(schema_config.tiers),
        "priorities": list(schema_config.priorities),
        "efforts": list(schema_config.efforts),
        "terminal_statuses": list(schema_config.terminal_statuses),
        "fields": {name: _spec_dict(spec) for name, spec in sorted(schema_config.fields.items())},
        "field_order": list(schema_config.field_order),
        # Core fields are part of the schema an agent has to satisfy, so they
        # belong in the introspection output alongside the enums -- listing
        # only the *custom* fields implied the rest were guessable.
        "core_fields": {
            name: dict(spec) for name, spec in sorted(schema.CORE_FIELD_SPECS.items())
        },
    }

    data: object
    if args.field is None:
        data = full
    else:
        array_key = _ARRAY_ALIASES.get(args.field)
        if array_key is not None:
            data = full[array_key]
        elif args.field in schema_config.fields:
            data = _spec_dict(schema_config.fields[args.field])
        elif args.field in schema.CORE_FIELD_SPECS:
            data = dict(schema.CORE_FIELD_SPECS[args.field])
        else:
            print(f"[quest schema] unknown schema field '{args.field}'")
            return 1

    print(_render_table(data) if args.format == "table" else json.dumps(data, indent=2))
    return 0


def _spec_dict(spec) -> dict:
    """A field spec as plain data, omitting the keys that do not apply.

    `values` only means something for `type: enum`, and a `default: null` on
    every field would be noise in the one output an agent reads to learn what
    it is allowed to write.
    """
    out: dict = {"type": spec.type, "required": spec.required}
    if spec.values:
        out["values"] = list(spec.values)
    if spec.default is not None:
        out["default"] = spec.default
    return out


def _render_table(data) -> str:
    if isinstance(data, list):
        return ", ".join(str(v) for v in data)
    if isinstance(data, dict) and all(isinstance(v, dict) for v in data.values()) and data:
        # a field-spec map: {name: {type, required}} (either the top-level "fields"
        # entry within the full schema, or a single custom field's own spec)
        lines = []
        for key, value in data.items():
            spec_str = ", ".join(f"{k}={v}" for k, v in value.items())
            lines.append(f"{key}: {spec_str}")
        return "\n".join(lines)
    if isinstance(data, dict):
        lines = []
        for key, value in data.items():
            if isinstance(value, list):
                lines.append(f"{key}: {', '.join(str(v) for v in value)}")
            elif isinstance(value, dict):
                lines.append(f"{key}:")
                for sub_key, sub_value in value.items():
                    lines.append(f"  {sub_key}: {sub_value}")
            else:
                lines.append(f"{key}: {value}")
        return "\n".join(lines)
    return str(data)
