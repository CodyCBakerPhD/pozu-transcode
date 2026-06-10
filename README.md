# pozu-transcode

Transcode **local** videos into the canonical, aspect-ratio–bucketed,
fast-seek H.264 space used by [pozu](https://github.com/CodyCBakerPhD), a
pure-web pose labeler that pulls random frames from random videos.

All labeling, training, and inference run in this one canonical space, so the
transcode is a one-way trip: we never map coordinates back to the original
videos. This tool works on local files only — there is no S3 / cloud step.

## The canonical space

Every output is:

- **H.264 High / yuv420p**, `-movflags +faststart` (moov atom at the front for
  fast streaming + seeking).
- **Constant frame rate** (`-fps_mode cfr -r <fps>`, default 30; `--fps 0`
  keeps the source rate but still forces CFR).
- **Closed ~1s GOP** for fast random-frame seeks without all-intra bloat:
  `-g`/`-keyint_min` ≈ `fps × gop_seconds`, `scenecut=0:open-gop=0`, `-bf 2`.
- **`-crf 20`, `-preset slow`**, audio `aac @ 128k`.
- **Aspect-ratio bucketed**: each video is assigned to the nearest canvas in
  log-aspect-ratio space, then **uniform-scaled + letterbox-padded** into that
  canvas — never stretched, never cropped. Downscale-only by default (no
  upscaling small sources unless `--allow-upscale`).

Default buckets (~0.52 MP each, even dims — tune to your corpus):

| name   | canvas   | aspect |
| ------ | -------- | ------ |
| `sq`   | 720×720  | 1.00   |
| `4x3`  | 832×624  | 1.33   |
| `16x9` | 960×540  | 1.78   |

The video filter chain is:

```
scale=AW:AH:flags=lanczos,pad=W:H:PADX:PADY:color=black,setsar=1
```

## Install

Requires **`ffmpeg` and `ffprobe` on your `PATH`** (they are external binaries,
not pip dependencies).

```bash
pip install -e .          # or: pip install pozu-transcode
pip install -e ".[test]"  # with the test extra
```

Check ffmpeg is visible:

```bash
ffmpeg -version
```

## Usage

Three commands share the same encode/bucket options:

```bash
# one file
pozu-transcode single  input.mp4 output.mp4

# a directory -> outputs + manifest.json
pozu-transcode batch   ./raw_videos ./transcoded

# resolution + aspect-ratio histogram, no transcoding
pozu-transcode survey  ./raw_videos
```

### Options

| option                          | default                              | meaning                                                  |
| ------------------------------- | ------------------------------------ | -------------------------------------------------------- |
| `--crf`                         | `20`                                 | x264 constant rate factor (lower = higher quality).      |
| `--preset`                      | `slow`                               | x264 preset (`slow`, `medium`, `fast`, …).               |
| `--gop-seconds`                 | `1.0`                                | Keyframe interval in seconds (closed GOP).               |
| `--fps`                         | `30`                                 | Force CFR to this fps; `0` keeps source fps (still CFR). |
| `--allow-upscale/--no-upscale`  | `--no-upscale`                       | Allow upscaling sources smaller than the canvas.         |
| `--bucket NAME:WxH`             | `sq:720x720 4x3:832x624 16x9:960x540`| Override aspect buckets (repeatable).                    |

Example with custom buckets and a higher-quality CRF:

```bash
pozu-transcode batch ./raw ./out \
  --crf 18 --fps 25 \
  --bucket sq:768x768 --bucket 16x9:1024x576
```

## `manifest.json` schema

`batch` writes one record per output to `OUTPUT_DIR/manifest.json`:

```json
[
  {
    "video_id": "clip01.mp4",
    "src_path": "raw/clip01.mov",
    "out_path": "out/clip01.mp4",
    "src_w": 1920,
    "src_h": 1080,
    "frame_count": 300,
    "bucket": "16x9",
    "canvas_w": 960,
    "canvas_h": 540,
    "active_w": 960,
    "active_h": 540,
    "pad_x": 0,
    "pad_y": 0,
    "fps": 30
  }
]
```

| field                  | meaning                                            |
| ---------------------- | -------------------------------------------------- |
| `video_id`             | output filename (stable id within the manifest).   |
| `src_path` / `out_path`| source and output paths.                           |
| `src_w` / `src_h`      | original source dimensions.                        |
| `frame_count`          | number of frames in the (CFR) output.              |
| `bucket`               | assigned bucket name.                              |
| `canvas_w` / `canvas_h`| bucket canvas dimensions.                          |
| `active_w` / `active_h`| scaled (letterboxed) content dimensions.           |
| `pad_x` / `pad_y`      | letterbox pad offsets inside the canvas.           |
| `fps`                  | output constant frame rate.                        |

## Library API

The core (`pozu_transcode.core`) is framework-agnostic — paths in, dataclasses
out — and is shared by every CLI command:

```python
from pozu_transcode import (
    TranscodeConfig, probe, plan_encode, build_ffmpeg_command,
    transcode, transcode_batch, survey, write_manifest,
)

cfg = TranscodeConfig(crf=18, fps=30)

# inspect without encoding
info = probe("clip.mov")
plan = plan_encode("clip.mov", "clip.mp4", info, cfg)
print(plan.bucket, plan.canvas_w, plan.canvas_h)
print(build_ffmpeg_command(plan))   # the exact ffmpeg argv

# encode one file
record = transcode("clip.mov", "clip.mp4", cfg)

# encode a directory and write a manifest
records = transcode_batch("raw/", "out/", cfg)
write_manifest(records, "out/manifest.json")
```

## Development

```bash
pip install -e ".[test]"
pytest
```

The unit tests cover geometry (`even`, `pick_bucket`, `compute_letterbox`),
planning (`plan_encode`), and ffmpeg command construction — and run **without
ffmpeg installed**.
