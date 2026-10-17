"""Tests for `quest completion <shell>` (QST-qfbm3): shell completion scripts
for bash, zsh and fish, with dynamic completion of quest ids, project names,
and schema field names delegated -- inside the generated script -- to `quest`
itself (`quest list --select id`, `quest logs --format json`,
`quest schema quest --format json`).

Real bash and its completion mechanism (`complete`, `compgen`, `COMPREPLY`)
are exercised directly for the bash script: a stub `quest` executable on
PATH stands in for the real CLI, so the test proves the generated script's
actual completion logic, not just its text. zsh and fish binaries aren't
available in this environment, so those two are checked structurally.
"""

from __future__ import annotations

import os
import stat
import subprocess

from questkit.cli import build_parser
from questkit.commands.completion_cmd import bash_script, fish_script, zsh_script

ALL_SUBCOMMANDS = set(build_parser()._subparsers._group_actions[0].choices)
ID_SUBCOMMANDS = ("show", "edit", "open", "set", "done", "scrap", "archive", "unarchive", "mv", "deps", "brief")


def test_completion_bash_registers_both_prog_names():
    script = bash_script()
    assert "complete -F" in script
    assert "quest" in script
    assert "qst" in script


def test_completion_bash_lists_every_subcommand():
    script = bash_script()
    for name in ALL_SUBCOMMANDS:
        assert name in script


def test_completion_zsh_is_a_compdef_script():
    script = zsh_script()
    assert script.startswith("#compdef quest qst")
    for name in ALL_SUBCOMMANDS:
        assert name in script


def test_completion_fish_registers_both_prog_names():
    script = fish_script()
    assert "complete -c quest" in script
    assert "complete -c qst" in script


def test_completion_cli_prints_the_right_script_per_shell(run):
    bash_result = run("completion", "bash")
    zsh_result = run("completion", "zsh")
    fish_result = run("completion", "fish")

    assert bash_result.code == 0 and bash_result.out.strip() == bash_script().strip()
    assert zsh_result.code == 0 and zsh_result.out.strip() == zsh_script().strip()
    assert fish_result.code == 0 and fish_result.out.strip() == fish_script().strip()


# --- real bash execution: proves the generated completion logic works -------------


def _stub_quest(tmp_path, csv_ids=(), logs_json="[]", schema_json="{}"):
    """A fake `quest` (and `qst`) on PATH that answers the three calls the
    generated script's dynamic completion delegates to it -- standing in for
    the real CLI so the test exercises the actual bash completion logic."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    csv_body = "id\n" + "\n".join(csv_ids)
    script = f"""#!/usr/bin/env bash
if [[ "$1 $2 $3" == "list --format csv" ]] || [[ "$*" == *"list --format csv"* ]]; then
  cat <<'EOF'
{csv_body}
EOF
  exit 0
fi
if [[ "$*" == *"logs --format json"* ]]; then
  cat <<'EOF'
{logs_json}
EOF
  exit 0
fi
if [[ "$*" == *"schema quest --format json"* ]]; then
  cat <<'EOF'
{schema_json}
EOF
  exit 0
fi
exit 1
"""
    for name in ("quest", "qst"):
        stub = bin_dir / name
        stub.write_text(script)
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    return bin_dir


def _complete(tmp_path, comp_words, cword, bin_dir=None):
    """Source the real generated bash script, run its completion function
    with COMP_WORDS/COMP_CWORD set as bash itself would, and return COMPREPLY."""
    script_path = tmp_path / "quest_completion.bash"
    script_path.write_text(bash_script())
    words = " ".join(f'"{w}"' for w in comp_words)
    env = dict(os.environ)
    if bin_dir is not None:
        env["PATH"] = f"{bin_dir}:{env['PATH']}"
    proc = subprocess.run(
        [
            "bash", "-c",
            f'source "{script_path}"; COMP_WORDS=({words}); COMP_CWORD={cword}; '
            f'_quest_complete; printf "%s\\n" "${{COMPREPLY[@]}}"',
        ],
        capture_output=True, text=True, env=env, timeout=10,
    )
    assert proc.returncode == 0, proc.stderr
    return [line for line in proc.stdout.splitlines() if line]


def test_bash_completes_subcommands_at_the_first_word(tmp_path):
    completions = _complete(tmp_path, ["quest", ""], 1)
    assert "new" in completions
    assert "show" in completions
    assert "list" in completions


def test_bash_completes_subcommands_filtered_by_prefix(tmp_path):
    completions = _complete(tmp_path, ["quest", "sh"], 1)
    assert completions == ["show"]


def test_bash_completes_quest_ids_after_an_id_taking_subcommand(tmp_path):
    bin_dir = _stub_quest(tmp_path, csv_ids=["QST-aaaaa", "QST-bbbbb"])
    completions = _complete(tmp_path, ["quest", "show", ""], 2, bin_dir=bin_dir)
    assert set(completions) == {"QST-aaaaa", "QST-bbbbb"}


def test_bash_completes_ids_for_every_id_taking_subcommand(tmp_path):
    bin_dir = _stub_quest(tmp_path, csv_ids=["QST-ccccc"])
    for sub in ID_SUBCOMMANDS:
        completions = _complete(tmp_path, ["quest", sub, ""], 2, bin_dir=bin_dir)
        assert "QST-ccccc" in completions, f"no id completion for '{sub}'"


def test_bash_completes_project_names_after_dash_dash_in(tmp_path):
    logs_json = '[{"project": "family", "path": "quests"}, {"project": "work", "path": "other/quests"}]'
    bin_dir = _stub_quest(tmp_path, logs_json=logs_json)
    completions = _complete(tmp_path, ["quest", "list", "--in", ""], 3, bin_dir=bin_dir)
    assert set(completions) == {"family", "work"}


def test_bash_completes_field_names_after_dash_dash_where(tmp_path):
    schema_json = '{"core_fields": {"status": {}, "priority": {}}, "fields": {"component": {}}}'
    bin_dir = _stub_quest(tmp_path, schema_json=schema_json)
    completions = _complete(tmp_path, ["quest", "list", "--where", ""], 3, bin_dir=bin_dir)
    assert {"status", "priority", "component"} <= set(completions)


def test_bash_completes_flags_for_a_subcommand(tmp_path):
    completions = _complete(tmp_path, ["quest", "list", "--"], 2)
    assert "--where" in completions
    assert "--format" in completions


def test_bash_works_when_invoked_as_qst(tmp_path):
    """The completion function reads the actual typed prog name from
    COMP_WORDS[0], so it must behave identically whether registered for
    `quest` or its `qst` alias."""
    bin_dir = _stub_quest(tmp_path, csv_ids=["QST-ddddd"])
    completions = _complete(tmp_path, ["qst", "show", ""], 2, bin_dir=bin_dir)
    assert "QST-ddddd" in completions
