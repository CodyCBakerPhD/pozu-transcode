"""Configuration defaults for the canonical pozu transcode space.

Everything here is a plain default that the CLI (and library callers) can
override. The :class:`AspectCanvas` / :class:`TranscodeConfig` dataclasses are the
shared vocabulary that ``core`` speaks in.
"""

from dataclasses import dataclass, field
from typing import List

# ── canonical encode defaults ───────────────────────────────────────────────
DEFAULT_CRF: int = 20
DEFAULT_PRESET: str = "slow"
DEFAULT_GOP_SECONDS: float = 1.0
DEFAULT_FPS: int = 30  # force CFR to this; 0 keeps source fps (still CFR)
DEFAULT_ALLOW_UPSCALE: bool = False
DEFAULT_AUDIO_BITRATE: str = "128k"

# Recognized input container extensions (case-insensitive).
VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v")


@dataclass(frozen=True)
class AspectCanvas:
    """A fixed-aspect-ratio output canvas.

    Videos are assigned to the nearest bucket in log-aspect-ratio space, then
    uniform-scaled + letterbox-padded into ``width`` x ``height``.
    """

    name: str
    width: int
    height: int

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height


# Default canvases (~0.52 MP each, even dims). Tune to your corpus.
DEFAULT_CANVASES: List[AspectCanvas] = [
    AspectCanvas("sq", 720, 720),    # 1.00
    AspectCanvas("4x3", 832, 624),   # 1.33
    AspectCanvas("16x9", 960, 540),  # 1.78
]


@dataclass
class TranscodeConfig:
    """All knobs shared by the ``single``, ``batch`` and ``survey`` commands."""

    crf: int = DEFAULT_CRF
    preset: str = DEFAULT_PRESET
    gop_seconds: float = DEFAULT_GOP_SECONDS
    fps: int = DEFAULT_FPS
    allow_upscale: bool = DEFAULT_ALLOW_UPSCALE
    audio_bitrate: str = DEFAULT_AUDIO_BITRATE
    canvases: List[AspectCanvas] = field(default_factory=lambda: list(DEFAULT_CANVASES))
