"""The Obsidian capture template: a packaged default, and a schema-generated one.

`.md`, not `.tmpl` -- the file must be editable in Obsidian on a phone, where
a `.tmpl` renders as nothing. A `.md` with `{{ }}` placeholders in real
frontmatter renders as what it produces, which is the best documentation it
could have. Replaces the old hardcoded `template.py`: `render_body()` now
reads the packaged file's body section instead of a Python string literal.
"""

from __future__ import annotations

from pathlib import Path

from . import macros, schema
from .config import QuestLogConfig

PACKAGED_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "_template.md"


def render_body(created: str, template_path: Path | None = None) -> str:
    """The body section of a template file, with `{{ today }}` filled in.

    `template_path` lets a log's own `_template.md` (see `generate_template`)
    override the packaged default -- `quest new` prefers it when present.
    """
    path = template_path if template_path is not None and template_path.is_file() else PACKAGED_TEMPLATE_PATH
    _, body = _split_frontmatter(path.read_text(encoding="utf-8"))
    context: dict[str, object] = {"today": created}
    return "".join(
        macros.expand(line, context) if macros.has_macro(line) else line
        for line in body.splitlines(keepends=True)
    )


def _split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---"):
        return "", text
    _, _, rest = text.partition("---")
    front, sep, body = rest.partition("---")
    if not sep:
        return "", text
    return front, body.lstrip("\n")


def generate_template(config: QuestLogConfig) -> str:
    """A real Obsidian template, generated from this log's merged schema.

    Regenerated on every `quest init --template` call -- a build artifact
    like `quests.base`, not a parallel hand-maintained implementation that
    would drift the moment the schema changes.
    """
    schema_config = config.schema
    lines = ["---"]
    lines.append('id: "{{ id }}"')
    lines.append('title: "{{ title }}"')
    lines.append('description: ""')
    if config.project:
        lines.append(f"project: {config.project}")
    lines.append(f"type: {config.defaults.get('type', schema.DEFAULT_TYPE)}")
    lines.append(f"status: {config.defaults.get('status', schema.DEFAULT_STATUS)}")
    lines.append(f"priority: {config.defaults.get('priority', schema.DEFAULT_PRIORITY)}")
    lines.append("tags: []")
    lines.append('created: "{{ today }}"')
    lines.append('modified: "{{ today }}"')
    for name, spec in sorted(schema_config.fields.items()):
        lines.append(f"{name}: {_field_placeholder(spec)}")
    lines.append("blocked_by: []")
    lines.append("aliases:")
    lines.append('  - "{{ id }}"')
    lines.append("---")
    lines.append("")
    lines.append("## Description")
    lines.append("")
    lines.append("## Acceptance Criteria")
    lines.append("")
    lines.append("- [ ] ...")
    lines.append("")
    lines.append("## Log")
    lines.append("")
    lines.append("- {{ today }}: captured")
    lines.append("")
    return "\n".join(lines)


def _field_placeholder(spec: schema.FieldSpec) -> str:
    if spec.default is not None and not (isinstance(spec.default, str) and macros.has_macro(spec.default)):
        return str(spec.default)
    if spec.values:
        return spec.values[0]
    return '""'
