"""rich-click CLI for pozu-transcode.

The ``pozu`` group nests ``transcode video``, ``transcode batch`` and
``survey``, all sharing the same set of encode/bucket options. All real work
lives in `pozu_transcode._core`; this module only defines click groups
and commands.
"""

from pathlib import Path

import rich_click as click
from rich.console import Console

from ._version import __version__
from . import _core
from ._core_helpers import _aspect_histogram
from ._cli_helpers import _config_from, _shared_options

click.rich_click.USE_RICH_MARKUP = True
click.rich_click.SHOW_ARGUMENTS = True

console = Console()


# pozu
@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="pozu")
def pozu() -> None:
    """**pozu** — tooling for the pozu pose labeler.

    Requires `ffmpeg` and `ffprobe` on your PATH.
    """


# pozu transcode
@pozu.group()
def transcode() -> None:
    """Transcode local videos into the canonical **pozu** space."""


# pozu transcode video INPUT OUTPUT
@transcode.command()
@click.argument("input", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("output", type=click.Path(dir_okay=False, path_type=Path))
@_shared_options
def video(input, output, crf, preset, gop_seconds, fps, allow_upscale, canvases):
    """Transcode a single INPUT video file to OUTPUT."""
    cfg = _config_from(crf, preset, gop_seconds, fps, allow_upscale, canvases)
    record = _core.transcode(input, output, cfg)
    console.print(
        f"[green]✓[/green] {record.src_path} → {record.out_path} "
        f"\\[{record.bucket} {record.canvas_w}x{record.canvas_h}, "
        f"{record.frame_count} frames @ {record.fps}fps]"
    )


# pozu transcode batch LIST_FILE OUTPUT_DIR
@transcode.command()
@click.argument("list_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("output_dir", type=click.Path(file_okay=False, path_type=Path))
@_shared_options
def batch(list_file, output_dir, crf, preset, gop_seconds, fps, allow_upscale, canvases):
    """Transcode the videos listed in LIST_FILE into OUTPUT_DIR + manifest.json.

    LIST_FILE is a text file with one video path per line. Blank lines and
    lines starting with `#` are ignored; relative paths resolve against the
    list file's own directory.
    """
    cfg = _config_from(crf, preset, gop_seconds, fps, allow_upscale, canvases)

    def progress(i, total, record):
        console.print(
            f"[green]✓[/green] \\[{i}/{total}] {record.video_id} "
            f"\\[{record.bucket} {record.canvas_w}x{record.canvas_h}]"
        )

    records = _core.transcode_batch(list_file, output_dir, cfg, on_progress=progress)
    manifest_path = Path(output_dir) / _core.MANIFEST_NAME
    console.print(
        f"\nWrote [cyan]{manifest_path}[/cyan] with {len(records)} entries."
    )
    if not records:
        console.print(f"[yellow]Note:[/yellow] no video paths found in {list_file}.")


# pozu survey INPUT_DIR
@pozu.command()
@click.argument("input_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@_shared_options
def survey(input_dir, crf, preset, gop_seconds, fps, allow_upscale, canvases):
    """Print a resolution + aspect-ratio histogram (no transcoding)."""
    cfg = _config_from(crf, preset, gop_seconds, fps, allow_upscale, canvases)
    entries = _core.survey(input_dir, cfg)
    if not entries:
        console.print("No videos found.")
        return
    for e in entries:
        vfr = " [yellow]VFR[/yellow]" if e.is_vfr else ""
        console.print(
            f"{e.path}: {e.width}x{e.height} AR={e.aspect_ratio:.2f} "
            f"{e.codec} {e.nominal_frames_per_second:.2f}fps → [cyan]{e.bucket}[/cyan]{vfr}"
        )
    hist = _aspect_histogram(entries)
    console.print("\n[bold]AR histogram:[/bold]")
    for ar, count in hist.items():
        console.print(f"  {ar:>5.2f}: {'#' * count} ({count})")
    console.print(f"\n{len(entries)} videos.")

