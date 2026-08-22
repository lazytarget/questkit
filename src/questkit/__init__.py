"""questkit: file-based quest tracking."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

try:
    # The one source of truth is pyproject.toml's [project] version -- this
    # reads it back from the installed package's own metadata rather than
    # duplicating the string here, which is exactly how `__version__` and
    # `pyproject.toml` drifted (0.2.0 here, 0.3.0 there) before this fix.
    __version__ = _version("questkit")
except PackageNotFoundError:
    # Only reachable running from an uninstalled source checkout -- every
    # real invocation (the `quest`/`qst` console scripts) implies an install,
    # so this is a defensive fallback, not the expected path.
    __version__ = "0.0.0+unknown"
