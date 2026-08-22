"""Tests for `quest version` / `quest --version`.

Both print the exact same string, from the one source of truth
(`questkit.__version__`, itself read from the installed package's metadata
-- see `__init__.py`) rather than a hand-duplicated string that could drift
from `pyproject.toml` the way it already had once.
"""

from __future__ import annotations

import pytest

from questkit import __version__
from questkit.cli import build_parser, main


def test_version_subcommand_prints_the_package_version(run):
    result = run("version")

    assert result.code == 0
    assert result.out.strip() == f"questkit {__version__}"


def test_dash_dash_version_prints_the_same_string(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])

    assert exc_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"questkit {__version__}"


def test_dash_dash_version_works_with_no_subcommand_given(capsys):
    """argparse's required=True on the subparsers must not shadow --version."""
    parser = build_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--version"])

    assert exc_info.value.code == 0


def test_version_is_never_the_stale_placeholder():
    """Regression guard for the exact bug found in review: __init__.py's
    __version__ once hand-duplicated pyproject.toml's and had already
    drifted (0.2.0 vs 0.3.0) by the time this was noticed."""
    assert __version__ != "0.2.0"


def test_version_appears_in_the_introspect_help_group(capsys):
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--help"])
    out = capsys.readouterr().out
    introspect_start = out.index("Introspect")
    assert "version" in out[introspect_start:]
