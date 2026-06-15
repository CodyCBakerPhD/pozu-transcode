"""Generate synthetic test videos via ffmpeg's lavfi source."""

import subprocess
from pathlib import Path

from .io import PathLike


def _create_sample_video(
    path: PathLike,
    *,
    width: int = 640,
    height: int = 480,
    frames_per_second: int = 30,
    duration_seconds: float = 2.0,
) -> Path:
    """Create a small synthetic video at *path* using ffmpeg's ``testsrc2`` source.

    Requires ffmpeg on PATH. Intended for generating test fixtures and demo assets.
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size={width}x{height}:rate={frames_per_second}",
            "-t",
            str(duration_seconds),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(out),
        ],
        check=True,
        capture_output=True,
    )
    return out
