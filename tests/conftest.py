"""Shared pytest fixtures."""

import shutil
from pathlib import Path

import pytest

from pozu_transcode._helpers import _create_sample_video

_FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None

requires_ffmpeg = pytest.mark.skipif(not _FFMPEG_AVAILABLE, reason="ffmpeg not on PATH")


@pytest.fixture(scope="session")
def sample_video(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Session-scoped 640×480 @ 30 fps, 2-second H.264 synthetic video."""
    root = tmp_path_factory.mktemp("assets")
    return _create_sample_video(root / "sample.mp4", width=640, height=480, frames_per_second=30, duration_seconds=2.0)
