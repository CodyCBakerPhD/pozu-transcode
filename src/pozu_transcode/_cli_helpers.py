"""Helper utilities shared across CLI commands.

Keeps :mod:`pozu_transcode._cli` focused on click group/command definitions.
"""

from typing import List, Optional, Tuple

import rich_click as click

from ._config import (
    DEFAULT_ALLOW_UPSCALE,
    DEFAULT_BUCKETS,
    DEFAULT_CRF,
    DEFAULT_FPS,
    DEFAULT_GOP_SECONDS,
    DEFAULT_PRESET,
    Bucket,
    TranscodeConfig,
)


def _parse_buckets(values: Tuple[str, ...]) -> Optional[List[Bucket]]:
    """Parse repeatable ``NAME:WxH`` strings into a bucket list (or None)."""
    if not values:
        return None
    buckets: List[Bucket] = []
    for raw in values:
        try:
            name, dims = raw.split(":", 1)
            w_str, h_str = dims.lower().split("x", 1)
            buckets.append(Bucket(name=name, width=int(w_str), height=int(h_str)))
        except ValueError:
            raise click.BadParameter(
                f"{raw!r} is not in NAME:WxH form (e.g. 16x9:960x540)",
                param_hint="--bucket",
            )
    return buckets


def shared_options(func):
    """Attach the encode/bucket options shared by every command."""
    options = [
        click.option("--crf", type=int, default=DEFAULT_CRF, show_default=True,
                     help="x264 constant rate factor (lower = higher quality)."),
        click.option("--preset", default=DEFAULT_PRESET, show_default=True,
                     help="x264 preset (e.g. slow, medium, fast)."),
        click.option("--gop-seconds", type=float, default=DEFAULT_GOP_SECONDS,
                     show_default=True,
                     help="Keyframe interval in seconds (closed GOP)."),
        click.option("--fps", type=int, default=DEFAULT_FPS, show_default=True,
                     help="Force CFR to this fps; 0 keeps source fps (still CFR)."),
        click.option("--allow-upscale/--no-upscale", default=DEFAULT_ALLOW_UPSCALE,
                     show_default=True,
                     help="Allow upscaling sources smaller than the canvas."),
        click.option("--bucket", "buckets", multiple=True, metavar="NAME:WxH",
                     help="Override aspect buckets (repeatable). "
                          "Default: sq:720x720 4x3:832x624 16x9:960x540."),
    ]
    for option in reversed(options):
        func = option(func)
    return func


def _config_from(crf, preset, gop_seconds, fps, allow_upscale, buckets) -> TranscodeConfig:
    parsed = _parse_buckets(buckets)
    cfg = TranscodeConfig(
        crf=crf,
        preset=preset,
        gop_seconds=gop_seconds,
        fps=fps,
        allow_upscale=allow_upscale,
    )
    if parsed is not None:
        cfg.buckets = parsed
    return cfg
