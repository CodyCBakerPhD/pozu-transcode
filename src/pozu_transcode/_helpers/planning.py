"""Resolve a probe + config into a concrete encode plan and ffmpeg command."""

from .._config import DEFAULT_CONFIG, TranscodeConfig
from .._models import EncodePlan, ProbeResult
from .geometry import _compute_letterbox, _pick_canvas
from .gpu import _detect_hw_encoder, _nvenc_preset
from .io import PathLike


def _plan_encode(
    src_path: PathLike,
    out_path: PathLike,
    probe_result: ProbeResult,
    config: TranscodeConfig | None = None,
) -> EncodePlan:
    """Resolve a probe + config into a concrete `EncodePlan`."""
    config = config or DEFAULT_CONFIG
    canvas = _pick_canvas(probe_result.aspect_ratio, config.canvases)
    box = _compute_letterbox(
        probe_result.width,
        probe_result.height,
        canvas.width,
        canvas.height,
    )
    frames_per_second = (
        config.frames_per_second if config.frames_per_second else round(probe_result.nominal_frames_per_second)
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
        encoder=config.encoder if config.encoder is not None else _detect_hw_encoder(),
    )


def _build_ffmpeg_command(plan: EncodePlan) -> list[str]:
    """Build the ffmpeg argv for ``plan``. Pure: no side effects."""
    vf = (
        f"scale={plan.active_width}:{plan.active_height}:flags=lanczos,"
        f"pad={plan.canvas_width}:{plan.canvas_height}:{plan.pad_x}:{plan.pad_y}:color=black,"
        f"setsar=1"
    )
    base = ["ffmpeg", "-y", "-i", plan.src_path, "-vf", vf]
    tail = ["-fps_mode", "cfr", "-r", str(plan.frames_per_second), "-an", "-movflags", "+faststart", plan.out_path]

    if plan.encoder == "h264_nvenc":
        return [
            *base,
            "-c:v",
            "h264_nvenc",
            "-profile:v",
            "high",
            "-pix_fmt",
            "yuv420p",
            "-cq",
            str(plan.constant_rate_factor),
            "-preset",
            _nvenc_preset(plan.preset),
            "-g",
            str(plan.group_of_pictures),
            "-keyint_min",
            str(plan.group_of_pictures),
            "-bf",
            "2",
            *tail,
        ]

    if plan.encoder == "h264_vaapi":
        # Software decode/filter → VAAPI encode; format=nv12 feeds the VAAPI encoder.
        vf_vaapi = vf + ",format=nv12|vaapi,hwupload"
        return [
            *base[:-2],
            "-vf",
            vf_vaapi,
            "-c:v",
            "h264_vaapi",
            "-profile:v",
            "100",
            "-qp",
            str(plan.constant_rate_factor),
            "-g",
            str(plan.group_of_pictures),
            "-keyint_min",
            str(plan.group_of_pictures),
            "-bf",
            "2",
            *tail,
        ]

    if plan.encoder == "h264_qsv":
        return [
            *base,
            "-c:v",
            "h264_qsv",
            "-profile:v",
            "high",
            "-pix_fmt",
            "yuv420p",
            "-global_quality",
            str(plan.constant_rate_factor),
            "-g",
            str(plan.group_of_pictures),
            "-keyint_min",
            str(plan.group_of_pictures),
            *tail,
        ]

    if plan.encoder == "h264_videotoolbox":
        # VideoToolbox uses quality 1-100 (100=best); invert CRF (0-51 lower=better).
        vt_quality = max(1, min(100, round((51 - plan.constant_rate_factor) * 100 / 51)))
        return [
            *base,
            "-c:v",
            "h264_videotoolbox",
            "-profile:v",
            "high",
            "-pix_fmt",
            "yuv420p",
            "-q:v",
            str(vt_quality),
            "-g",
            str(plan.group_of_pictures),
            "-keyint_min",
            str(plan.group_of_pictures),
            *tail,
        ]

    # libx264 (CPU fallback)
    return [
        *base,
        "-c:v",
        "libx264",
        "-profile:v",
        "high",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        str(plan.constant_rate_factor),
        "-preset",
        plan.preset,
        "-g",
        str(plan.group_of_pictures),
        "-keyint_min",
        str(plan.group_of_pictures),
        "-x264-params",
        "scenecut=0:open-gop=0",
        "-bf",
        "2",
        *tail,
    ]
