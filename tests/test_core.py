"""Unit tests for the framework-agnostic core. None of these need ffmpeg.

The intermediate helpers are private to ``pozu_transcode._core`` (the public
package only re-exports the command-mirroring operations and the dataclasses),
so the tests import them from the private module directly.
"""

import math
from pathlib import Path

import pytest

from pozu_transcode import AspectCanvas, ProbeResult, TranscodeConfig
from pozu_transcode._helpers import (
    _build_ffmpeg_command,
    _compute_letterbox,
    _even,
    _pick_canvas,
    _plan_encode,
    _read_path_list,
)


# ── _even() ──────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "value,expected",
    [(0, 2), (1, 2), (2, 2), (3, 4), (4, 4), (6, 6), (7, 8), (719, 720), (720.4, 720)],
)
def test_even(value: float, expected: int) -> None:
    assert _even(value) == expected
    assert _even(value) % 2 == 0


# ── _pick_canvas() ───────────────────────────────────────────────────────────
def test_pick_bucket_nearest_ar() -> None:
    # exact matches land on their own bucket
    assert _pick_canvas(1.0).name == "square"
    assert _pick_canvas(4 / 3).name == "4x3"
    assert _pick_canvas(16 / 9).name == "16x9"
    # near matches snap to the closest in log-AR space
    assert _pick_canvas(1.05).name == "square"
    assert _pick_canvas(1.40).name == "4x3"
    assert _pick_canvas(1.85).name == "16x9"
    # an ultrawide source still picks the widest available bucket
    assert _pick_canvas(2.39).name == "16x9"


def test_pick_bucket_is_log_space() -> None:
    # midpoint in log space between square (1.0) and 4x3 (1.333) is exp(mean of logs)
    mid = math.exp((math.log(1.0) + math.log(4 / 3)) / 2)
    # just above the log-midpoint should prefer 4x3
    assert _pick_canvas(mid * 1.001).name == "4x3"
    assert _pick_canvas(mid * 0.999).name == "square"


# ── _compute_letterbox() ─────────────────────────────────────────────────────
def test_letterbox_exact_fit_no_pad() -> None:
    # a 960x540 source into the 16x9 canvas fits exactly, no scaling, no pad
    box = _compute_letterbox(960, 540, 960, 540)
    assert (box.active_width, box.active_height) == (960, 540)
    assert (box.pad_x, box.pad_y) == (0, 0)


def test_letterbox_no_upscale_pads_small_source() -> None:
    # a small square source into the 16x9 canvas: downscale-only leaves it at
    # native size, centered with pad on all sides
    box = _compute_letterbox(480, 480, 960, 540)
    assert (box.active_width, box.active_height) == (480, 480)
    assert box.pad_x == (960 - 480) // 2 == 240
    assert box.pad_y == (540 - 480) // 2 == 30


def test_letterbox_downscale_letterboxes_wide_into_square() -> None:
    # 1920x1080 (16:9) into the square 720x720 canvas: width-limited scale → pad top/bottom
    box = _compute_letterbox(1920, 1080, 720, 720)
    assert box.active_width == 720
    assert box.active_height == _even(1080 * (720 / 1920))  # 405 -> 406 even
    assert box.pad_x == 0
    assert box.pad_y == (720 - box.active_height) // 2


def test_letterbox_dims_always_even() -> None:
    box = _compute_letterbox(1001, 563, 832, 624)
    assert box.active_width % 2 == 0
    assert box.active_height % 2 == 0


# ── _plan_encode() ───────────────────────────────────────────────────────────
def _probe(w: int, h: int, fps: float = 30.0) -> ProbeResult:
    return ProbeResult(
        width=w,
        height=h,
        nominal_frames_per_second=fps,
        average_frames_per_second=fps,
        codec="h264",
        duration=10.0,
    )


def test_plan_encode_default_16x9_bucket() -> None:
    plan = _plan_encode("in.mp4", "out.mp4", _probe(1920, 1080))
    assert plan.bucket == "16x9"
    assert (plan.canvas_width, plan.canvas_height) == (480, 270)
    assert (plan.active_width, plan.active_height) == (480, 270)
    assert (plan.pad_x, plan.pad_y) == (0, 0)


