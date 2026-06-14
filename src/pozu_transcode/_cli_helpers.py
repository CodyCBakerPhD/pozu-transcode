"""Helper utilities shared across CLI commands.

Keeps `pozu_transcode._cli` focused on click group/command definitions.
"""

from typing import List, Optional, Tuple

import rich_click as click

from ._config import (
    DEFAULT_CONFIG,
    AspectCanvas,
    TranscodeConfig,
)


def _parse_canvases(values: Tuple[str, ...]) -> Optional[List[AspectCanvas]]:
    """Parse repeatable ``NAME:WxH`` strings into a bucket list (or None)."""
    if not values:
        return None
    canvases: List[AspectCanvas] = []
    for raw in values:
        try:
            name, dims = raw.split(":", 1)
            w_str, h_str = dims.lower().split("x", 1)
            canvases.append(AspectCanvas(name=name, width=int(w_str), height=int(h_str)))
        except ValueError:
            raise click.BadParameter(
                f"{raw!r} is not in NAME:WxH form (e.g. 16x9:960x540)",
                param_hint="--canvas",
            )
    return canvases


def _shared_options(func):
    """Attach the encode/canvas options shared by every command."""
    options = [
        click.option("--crf", type=int, default=DEFAULT_CONFIG.constant_rate_factor,
                     show_default=True,
                     help="x264 constant rate factor (lower = higher quality)."),
        click.option("--preset", default=DEFAULT_CONFIG.preset, show_default=True,
                     help="x264 preset (e.g. slow, medium, fast)."),
        click.option("--gop-seconds", type=float,
                     default=DEFAULT_CONFIG.group_of_pictures_seconds,
                     show_default=True,
                     help="Keyframe interval in seconds (closed GOP)."),
        click.option("--fps", type=int, default=DEFAULT_CONFIG.frames_per_second,
                     show_default=True,
                     help="Force CFR to this fps; 0 keeps source fps (still CFR)."),
        click.option("--allow-upscale/--no-upscale", default=DEFAULT_CONFIG.allow_upscale,
                     show_default=True,
                     help="Allow upscaling sources smaller than the canvas."),
        click.option("--canvas", "canvases", multiple=True, metavar="NAME:WxH",
                     help="Override aspect canvases (repeatable). "
                          "Default: sq:360x360 4x3:416x312 16x9:480x270."),
    ]
    for option in reversed(options):
        func = option(func)
    return func


def _config_from(crf, preset, gop_seconds, fps, allow_upscale, canvases) -> TranscodeConfig:
    # CLI flags stay short (--crf/--fps/--gop-seconds); map them onto the
    # full config field names here.
    parsed = _parse_canvases(canvases)
    cfg = TranscodeConfig(
        constant_rate_factor=crf,
        preset=preset,
        group_of_pictures_seconds=gop_seconds,
        frames_per_second=fps,
        allow_upscale=allow_upscale,
    )
    if parsed is not None:
        cfg.canvases = parsed
    return cfg
