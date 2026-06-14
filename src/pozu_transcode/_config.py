"""Configuration defaults for the canonical pozu transcode space.

Everything here is a plain default that the CLI (and library callers) can
override. The :class:`AspectCanvas` / :class:`TranscodeConfig` dataclasses are the
shared vocabulary that ``core`` speaks in.
"""

from dataclasses import dataclass, field
from typing import List

# ── canonical encode defaults ───────────────────────────────────────────────
DEFAULT_CONSTANT_RATE_FACTOR: int = 20  # x264 quality knob (lower = better quality)
DEFAULT_PRESET: str = "slow"
DEFAULT_GROUP_OF_PICTURES_SECONDS: float = 1.0  # keyframe interval, in seconds
DEFAULT_FRAMES_PER_SECOND: int = 30  # force constant frame rate (CFR); 0 keeps source rate
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


# Default canvases (~0.13 MP each, even dims). Tune to your corpus.
DEFAULT_CANVASES: List[AspectCanvas] = [
    AspectCanvas("sq", 360, 360),    # 1.00
    AspectCanvas("4x3", 416, 312),   # 1.33
    AspectCanvas("16x9", 480, 270),  # 1.78
]


@dataclass
class TranscodeConfig:
    """All knobs shared by the ``video``, ``batch`` and ``survey`` commands.

    Attributes
    ----------
    constant_rate_factor : int
        x264 Constant Rate Factor (CRF) quality control (lower = better quality,
        larger file; 0 = lossless, 51 = worst).
    preset : str
        x264 encoding speed preset; slower presets compress better at the same
        Constant Rate Factor (e.g. ``"ultrafast"``, ``"slow"``, ``"veryslow"``).
    group_of_pictures_seconds : float
        Target Group of Pictures (GOP) duration in seconds; controls the maximum
        distance between keyframes for random-access seeking.
    frames_per_second : int
        Output frame rate for Constant Frame Rate (CFR) encoding; ``0`` keeps the
        source frame rate while still enforcing a constant frame rate.
    allow_upscale : bool
        When ``True``, inputs smaller than the chosen canvas are scaled up to
        fill it; when ``False`` they are padded instead.
    audio_bitrate : str
        Advanced Audio Coding (AAC) encode bitrate (e.g. ``"128k"``).
    canvases : list of AspectCanvas
        Ordered list of candidate output canvases; each input video is assigned
        to the nearest canvas in log-aspect-ratio space.
    """

    constant_rate_factor: int = DEFAULT_CONSTANT_RATE_FACTOR
    preset: str = DEFAULT_PRESET
    group_of_pictures_seconds: float = DEFAULT_GROUP_OF_PICTURES_SECONDS
    frames_per_second: int = DEFAULT_FRAMES_PER_SECOND
    allow_upscale: bool = DEFAULT_ALLOW_UPSCALE
    audio_bitrate: str = DEFAULT_AUDIO_BITRATE
    canvases: List[AspectCanvas] = field(default_factory=lambda: list(DEFAULT_CANVASES))


# Canonical transcode configuration. Tune to your corpus.
DEFAULT_CONFIG: TranscodeConfig = TranscodeConfig()
