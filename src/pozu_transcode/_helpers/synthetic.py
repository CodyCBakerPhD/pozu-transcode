"""Generate synthetic test videos via ffmpeg's lavfi source."""

import subprocess
from pathlib import Path

from .io import PathLike


def _create_sample_video(
    path: PathLike,
    *,
    width: int = 640,
    height: int = 640,
    frames_per_second: int = 60,
    duration_seconds: float = 2.0,
    include_audio: bool = True,
) -> Path:
    """Create a small synthetic video at *path* using ffmpeg's ``testsrc2`` source.

    Defaults to a 640×640 square frame at 60 fps with a 440 Hz sine-wave audio track,
    giving values that clearly map onto the square canvas and stand apart from typical
    production footage. Pass ``include_audio=False`` to omit the audio stream.

    Requires ffmpeg on PATH. Intended for generating test fixtures and demo assets.
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=size={width}x{height}:rate={frames_per_second}",
    ]
    if include_audio:
        cmd += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100"]
    cmd += [
        "-t",
        str(duration_seconds),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
    ]
    if include_audio:
        cmd += ["-c:a", "aac"]
    else:
        cmd += ["-an"]
    cmd.append(str(out))

    subprocess.run(cmd, check=True, capture_output=True)
    return out
