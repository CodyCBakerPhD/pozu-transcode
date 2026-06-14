"""Private implementation helpers, split by theme.

geometry: canvas selection + letterbox math
probe:    ffprobe wrapper
planning: probe/config to encode plan + ffmpeg command
io:       filesystem discovery and manifest writing
cli:      shared click options

Nothing here is part of the supported API.
"""

from .cli import _config_from, _parse_canvases, _shared_options
from .geometry import _compute_letterbox, _even, _pick_canvas
from .io import (
    PathLike,
    _aspect_histogram,
    _iter_videos,
    _read_path_list,
    _write_manifest,
)
from .planning import _build_ffmpeg_command, _plan_encode
from .probe import _probe

__all__ = [
    "PathLike",
    "_aspect_histogram",
    "_build_ffmpeg_command",
    "_compute_letterbox",
    "_config_from",
    "_even",
    "_iter_videos",
    "_parse_canvases",
    "_pick_canvas",
    "_plan_encode",
    "_probe",
    "_read_path_list",
    "_shared_options",
    "_write_manifest",
]
