# Pozu (Transcoding)

Transcode **local** video files into the canonical, aspect-ratio–bucketed, fast-seek H.264 space used by [pozu](https://github.com/CodyCBakerPhD/pozu), a pure-web pose labeler that pulls random frames from random videos.

All labeling, training, and inference run in this one canonical space, so the transcode is a one-way trip: we never map coordinates back to the original videos.

## The canonical space

Every output is:
- **H.264 High / yuv420p**, `-movflags +faststart` (moov atom at the front for fast streaming + seeking).
- **Constant frame rate** (`-fps_mode cfr -r <fps>`, default of 30 Hz; `--fps 0` keeps the source rate but still forces CFR).
- **Closed ~1s GoP (Group of Pictures)** for fast random-frame seeks without all-intra bloat: `-g`/`-keyint_min` ≈ `fps × gop_seconds`, `scenecut=0:open-gop=0`, `-bf 2`.
- **`-crf 20`, `-preset slow`**, audio `aac @ 128k`.
- **Aspect-ratio bucketed**: each video is assigned to the nearest canvas in log-aspect-ratio space, then **uniform-scaled + letterbox-padded** into that canvas (never stretched or cropped). Downscale-only by default (no upscaling small sources unless `--allow-upscale`).

Default canvases (~0.13 megapixels each, even dims):

| name     | canvas   | aspect |
| -------- | -------- | ------ |
| `square` | 360×360  | 1.00   |
| `4x3`    | 416×312  | 1.33   |
| `16x9`   | 480×270  | 1.78   |

The video filter chain is:

```
scale=AW:AH:flags=lanczos,pad=W:H:PADX:PADY:color=black,setsar=1
```

Scaling uses **Lanczos resampling** (`flags=lanczos`): each output pixel is a weighted average of a neighborhood of source pixels via a windowed-sinc kernel. Unlike a plain box/bilinear average, the kernel's negative side-lobes preserve edge sharpness and detail when shrinking (at the cost of slight ringing near hard edges) — a good trade for small frames sampled for labeling.

## Install

Requires **`ffmpeg`** to be installed separately.

```bash
git clone https://github.com/CodyCBakerPhD/pozu-transcode
pip install -e ./pozu-transcode
```

Python 3.12+ is required.

Check ffmpeg is visible:

```bash
ffmpeg -version
```

## Usage

`pozu` is the top-level command. Transcoding lives under the `transcode` group; `survey` sits at the top level.
The encode settings are fixed (the canonical space); there are no tuning flags.

```bash
# one file
pozu transcode video  input.mp4 output.mp4

# a list of videos -> outputs + manifest.json
pozu transcode batch  clips.txt ./transcoded

# resolution + aspect-ratio histogram, no transcoding
pozu survey  ./raw_videos
```

`batch` reads `clips.txt`, a text file with **one video path per line**.
Blank lines and lines starting with `#` are ignored, and relative paths resolve against the list file's own directory:

```text
# clips.txt
/data/raw/clip01.mov
clip02.mp4
subdir/clip03.mkv
```

The encode parameters (CRF, preset, frame rate, GOP, canvases, …) are fixed to the canonical space and not exposed as CLI flags.
Library callers can still override them by passing a `TranscodeConfig` to `transcode` / `transcode_batch` / `survey` (see below).

## `manifest.json` schema

`batch` writes one record per output to `OUTPUT_DIR/manifest.json`:

```json
[
  {
    "video_id": "clip01.mp4",
    "src_path": "raw/clip01.mov",
    "out_path": "out/clip01.mp4",
    "source_width": 1920,
    "source_height": 1080,
    "frame_count": 300,
    "bucket": "16x9",
    "canvas_width": 960,
    "canvas_height": 540,
    "active_width": 960,
    "active_height": 540,
    "pad_x": 0,
    "pad_y": 0,
    "frames_per_second": 30
  }
]
```

| field                  | meaning                                            |
| ---------------------- | -------------------------------------------------- |
| `video_id`             | output filename (stable id within the manifest).   |
| `src_path` / `out_path`| source and output paths.                           |
| `source_width` / `source_height`     | original source dimensions.          |
| `frame_count`          | number of frames in the (CFR) output.              |
| `bucket`               | assigned bucket name.                              |
| `canvas_width` / `canvas_height`     | bucket canvas dimensions.            |
| `active_width` / `active_height`     | scaled (letterboxed) content dimensions. |
| `pad_x` / `pad_y`      | letterbox pad offsets inside the canvas.           |
| `frames_per_second`    | output constant frame rate.                        |

## Library API

The public API is intentionally small and mirrors the three CLI commands.
Import from the top-level `pozu_transcode` package (the submodules are private):

| function | mirrors |
| --- | --- |
| `transcode(input, output, config=None)` | `pozu transcode video` |
| `transcode_batch(list_file, output_dir, config=None)` | `pozu transcode batch` |
| `survey(input_dir, config=None)` | `pozu survey` |

```python
from pozu_transcode import TranscodeConfig, transcode, transcode_batch, survey

cfg = TranscodeConfig(constant_rate_factor=18, frames_per_second=30)

# one file -> returns a TranscodeRecord
record = transcode("clip.mov", "clip.mp4", cfg)

# a list of videos -> transcodes each and writes out/manifest.json itself
records = transcode_batch("clips.txt", "out/", cfg)

# inspect a directory without transcoding -> list[SurveyEntry]
for entry in survey("raw/", cfg):
    print(entry.path, entry.bucket, entry.has_variable_frame_rate)
```

The configuration types (`TranscodeConfig`, `AspectCanvas`, `DEFAULT_CANVASES`) and the result dataclasses (`ProbeResult`, `Letterbox`, `EncodePlan`, `TranscodeRecord`, `SurveyEntry`) are public; the intermediate helpers (probing, planning, ffmpeg command building, ...) are private to `pozu_transcode._core`.

## Development

```bash
pip install -e . --group test   # pip >= 25.1, or: uv sync --group test
pytest
```

The unit tests cover geometry (`even`, `pick_bucket`, `compute_letterbox`),
planning (`plan_encode`), ffmpeg command construction, and path-list parsing
(`read_path_list`) — and run **without ffmpeg installed**.