def test_plan_encode_fps_and_gop() -> None:
    plan = _plan_encode("in.mp4", "out.mp4", _probe(1920, 1080))
    assert plan.frames_per_second == 30  # default
    assert plan.group_of_pictures == 30  # round(30 * 1.0)

    config = TranscodeConfig(frames_per_second=24, group_of_pictures_in_seconds=2.0)
    plan2 = _plan_encode("in.mp4", "out.mp4", _probe(1920, 1080), config)
    assert plan2.frames_per_second == 24
    assert plan2.group_of_pictures == 48  # round(24 * 2.0)


def test_plan_encode_fps_zero_keeps_source() -> None:
    config = TranscodeConfig(frames_per_second=0, group_of_pictures_in_seconds=1.0)
    plan = _plan_encode("in.mp4", "out.mp4", _probe(1280, 720, fps=25.0), config)
    assert plan.frames_per_second == 25
    assert plan.group_of_pictures == 25


def test_plan_encode_carries_crf_preset() -> None:
    config = TranscodeConfig(constant_rate_factor=18, preset="medium")
    plan = _plan_encode("in.mp4", "out.mp4", _probe(1280, 720), config)
    assert plan.constant_rate_factor == 18
    assert plan.preset == "medium"


# ── _build_ffmpeg_command() ──────────────────────────────────────────────────
def test_build_ffmpeg_command_contains_canonical_flags() -> None:
    plan = _plan_encode("in.mp4", "out.mp4", _probe(1920, 1080))
    cmd = _build_ffmpeg_command(plan)
    joined = " ".join(cmd)

    assert "+faststart" in joined
    assert "scenecut=0:open-gop=0" in joined
    assert "-fps_mode" in cmd and cmd[cmd.index("-fps_mode") + 1] == "cfr"
    assert "-crf" in cmd and cmd[cmd.index("-crf") + 1] == str(plan.constant_rate_factor)
    assert "-g" in cmd and cmd[cmd.index("-g") + 1] == str(plan.group_of_pictures)
    assert "-keyint_min" in cmd
    assert "-profile:v" in cmd and cmd[cmd.index("-profile:v") + 1] == "high"
    assert "-pix_fmt" in cmd and cmd[cmd.index("-pix_fmt") + 1] == "yuv420p"
    # audio is stripped entirely (no audio stream in the output)
    assert "-an" in cmd
    assert "-c:a" not in cmd
    # scale + pad filter present and correct
    assert f"scale={plan.active_width}:{plan.active_height}:flags=lanczos" in joined
    assert f"pad={plan.canvas_width}:{plan.canvas_height}:{plan.pad_x}:{plan.pad_y}:color=black" in joined
    assert "setsar=1" in joined
    # input and output positions
    assert cmd[0] == "ffmpeg"
    assert cmd[-1] == "out.mp4"


def test_build_ffmpeg_command_custom_bucket() -> None:
    config = TranscodeConfig(canvases=[AspectCanvas("portrait", 540, 960)])
    plan = _plan_encode("in.mp4", "out.mp4", _probe(1080, 1920), config)
    assert plan.bucket == "portrait"
    cmd = _build_ffmpeg_command(plan)
    assert "pad=540:960:" in " ".join(cmd)


# ── _read_path_list() ────────────────────────────────────────────────────────
def test_read_path_list_skips_blanks_and_comments(tmp_path: Path) -> None:
    (tmp_path / "a.mp4").touch()
    (tmp_path / "b.mp4").touch()
    abs_path = tmp_path / "b.mp4"
    list_file = tmp_path / "clips.txt"
    list_file.write_text(f"# a comment\na.mp4\n\n   \n{abs_path}\n")
    paths = _read_path_list(list_file)
    # relative paths resolve against the list file's directory; absolute stay put
    assert paths == [tmp_path / "a.mp4", abs_path]
