"""Detect the best available H.264 hardware encoder via ffmpeg."""

import functools
import logging
import subprocess

_log = logging.getLogger(__name__)


# Probe order: NVIDIA NVENC → AMD/Intel VAAPI → Intel Quick Sync → Apple VideoToolbox → CPU
_ENCODER_PRIORITY = [
    "h264_nvenc",
    "h264_vaapi",
    "h264_qsv",
    "h264_videotoolbox",
    "libx264",
]

_X264_TO_NVENC_PRESET: dict[str, str] = {
    "ultrafast": "p1",
    "superfast": "p1",
    "veryfast": "p2",
    "faster": "p3",
    "fast": "p4",
    "medium": "p4",
    "slow": "p5",
    "slower": "p6",
    "veryslow": "p7",
}


def _encoder_works(encoder: str) -> bool:
    """Return True if *encoder* can encode at least one frame without error."""
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-f", "lavfi", "-i", "color=s=16x16:r=1",
                "-frames:v", "1",
                "-c:v", encoder,
                "-f", "null", "-",
            ],
            capture_output=True,
            timeout=10,
            check=True,
        )
        return True
    except Exception:
        return False


@functools.lru_cache(maxsize=1)
def _detect_hw_encoder() -> str:
    """Return the best available H.264 encoder name, preferring hardware."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-encoders", "-v", "quiet"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        available = result.stdout
    except Exception:
        return "libx264"

    for encoder in _ENCODER_PRIORITY:
        if encoder in available and _encoder_works(encoder):
            if encoder == "libx264":
                _log.info("GPU encoder not found; using libx264 (CPU)")
            else:
                _log.info("Using hardware encoder: %s", encoder)
            return encoder
    return "libx264"


def _nvenc_preset(x264_preset: str) -> str:
    return _X264_TO_NVENC_PRESET.get(x264_preset, "p5")
