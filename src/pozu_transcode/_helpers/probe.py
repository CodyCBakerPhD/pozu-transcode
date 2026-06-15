"""ffprobe wrapper: read a source video's first video stream."""

import json
import subprocess

from .._models import ProbeResult
from .io import PathLike


def _probe(path: PathLike) -> ProbeResult:
    """Run ffprobe on ``path`` and return its first video stream's geometry."""
    out = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,avg_frame_rate,codec_name",
            "-show_entries", "format=duration", "-of", "json", str(path),
        ],
        capture_output=True, text=True, check=True,
    ).stdout
    j = json.loads(out)
    st = j["streams"][0]

    def rate(s: str) -> float:
        n, _, d = s.partition("/")
        denom = float(d) if d else 1.0
        denom = denom or 1.0
        return float(n) / denom

    return ProbeResult(
        width=int(st["width"]),
        height=int(st["height"]),
        nominal_frames_per_second=rate(st["r_frame_rate"]),
        average_frames_per_second=rate(st.get("avg_frame_rate", st["r_frame_rate"])),
        codec=st["codec_name"],
        duration=float(j["format"]["duration"]),
    )
