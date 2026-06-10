"""Framework-agnostic transcode core: paths in, dataclasses out.

This module is shared by every CLI command. It never imports click, never
prints, and never touches S3 — it operates on local files and shells out to the
external ``ffmpeg`` / ``ffprobe`` binaries (which must be on ``PATH``).

Canonical space (see README): H.264 High / yuv420p / +faststart, constant
frame rate, ~1s closed GOP for fast random-frame seeks, aspect-ratio bucketing
with uniform-scale + letterbox pad (never stretch, never crop).
"""

from __future__ import annotations

import collections
import json
import math
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Union

from .config import DEFAULT_BUCKETS, VIDEO_EXTENSIONS, Bucket, TranscodeConfig

PathLike = Union[str, "os.PathLike[str]"]


# ── result dataclasses ───────────────────────────────────────────────────────
@dataclass
class ProbeResult:
    """What ffprobe tells us about a source video's first video stream."""

    width: int
    height: int
    fps_r: float           # r_frame_rate (nominal)
    fps_avg: float         # avg_frame_rate (actual average)
    codec: str
    duration: float

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height

    @property
    def is_vfr(self) -> bool:
        return abs(self.fps_r - self.fps_avg) > 0.01


@dataclass
class Letterbox:
    """Active (scaled) dimensions plus the pad offsets inside a canvas."""

    active_w: int
    active_h: int
    pad_x: int
    pad_y: int


@dataclass
class EncodePlan:
    """A fully-resolved plan for one transcode — enough to build the command."""

    src_path: str
    out_path: str
    src_w: int
    src_h: int
    bucket: str
    canvas_w: int
    canvas_h: int
    active_w: int
    active_h: int
    pad_x: int
    pad_y: int
    fps: int
    gop: int
    crf: int
    preset: str
    audio_bitrate: str


@dataclass
class TranscodeRecord:
    """One manifest entry: everything needed to locate + reason about an output."""

    video_id: str
    src_path: str
    out_path: str
    src_w: int
    src_h: int
    frame_count: int
    bucket: str
    canvas_w: int
    canvas_h: int
    active_w: int
    active_h: int
    pad_x: int
    pad_y: int
    fps: int


# ── geometry helpers ─────────────────────────────────────────────────────────
def even(x: float) -> int:
    """Round to the nearest even integer (>= 2). yuv420p requires even dims."""
    return max(2, int(round(x / 2) * 2))


def pick_bucket(aspect_ratio: float, buckets: Sequence[Bucket] = DEFAULT_BUCKETS) -> Bucket:
    """Assign to the nearest bucket in log-AR space (minimizes letterbox area)."""
    return min(buckets, key=lambda b: abs(math.log(aspect_ratio / b.aspect_ratio)))


def compute_letterbox(
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
    aw, ah = even(src_w * scale), even(src_h * scale)
    return Letterbox(aw, ah, (canvas_w - aw) // 2, (canvas_h - ah) // 2)


# ── external tools ───────────────────────────────────────────────────────────
def probe(path: PathLike) -> ProbeResult:
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


# ── planning ─────────────────────────────────────────────────────────────────
def plan_encode(
    src_path: PathLike,
    out_path: PathLike,
    probe_result: ProbeResult,
    config: Optional[TranscodeConfig] = None,
) -> EncodePlan:
    """Resolve a probe + config into a concrete :class:`EncodePlan`."""
    config = config or TranscodeConfig()
    bucket = pick_bucket(probe_result.aspect_ratio, config.buckets)
    box = compute_letterbox(
        probe_result.width, probe_result.height,
        bucket.width, bucket.height, config.allow_upscale,
    )
    fps = config.fps if config.fps else round(probe_result.fps_r)
    fps = max(1, int(fps))
    gop = max(1, round(fps * config.gop_seconds))
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
        crf=config.crf,
        preset=config.preset,
        audio_bitrate=config.audio_bitrate,
    )


def build_ffmpeg_command(plan: EncodePlan) -> List[str]:
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


# ── transcoding ──────────────────────────────────────────────────────────────
def transcode(
    src_path: PathLike,
    out_path: PathLike,
    config: Optional[TranscodeConfig] = None,
) -> TranscodeRecord:
    """Probe, plan, encode one file, then re-probe the output for frame_count."""
    config = config or TranscodeConfig()
    src_probe = probe(src_path)
    plan = plan_encode(src_path, out_path, src_probe, config)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(build_ffmpeg_command(plan), check=True)

    out_probe = probe(out_path)
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


def iter_videos(input_dir: PathLike) -> Iterator[Path]:
    """Yield video files under ``input_dir`` (recursive), sorted, by extension."""
    root = Path(input_dir)
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
            yield path


def transcode_batch(
    input_dir: PathLike,
    output_dir: PathLike,
    config: Optional[TranscodeConfig] = None,
    on_progress=None,
) -> List[TranscodeRecord]:
    """Transcode every video under ``input_dir`` into ``output_dir`` (flat .mp4).

    ``on_progress(index, total, record)`` is called after each output if given.
    Returns the list of records (also write it with :func:`write_manifest`).
    """
    config = config or TranscodeConfig()
    out_root = Path(output_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    sources = list(iter_videos(input_dir))
    records: List[TranscodeRecord] = []
    for i, src in enumerate(sources):
        out_path = out_root / (src.stem + ".mp4")
        record = transcode(src, out_path, config)
        records.append(record)
        if on_progress is not None:
            on_progress(i + 1, len(sources), record)
    return records


# ── survey ───────────────────────────────────────────────────────────────────
@dataclass
class SurveyEntry:
    path: str
    width: int
    height: int
    aspect_ratio: float
    codec: str
    fps_r: float
    is_vfr: bool
    bucket: str


def aspect_histogram(entries: Sequence[SurveyEntry], precision: int = 2) -> Dict[float, int]:
    """Bucket survey entries into a rounded-AR -> count histogram."""
    hist: "collections.Counter[float]" = collections.Counter()
    for e in entries:
        hist[round(e.aspect_ratio, precision)] += 1
    return dict(sorted(hist.items()))


def survey(
    input_dir: PathLike,
    config: Optional[TranscodeConfig] = None,
) -> List[SurveyEntry]:
    """Probe every video under ``input_dir`` (no transcoding) for AR analysis."""
    config = config or TranscodeConfig()
    entries: List[SurveyEntry] = []
    for src in iter_videos(input_dir):
        m = probe(src)
        bucket = pick_bucket(m.aspect_ratio, config.buckets)
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


# ── manifest ─────────────────────────────────────────────────────────────────
def write_manifest(records: Sequence[TranscodeRecord], out_path: PathLike) -> Path:
    """Write ``records`` as a JSON array to ``out_path``. Returns the path."""
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(r) for r in records], indent=2))
    return path
