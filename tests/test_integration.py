"""ffmpeg-backed integration tests.

All tests in this file are skipped automatically when ffmpeg is not on PATH.
They exercise the full encode pipeline end-to-end rather than mocking ffmpeg.
"""

from pathlib import Path

import pytest
from conftest import requires_ffmpeg

from pozu_transcode import (
    AspectCanvas,
    TranscodeConfig,
    TranscodeRecord,
    survey,
    transcode,
    transcode_batch,
)
from pozu_transcode._helpers import _create_sample_video, _probe

# ── fixture helpers ───────────────────────────────────────────────────────────


@pytest.fixture()
def video_640x480(sample_video: Path) -> Path:
    """640×480 synthetic source — falls into the 4×3 bucket."""
    return sample_video


@pytest.fixture()
def video_1920x1080(tmp_path: Path) -> Path:
    """1920×1080 synthetic source — falls into the 16×9 bucket."""
    return _create_sample_video(
        tmp_path / "hd.mp4", width=1920, height=1080, frames_per_second=30, duration_seconds=1.0
    )


@pytest.fixture()
def video_360x360(tmp_path: Path) -> Path:
    """360×360 synthetic source — falls into the square bucket."""
    return _create_sample_video(tmp_path / "sq.mp4", width=360, height=360, frames_per_second=30, duration_seconds=1.0)


# ── _probe() ─────────────────────────────────────────────────────────────────


@requires_ffmpeg
def test_probe_returns_correct_geometry(sample_video: Path) -> None:
    result = _probe(sample_video)
    assert result.width == 640
    assert result.height == 480
    assert abs(result.nominal_frames_per_second - 30.0) < 0.1
    assert result.codec == "h264"
    assert abs(result.duration - 2.0) < 0.1


# ── transcode() ───────────────────────────────────────────────────────────────


@requires_ffmpeg
def test_transcode_produces_output_file(video_640x480: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.mp4"
    record = transcode(video_640x480, out)
    assert isinstance(record, TranscodeRecord)
    assert out.exists()
    assert out.stat().st_size > 0


@requires_ffmpeg
def test_transcode_output_is_canonical(video_640x480: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.mp4"
    transcode(video_640x480, out)
    probe = _probe(out)
    # output must be H.264 in yuv420p (ffprobe reports codec as h264)
    assert probe.codec == "h264"
    # aspect: 640x480 -> 4x3 bucket -> canvas 416x312
    assert probe.width == 416
    assert probe.height == 312


@requires_ffmpeg
def test_transcode_16x9_source(video_1920x1080: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.mp4"
    transcode(video_1920x1080, out)
    probe = _probe(out)
    # 16x9 canvas is 480x270
    assert probe.width == 480
    assert probe.height == 270


@requires_ffmpeg
def test_transcode_square_source(video_360x360: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.mp4"
    transcode(video_360x360, out)
    probe = _probe(out)
    # square canvas is 360x360
    assert probe.width == 360
    assert probe.height == 360


@requires_ffmpeg
def test_transcode_custom_canvas(video_1920x1080: Path, tmp_path: Path) -> None:
    config = TranscodeConfig(canvases=[AspectCanvas("portrait", 270, 480)])
    out = tmp_path / "out.mp4"
    record = transcode(video_1920x1080, out, config)
    assert record.bucket == "portrait"
    probe = _probe(out)
    assert probe.width == 270
    assert probe.height == 480


@requires_ffmpeg
def test_transcode_record_frame_count(video_640x480: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.mp4"
    record = transcode(video_640x480, out)
    # 2 seconds @ 30 fps → 60 frames (allow ±2 for rounding)
    assert abs(record.frame_count - 60) <= 2


# ── transcode_batch() ─────────────────────────────────────────────────────────


@requires_ffmpeg
def test_transcode_batch_writes_manifest(sample_video: Path, tmp_path: Path) -> None:
    list_file = tmp_path / "clips.txt"
    list_file.write_text(str(sample_video) + "\n")
    out_dir = tmp_path / "output"

    records = transcode_batch(list_file, out_dir)

    assert len(records) == 1
    assert (out_dir / "manifest.json").exists()
    assert isinstance(records[0], TranscodeRecord)


@requires_ffmpeg
def test_transcode_batch_multiple_files(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    _create_sample_video(src / "a.mp4", width=640, height=480)
    _create_sample_video(src / "b.mp4", width=1920, height=1080)

    list_file = tmp_path / "clips.txt"
    list_file.write_text(f"{src / 'a.mp4'}\n{src / 'b.mp4'}\n")
    out_dir = tmp_path / "output"

    records = transcode_batch(list_file, out_dir)

    assert len(records) == 2
    buckets = {r.bucket for r in records}
    assert "4x3" in buckets
    assert "16x9" in buckets


# ── survey() ──────────────────────────────────────────────────────────────────


@requires_ffmpeg
def test_survey_detects_source_dimensions(tmp_path: Path) -> None:
    _create_sample_video(tmp_path / "a.mp4", width=640, height=480)
    _create_sample_video(tmp_path / "b.mp4", width=1920, height=1080)

    entries = survey(tmp_path)

    assert len(entries) == 2
    dims = {(e.width, e.height) for e in entries}
    assert (640, 480) in dims
    assert (1920, 1080) in dims


@requires_ffmpeg
def test_survey_assigns_correct_buckets(tmp_path: Path) -> None:
    _create_sample_video(tmp_path / "sq.mp4", width=360, height=360)
    _create_sample_video(tmp_path / "hd.mp4", width=1920, height=1080)

    entries = survey(tmp_path)
    buckets = {e.bucket for e in entries}

    assert "square" in buckets
    assert "16x9" in buckets
