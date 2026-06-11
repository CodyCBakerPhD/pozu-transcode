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
pip install -e .                   # or: pip install pozu-transcode
pip install -e . --group test      # with the test dependency group (pip >= 25.1)
```

Python 3.12+ is required.

Check ffmpeg is visible:

```bash
ffmpeg -version
```

## Usage

`pozu` is the top-level command. Transcoding lives under the `transcode`
group; `survey` sits at the top level. They all share the same encode/bucket
options.

```bash
# one file
pozu transcode video  input.mp4 output.mp4

# a list of videos -> outputs + manifest.json
pozu transcode batch  clips.txt ./transcoded

# resolution + aspect-ratio histogram, no transcoding
pozu survey  ./raw_videos
```

`batch` reads `clips.txt`, a text file with **one video path per line**. Blank
lines and lines starting with `#` are ignored, and relative paths resolve
against the list file's own directory:

```text
# clips.txt
/data/raw/clip01.mov
clip02.mp4
subdir/clip03.mkv
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
pozu transcode batch clips.txt ./out \
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

The public API is intentionally small and mirrors the three CLI commands. Import
from the top-level `pozu_transcode` package (the submodules are private):

| function | mirrors |
| --- | --- |
| `transcode(input, output, config=None)` | `pozu transcode video` |
| `transcode_batch(list_file, output_dir, config=None)` | `pozu transcode batch` |
| `survey(input_dir, config=None)` | `pozu survey` |

```python
from pozu_transcode import TranscodeConfig, transcode, transcode_batch, survey

cfg = TranscodeConfig(crf=18, fps=30)

# one file -> returns a TranscodeRecord
record = transcode("clip.mov", "clip.mp4", cfg)

# a list of videos -> transcodes each and writes out/manifest.json itself
records = transcode_batch("clips.txt", "out/", cfg)

# inspect a directory without transcoding -> list[SurveyEntry]
for entry in survey("raw/", cfg):
    print(entry.path, entry.bucket, entry.is_vfr)
```

The configuration types (`TranscodeConfig`, `Bucket`, `DEFAULT_BUCKETS`) and the
result dataclasses (`ProbeResult`, `Letterbox`, `EncodePlan`, `TranscodeRecord`,
`SurveyEntry`) are public; the intermediate helpers (probing, planning, ffmpeg
command building, …) are private to `pozu_transcode._core`.

## Development

```bash
pip install -e . --group test   # pip >= 25.1, or: uv sync --group test
pytest
```

The unit tests cover geometry (`even`, `pick_bucket`, `compute_letterbox`),
planning (`plan_encode`), ffmpeg command construction, and path-list parsing
(`read_path_list`) — and run **without ffmpeg installed**.
