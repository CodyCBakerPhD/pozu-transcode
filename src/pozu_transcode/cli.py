"""rich-click CLI for pozu-transcode.

Three commands (``single``, ``batch``, ``survey``) share the same set of
encode/bucket options. All real work lives in :mod:`pozu_transcode.core`; this
module only parses options and prints.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import rich_click as click
from rich.console import Console

from . import __version__
from .config import (
    DEFAULT_ALLOW_UPSCALE,
    DEFAULT_BUCKETS,
    DEFAULT_CRF,
    DEFAULT_FPS,
    DEFAULT_GOP_SECONDS,
    DEFAULT_PRESET,
    Bucket,
    TranscodeConfig,
)
from . import core

click.rich_click.USE_RICH_MARKUP = True
click.rich_click.SHOW_ARGUMENTS = True

console = Console()


def _parse_buckets(values: Tuple[str, ...]) -> Optional[List[Bucket]]:
    """Parse repeatable ``NAME:WxH`` strings into a bucket list (or None)."""
    if not values:
        return None
    buckets: List[Bucket] = []
    for raw in values:
        try:
            name, dims = raw.split(":", 1)
            w_str, h_str = dims.lower().split("x", 1)
            buckets.append(Bucket(name=name, width=int(w_str), height=int(h_str)))
        except ValueError:
            raise click.BadParameter(
                f"{raw!r} is not in NAME:WxH form (e.g. 16x9:960x540)",
                param_hint="--bucket",
            )
    return buckets


def shared_options(func):
    """Attach the encode/bucket options shared by every command."""
    options = [
        click.option("--crf", type=int, default=DEFAULT_CRF, show_default=True,
                     help="x264 constant rate factor (lower = higher quality)."),
        click.option("--preset", default=DEFAULT_PRESET, show_default=True,
                     help="x264 preset (e.g. slow, medium, fast)."),
        click.option("--gop-seconds", type=float, default=DEFAULT_GOP_SECONDS,
                     show_default=True,
                     help="Keyframe interval in seconds (closed GOP)."),
        click.option("--fps", type=int, default=DEFAULT_FPS, show_default=True,
                     help="Force CFR to this fps; 0 keeps source fps (still CFR)."),
        click.option("--allow-upscale/--no-upscale", default=DEFAULT_ALLOW_UPSCALE,
                     show_default=True,
                     help="Allow upscaling sources smaller than the canvas."),
        click.option("--bucket", "buckets", multiple=True, metavar="NAME:WxH",
                     help="Override aspect buckets (repeatable). "
                          "Default: sq:720x720 4x3:832x624 16x9:960x540."),
    ]
    for option in reversed(options):
        func = option(func)
    return func


def _config_from(crf, preset, gop_seconds, fps, allow_upscale, buckets) -> TranscodeConfig:
    parsed = _parse_buckets(buckets)
    cfg = TranscodeConfig(
        crf=crf,
        preset=preset,
        gop_seconds=gop_seconds,
        fps=fps,
        allow_upscale=allow_upscale,
    )
    if parsed is not None:
        cfg.buckets = parsed
    return cfg


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="pozu")
def pozu() -> None:
    """**pozu** — tooling for the pozu pose labeler.

    Requires `ffmpeg` and `ffprobe` on your PATH.
    """


@pozu.group()
def transcode() -> None:
    """Transcode local videos into the canonical **pozu** space."""


@transcode.command()
@click.argument("input", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("output", type=click.Path(dir_okay=False, path_type=Path))
@shared_options
def video(input, output, crf, preset, gop_seconds, fps, allow_upscale, buckets):
    """Transcode a single INPUT video file to OUTPUT."""
    cfg = _config_from(crf, preset, gop_seconds, fps, allow_upscale, buckets)
    record = core.transcode(input, output, cfg)
    console.print(
        f"[green]✓[/green] {record.src_path} → {record.out_path} "
        f"\\[{record.bucket} {record.canvas_w}x{record.canvas_h}, "
        f"{record.frame_count} frames @ {record.fps}fps]"
    )


@transcode.command()
@click.argument("list_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("output_dir", type=click.Path(file_okay=False, path_type=Path))
@shared_options
def batch(list_file, output_dir, crf, preset, gop_seconds, fps, allow_upscale, buckets):
    """Transcode the videos listed in LIST_FILE into OUTPUT_DIR + manifest.json.

    LIST_FILE is a text file with one video path per line. Blank lines and
    lines starting with `#` are ignored; relative paths resolve against the
    list file's own directory.
    """
    cfg = _config_from(crf, preset, gop_seconds, fps, allow_upscale, buckets)
    sources = core.read_path_list(list_file)
    if not sources:
        console.print(f"No video paths found in {list_file}.")
        return

    def progress(i, total, record):
        console.print(
            f"[green]✓[/green] \\[{i}/{total}] {record.video_id} "
            f"\\[{record.bucket} {record.canvas_w}x{record.canvas_h}]"
        )

    records = core.transcode_batch(sources, output_dir, cfg, on_progress=progress)
    manifest_path = core.write_manifest(records, Path(output_dir) / "manifest.json")
    console.print(
        f"\nWrote [cyan]{manifest_path}[/cyan] with {len(records)} entries."
    )


@pozu.command()
@click.argument("input_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@shared_options
def survey(input_dir, crf, preset, gop_seconds, fps, allow_upscale, buckets):
    """Print a resolution + aspect-ratio histogram (no transcoding)."""
    cfg = _config_from(crf, preset, gop_seconds, fps, allow_upscale, buckets)
    entries = core.survey(input_dir, cfg)
    if not entries:
        console.print("No videos found.")
        return
    for e in entries:
        vfr = " [yellow]VFR[/yellow]" if e.is_vfr else ""
        console.print(
            f"{e.path}: {e.width}x{e.height} AR={e.aspect_ratio:.2f} "
            f"{e.codec} {e.fps_r:.2f}fps → [cyan]{e.bucket}[/cyan]{vfr}"
        )
    hist = core.aspect_histogram(entries)
    console.print("\n[bold]AR histogram:[/bold]")
    for ar, count in hist.items():
        console.print(f"  {ar:>5.2f}: {'#' * count} ({count})")
    console.print(f"\n{len(entries)} videos.")


if __name__ == "__main__":
    pozu()
