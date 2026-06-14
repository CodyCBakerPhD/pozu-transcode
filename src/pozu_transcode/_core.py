"""Framework-agnostic transcode core: paths in, dataclasses out.

This module is shared by every CLI command. It never imports click, never
prints, and never touches S3 — it operates on local files and shells out to the
external ``ffmpeg`` / ``ffprobe`` binaries (which must be on ``PATH``).

The public surface mirrors the CLI commands: :func:`transcode` (``transcode
video``), :func:`transcode_batch` (``transcode batch``) and :func:`survey`
(``survey``). Everything else here is an intermediate helper (``_``-prefixed)
and is not part of the supported API.

Canonical space (see README): H.264 High / yuv420p / +faststart, constant
frame rate, ~1s closed GOP for fast random-frame seeks, aspect-ratio bucketing
with uniform-scale + letterbox pad (never stretch, never crop).
"""

import collections
import json
import math
import os
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Union

from ._config import DEFAULT_CONFIG, DEFAULT_CANVASES, VIDEO_EXTENSIONS, AspectCanvas, TranscodeConfig
from ._models import EncodePlan, Letterbox, ProbeResult, SurveyEntry, TranscodeRecord

PathLike = Union[str, "os.PathLike[str]"]

MANIFEST_NAME = "manifest.json"


# ── geometry helpers (private) ───────────────────────────────────────────────
def _even(x: float) -> int:
    """Round to the nearest even integer (>= 2). yuv420p requires even dims."""
    return max(2, int(round(x / 2) * 2))


def _pick_canvas(aspect_ratio: float, canvases: Sequence[AspectCanvas] = DEFAULT_CANVASES) -> AspectCanvas:
    """Assign to the nearest bucket in log-AR space (minimizes letterbox area)."""
    return min(canvases, key=lambda b: abs(math.log(aspect_ratio / b.aspect_ratio)))


def _compute_letterbox(
    src_w: int,
    src_h: int,
    canvas_w: int,
    canvas_h: int,
    allow_upscale: bool = False,
) -> Letterbox:
    """Uniform-scale ``src`` to fit inside the canvas, then center-pad.

    Downscale-only unless ``allow_upscale`` — we never invent detail in sources
    smaller than the canvas.
    """
    scale = min(canvas_w / src_w, canvas_h / src_h)
    if not allow_upscale:
        scale = min(scale, 1.0)
    aw, ah = _even(src_w * scale), _even(src_h * scale)
    return Letterbox(aw, ah, (canvas_w - aw) // 2, (canvas_h - ah) // 2)


# ── external tools (private) ─────────────────────────────────────────────────
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
        fps_r=rate(st["r_frame_rate"]),
        fps_avg=rate(st.get("avg_frame_rate", st["r_frame_rate"])),
        codec=st["codec_name"],
        duration=float(j["format"]["duration"]),
    )


# ── planning (private) ───────────────────────────────────────────────────────
def _plan_encode(
    src_path: PathLike,
    out_path: PathLike,
    probe_result: ProbeResult,
    config: Optional[TranscodeConfig] = None,
) -> EncodePlan:
    """Resolve a probe + config into a concrete :class:`EncodePlan`."""
    config = config or DEFAULT_CONFIG
    bucket = _pick_canvas(probe_result.aspect_ratio, config.canvases)
    box = _compute_letterbox(
        probe_result.width, probe_result.height,
        bucket.width, bucket.height, config.allow_upscale,
    )
    fps = config.frames_per_second if config.frames_per_second else round(probe_result.fps_r)
    fps = max(1, int(fps))
    gop = max(1, round(fps * config.group_of_pictures_seconds))
    return EncodePlan(
        src_path=str(src_path),
        out_path=str(out_path),
        src_w=probe_result.width,
        src_h=probe_result.height,
        bucket=bucket.name,
        canvas_w=bucket.width,
        canvas_h=bucket.height,
        active_w=box.active_w,
        active_h=box.active_h,
        pad_x=box.pad_x,
        pad_y=box.pad_y,
        fps=fps,
        gop=gop,
        crf=config.constant_rate_factor,
        preset=config.preset,
        audio_bitrate=config.audio_bitrate,
    )


def _build_ffmpeg_command(plan: EncodePlan) -> List[str]:
    """Build the ffmpeg argv for ``plan``. Pure: no side effects."""
    vf = (
        f"scale={plan.active_w}:{plan.active_h}:flags=lanczos,"
        f"pad={plan.canvas_w}:{plan.canvas_h}:{plan.pad_x}:{plan.pad_y}:color=black,"
        f"setsar=1"
    )
    return [
        "ffmpeg", "-y", "-i", plan.src_path,
        "-vf", vf,
        "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-crf", str(plan.crf), "-preset", plan.preset,
        "-g", str(plan.gop), "-keyint_min", str(plan.gop),
        "-x264-params", "scenecut=0:open-gop=0", "-bf", "2",
        "-fps_mode", "cfr", "-r", str(plan.fps),
        "-c:a", "aac", "-b:a", plan.audio_bitrate,
        "-movflags", "+faststart", plan.out_path,
    ]


