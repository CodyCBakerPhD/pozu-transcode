"""Resolve a probe + config into a concrete encode plan and ffmpeg command."""

from typing import List, Optional

from .._config import DEFAULT_CONFIG, TranscodeConfig
from .._models import EncodePlan, ProbeResult
from .geometry import _compute_letterbox, _pick_canvas
from .io import PathLike


def _plan_encode(
    src_path: PathLike,
    out_path: PathLike,
    probe_result: ProbeResult,
    config: Optional[TranscodeConfig] = None,
) -> EncodePlan:
    """Resolve a probe + config into a concrete `EncodePlan`."""
    config = config or DEFAULT_CONFIG
    canvas = _pick_canvas(probe_result.aspect_ratio, config.canvases)
    box = _compute_letterbox(
        probe_result.width, probe_result.height,
        canvas.width, canvas.height, config.allow_upscale,
    )
    frames_per_second = (
        config.frames_per_second
        if config.frames_per_second
        else round(probe_result.nominal_frames_per_second)
    )
    frames_per_second = max(1, int(frames_per_second))
    group_of_pictures = max(1, round(frames_per_second * config.group_of_pictures_in_seconds))
    return EncodePlan(
        src_path=str(src_path),
        out_path=str(out_path),
        source_width=probe_result.width,
        source_height=probe_result.height,
        bucket=canvas.name,
        canvas_width=canvas.width,
        canvas_height=canvas.height,
        active_width=box.active_width,
        active_height=box.active_height,
        pad_x=box.pad_x,
        pad_y=box.pad_y,
        frames_per_second=frames_per_second,
        group_of_pictures=group_of_pictures,
        constant_rate_factor=config.constant_rate_factor,
        preset=config.preset,
        audio_bitrate=config.audio_bitrate,
    )


def _build_ffmpeg_command(plan: EncodePlan) -> List[str]:
    """Build the ffmpeg argv for ``plan``. Pure: no side effects."""
    vf = (
        f"scale={plan.active_width}:{plan.active_height}:flags=lanczos,"
        f"pad={plan.canvas_width}:{plan.canvas_height}:{plan.pad_x}:{plan.pad_y}:color=black,"
        f"setsar=1"
    )
    return [
        "ffmpeg", "-y", "-i", plan.src_path,
        "-vf", vf,
        "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-crf", str(plan.constant_rate_factor), "-preset", plan.preset,
        "-g", str(plan.group_of_pictures), "-keyint_min", str(plan.group_of_pictures),
        "-x264-params", "scenecut=0:open-gop=0", "-bf", "2",
        "-fps_mode", "cfr", "-r", str(plan.frames_per_second),
        "-c:a", "aac", "-b:a", plan.audio_bitrate,
        "-movflags", "+faststart", plan.out_path,
    ]
