"""Aspect-canvas selection and letterbox geometry."""

import math
from typing import Sequence

from .._config import DEFAULT_CANVASES, AspectCanvas
from .._models import Letterbox


def _even(x: float) -> int:
    """Round to the nearest even integer (>= 2). yuv420p requires even dims."""
    return max(2, int(round(x / 2) * 2))


def _pick_canvas(aspect_ratio: float, canvases: Sequence[AspectCanvas] = DEFAULT_CANVASES) -> AspectCanvas:
    """Assign to the nearest canvas in log-AR space (minimizes letterbox area)."""
    return min(canvases, key=lambda b: abs(math.log(aspect_ratio / b.aspect_ratio)))


def _compute_letterbox(
    source_width: int,
    source_height: int,
    canvas_width: int,
    canvas_height: int,
    allow_upscale: bool = False,
) -> Letterbox:
    """Uniform-scale ``src`` to fit inside the canvas, then center-pad.

    Downscale-only unless ``allow_upscale`` — we never invent detail in sources
    smaller than the canvas.
    """
    scale = min(canvas_width / source_width, canvas_height / source_height)
    if not allow_upscale:
        scale = min(scale, 1.0)
    active_width, active_height = _even(source_width * scale), _even(source_height * scale)
    return Letterbox(
        active_width,
        active_height,
        (canvas_width - active_width) // 2,
        (canvas_height - active_height) // 2,
    )
