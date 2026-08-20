"""`quest deps <id>` — walk the dependency graph. A real graph walk, not a
filter, so unlike `next`/`stale`/`blocked` it stays its own command rather
than a `list` prefill.

`blocked_by` is many-to-many, so this is a **DAG, not a tree**: rendering it
strictly would either duplicate nodes or silently drop edges. A node
encountered a second time is marked and not re-expanded, rather than either
of those.
"""

from __future__ import annotations

import argparse

from .. import schema
from ..config import ConfigVersionError, QuestLogConfig
from ..discovery import resolve_log_set
from ..quest import Quest


def run(args: argparse.Namespace) -> int:
    logs = resolve_log_set(in_dirs=args.in_dirs, all_logs=not args.in_dirs, root=args.root)

    nodes: dict[str, dict] = {}
    for quests_dir in logs:
        try:
            config = QuestLogConfig.load(quests_dir)
        except (ConfigVersionError, schema.SchemaExtendsError, schema.SchemaConfigError):
            continue
        project = config.project or quests_dir.name
        for path in sorted(quests_dir.glob(config.pattern)):
            fm = Quest.load(path).frontmatter
            quest_id = fm.get("id")
            nodes[quest_id] = {
                "title": fm.get("title"),
                "status": fm.get("status"),
                "project": project,
                "blocked_by": list(fm.get("blocked_by") or []),
            }

    if args.id not in nodes:
        print(f"[quest deps] no quest matching id '{args.id}' found")
        return 1

    forward: dict[str, list[str]] = {node_id: [] for node_id in nodes}
    for node_id, node in nodes.items():
        for ref in node["blocked_by"]:
            target_id = ref.rsplit("/", 1)[-1]
            if target_id in nodes:
                forward[node_id].append(target_id)

    if args.blocks:
        edges: dict[str, list[str]] = {node_id: [] for node_id in nodes}
        for node_id, targets in forward.items():
            for target_id in targets:
                edges[target_id].append(node_id)
    else:
        edges = forward

    print("\n".join(_render(args.id, nodes, edges, set(), 0)))
    return 0


def _label(node_id: str, node: dict) -> str:
    return f"{node_id} [{node['project']}] {node['title']} ({node['status']})"


def _render(node_id: str, nodes: dict, edges: dict, visited: set, depth: int) -> list[str]:
    indent = "  " * depth
    label = _label(node_id, nodes[node_id])
    if node_id in visited:
        return [f"{indent}{label} (see above)"]
    visited.add(node_id)
    lines = [f"{indent}{label}"]
    for target_id in sorted(edges.get(node_id, [])):
        lines.extend(_render(target_id, nodes, edges, visited, depth + 1))
    return lines