# ── input discovery (private) ────────────────────────────────────────────────
def _iter_videos(input_dir: PathLike) -> Iterator[Path]:
    """Yield video files under ``input_dir`` (recursive), sorted, by extension."""
    root = Path(input_dir)
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
            yield path


def _read_path_list(list_file: PathLike) -> List[Path]:
    """Read a text file of video paths (one per line).

    Blank lines and lines starting with ``#`` are ignored. Relative paths are
    resolved against the list file's own directory, so a list is portable.
    """
    path = Path(list_file)
    base = path.parent
    sources: List[Path] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = Path(line)
        sources.append(p if p.is_absolute() else base / p)
    return sources


def _aspect_histogram(entries: Sequence[SurveyEntry], precision: int = 2) -> Dict[float, int]:
    """AspectCanvas survey entries into a rounded-AR -> count histogram."""
    hist: "collections.Counter[float]" = collections.Counter()
    for e in entries:
        hist[round(e.aspect_ratio, precision)] += 1
    return dict(sorted(hist.items()))


def _write_manifest(records: Sequence[TranscodeRecord], out_path: PathLike) -> Path:
    """Write ``records`` as a JSON array to ``out_path``. Returns the path."""
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(r) for r in records], indent=2))
    return path


# ── public operations (mirror the CLI commands) ──────────────────────────────
def transcode(
    src_path: PathLike,
    out_path: PathLike,
    config: Optional[TranscodeConfig] = None,
) -> TranscodeRecord:
    """Transcode one video file (mirrors ``pozu transcode video``).

    Probe, plan, encode, then re-probe the output for ``frame_count``.
    """
    config = config or DEFAULT_CONFIG
    src_probe = _probe(src_path)
    plan = _plan_encode(src_path, out_path, src_probe, config)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(_build_ffmpeg_command(plan), check=True)

    out_probe = _probe(out_path)
    frame_count = round(out_probe.duration * plan.fps)
    return TranscodeRecord(
        video_id=Path(out_path).name,
        src_path=str(src_path),
        out_path=str(out_path),
        src_w=plan.src_w,
        src_h=plan.src_h,
        frame_count=frame_count,
        bucket=plan.bucket,
        canvas_w=plan.canvas_w,
        canvas_h=plan.canvas_h,
        active_w=plan.active_w,
        active_h=plan.active_h,
        pad_x=plan.pad_x,
        pad_y=plan.pad_y,
        fps=plan.fps,
    )


def transcode_batch(
    list_file: PathLike,
    output_dir: PathLike,
    config: Optional[TranscodeConfig] = None,
    on_progress=None,
) -> List[TranscodeRecord]:
    """Transcode the videos listed in ``list_file`` (mirrors ``pozu transcode batch``).

    ``list_file`` is a text file with one video path per line (blank lines and
    lines starting with ``#`` are ignored; relative paths resolve against the
    list file's own directory). Outputs are written flat as ``<stem>.mp4`` into
    ``output_dir``, and a ``manifest.json`` is written there too.

    ``on_progress(index, total, record)`` is called after each output if given.
    Returns the list of records.
    """
    config = config or DEFAULT_CONFIG
    out_root = Path(output_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    sources = _read_path_list(list_file)
    records: List[TranscodeRecord] = []
    for i, src in enumerate(sources):
        out_path = out_root / (src.stem + ".mp4")
        record = transcode(src, out_path, config)
        records.append(record)
        if on_progress is not None:
            on_progress(i + 1, len(sources), record)

    _write_manifest(records, out_root / MANIFEST_NAME)
    return records


def survey(
    input_dir: PathLike,
    config: Optional[TranscodeConfig] = None,
) -> List[SurveyEntry]:
    """Probe every video under ``input_dir`` (mirrors ``pozu survey``).

    No transcoding — just resolution + aspect-ratio analysis.
    """
    config = config or DEFAULT_CONFIG
    entries: List[SurveyEntry] = []
    for src in _iter_videos(input_dir):
        m = _probe(src)
        bucket = _pick_canvas(m.aspect_ratio, config.canvases)
        entries.append(
            SurveyEntry(
                path=str(src),
                width=m.width,
                height=m.height,
                aspect_ratio=m.aspect_ratio,
                codec=m.codec,
                fps_r=m.fps_r,
                is_vfr=m.is_vfr,
                bucket=bucket.name,
            )
        )
    return entries
