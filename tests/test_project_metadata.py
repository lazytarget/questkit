"""The links PyPI shows on the project page come from `[project.urls]`.

PyPI marks a URL as verified only at upload time, and only a GitHub URL for the
repository the trusted publisher is configured for. The Gitea host is private and
unreachable for readers, so it must not be listed.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "https://github.com/lazytarget/questkit"


def _urls() -> dict:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]["urls"]


def test_the_labels_pypi_recognises_are_present():
    assert {"Homepage", "Source", "Changelog", "Documentation"} <= set(_urls())


def test_every_link_points_into_the_github_repository():
    for label, url in _urls().items():
        assert url == REPO or url.startswith(REPO + "/"), (label, url)


def test_no_link_names_the_private_gitea_host():
    for label, url in _urls().items():
        assert "gitea" not in url.lower(), (label, url)


def test_the_file_links_point_at_files_that_exist():
    prefix = REPO + "/blob/main/"
    for label, url in _urls().items():
        if url.startswith(prefix):
            assert (ROOT / url[len(prefix):]).is_file(), (label, url)
