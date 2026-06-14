"""Framework-agnostic transcode operations: paths in, dataclasses out.

The public functions here back the CLI commands. They run entirely on local
files — no click, no printing, no cloud — shelling out to ffmpeg/ffprobe to
render videos into the project's canonical playback space (see the README).
"""

import subprocess
from pathlib import Path
from typing import List, Optional

from ._config import DEFAULT_CONFIG, TranscodeConfig
from ._helpers import (
    PathLike,
    _build_ffmpeg_command,
    _iter_videos,
    _pick_canvas,
    _plan_encode,
    _probe,
    _read_path_list,
    _write_manifest,
)
from ._models import SurveyEntry, TranscodeRecord

MANIFEST_NAME = "manifest.json"


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
    frame_count = round(out_probe.duration * plan.frames_per_second)
    return TranscodeRecord(
        video_id=Path(out_path).name,
        src_path=str(src_path),
        out_path=str(out_path),
        source_width=plan.source_width,
        source_height=plan.source_height,
        frame_count=frame_count,
        bucket=plan.bucket,
        canvas_width=plan.canvas_width,
        canvas_height=plan.canvas_height,
        active_width=plan.active_width,
        active_height=plan.active_height,
        pad_x=plan.pad_x,
        pad_y=plan.pad_y,
        frames_per_second=plan.frames_per_second,
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
        canvas = _pick_canvas(m.aspect_ratio, config.canvases)
        entries.append(
            SurveyEntry(
                path=str(src),
                width=m.width,
                height=m.height,
                aspect_ratio=m.aspect_ratio,
                codec=m.codec,
                nominal_frames_per_second=m.nominal_frames_per_second,
                has_variable_frame_rate=m.has_variable_frame_rate,
                bucket=canvas.name,
            )
        )
    return entries
