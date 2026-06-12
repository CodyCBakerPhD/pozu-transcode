"""Package version.

Single source of truth is ``[project].version`` in ``pyproject.toml``,
surfaced here from the installed distribution metadata.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__: str = version("pozu-transcode")
except PackageNotFoundError:  # not installed (e.g. running from a raw checkout)
    __version__ = "0.0.0+unknown"
