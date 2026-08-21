"""The `--where` expression grammar: parsing and matching against one row.

Extracted from `commands/list_cmd.py` so `schema.py`'s readiness engine can
reuse the exact same grammar for `readiness: [{require: {where: ...}}]` --
"one expression language, not two". `list_cmd` still owns sorting (which
needs a `SchemaConfig` for declared-order ranking); this module owns nothing
but parsing and boolean matching, so `schema.py` can import it with no
circular dependency back onto `commands.*`.
"""

from __future__ import annotations

# Checked in this order, and the order is the whole point: the compound
# operators must be tried before their single-character prefixes, or `>=` is
# shredded into `>` plus a value that silently gains a leading `=`.
OPERATORS = (
    ("!=", "ne"),
    (">=", "gte"),
    ("<=", "lte"),
    ("~", "contains"),
    (">", "gt"),
    ("<", "lt"),
    ("=", "eq"),
)


def parse_where(expr: str) -> tuple[str, str, str | None]:
    if expr.endswith(":exists"):
        return expr[: -len(":exists")].strip(), "exists", None
    for token, op in OPERATORS:
        if token in expr:
            field_name, _, value = expr.partition(token)
            return field_name.strip(), op, value.strip()
    raise ValueError(
        f"malformed --where expression '{expr}' (expected field<op>value with op in "
        f"{', '.join(token for token, _ in OPERATORS)}, or field:exists)"
    )


def split_candidates(value: str) -> list[str]:
    """`"a,b"` -> `["a", "b"]` -- the comma-list-is-OR convention shared by
    every --where operator: `field=a,b` and `field~a,b` both mean "a or b"."""
    return [c.strip().lower() for c in value.split(",") if c.strip()]


def matches(row, field_name: str, op: str, value: str | None) -> bool:
    actual = row.get(field_name)
    if op == "exists":
        return not is_blank(actual)
    if op == "contains":
        candidates = split_candidates(value or "")
        if isinstance(actual, list):
            actual_values = [str(v).lower() for v in actual]
            return any(c in actual_values for c in candidates)
        actual_str = str(actual or "").lower()
        return any(c in actual_str for c in candidates)
    if op == "eq":
        wanted = set(split_candidates(value or ""))
        if isinstance(actual, list):
            return bool({str(v).lower() for v in actual} & wanted)
        return str(actual).lower() in wanted
    if op == "ne":
        wanted = set(split_candidates(value or ""))
        if isinstance(actual, list):
            return not ({str(v).lower() for v in actual} & wanted)
        # An absent field genuinely *is* `!= afk`, so this must not be false.
        return str(actual).lower() not in wanted if actual is not None else True
    if op in _COMPARISONS:
        return compare(actual, value or "", op)
    return False


_COMPARISONS = {
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
}


def compare(actual, value: str, op: str) -> bool:
    """Numeric where both sides look numeric, string otherwise.

    Frontmatter is untyped, so a count can arrive as `20` or `"20"` depending
    on who wrote the file -- and the computed fields (`idle`, `blocks`) are
    real ints. ISO dates need no special case at all: they compare correctly
    as plain strings, which is why `--where status_changed<2026-08-05` works
    with no date parsing anywhere.
    """
    if is_blank(actual):
        return False
    left, right = str(actual), value
    if looks_numeric(left) and looks_numeric(right):
        return _COMPARISONS[op](float(left), float(right))
    return _COMPARISONS[op](left.lower(), right.lower())


def looks_numeric(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return True


def is_blank(value) -> bool:
    return value is None or value == "" or value == []
