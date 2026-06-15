"""Filesystem helpers: input discovery, path lists, histograms, manifest I/O."""

import collections
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Iterator, List, Sequence, Union

from .._config import VIDEO_EXTENSIONS
from .._models import SurveyEntry, TranscodeRecord

PathLike = Union[str, "os.PathLike[str]"]


def _iter_videos(input_dir: PathLike) -> Iterator[Path]:
    """Yield video files under ``input_dir`` (recursive), sorted, by extension."""
    root = Path(input_dir)
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
            yield path


def _read_path_list(list_file: PathLike) -> List[Path]:
    """Read a text file of video paths (one per line).

    Blank lines and lines starting with ``#`` are ignored. Relative paths are
    resolved against the list file's own directory, so a list is portable.
    """
    path = Path(list_file)
    base = path.parent
    sources: List[Path] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = Path(line)
        sources.append(p if p.is_absolute() else base / p)
    return sources


def _aspect_histogram(entries: Sequence[SurveyEntry], precision: int = 2) -> Dict[float, int]:
    """Bin survey entries into a rounded-aspect-ratio -> count histogram."""
    hist: "collections.Counter[float]" = collections.Counter()
    for e in entries:
        hist[round(e.aspect_ratio, precision)] += 1
    return dict(sorted(hist.items()))


def _write_manifest(records: Sequence[TranscodeRecord], out_path: PathLike) -> Path:
    """Write ``records`` as a JSON array to ``out_path``. Returns the path."""
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(r) for r in records], indent=2))
    return path
