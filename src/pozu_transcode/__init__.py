"""pozu-transcode: transcode local videos into the canonical pozu space.

The public API lives in :mod:`pozu_transcode.core` (framework-agnostic) and is
configured via :mod:`pozu_transcode.config`.
"""

from .config import (
    DEFAULT_BUCKETS,
    Bucket,
    TranscodeConfig,
)
from .core import (
    EncodePlan,
    Letterbox,
    ProbeResult,
    SurveyEntry,
    TranscodeRecord,
    aspect_histogram,
    build_ffmpeg_command,
    compute_letterbox,
    even,
    iter_videos,
    pick_bucket,
    plan_encode,
    probe,
    survey,
    transcode,
    transcode_batch,
    write_manifest,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "Bucket",
    "TranscodeConfig",
    "DEFAULT_BUCKETS",
    "ProbeResult",
    "Letterbox",
    "EncodePlan",
    "TranscodeRecord",
    "SurveyEntry",
    "even",
    "pick_bucket",
    "compute_letterbox",
    "probe",
    "plan_encode",
    "build_ffmpeg_command",
    "transcode",
    "transcode_batch",
    "iter_videos",
    "survey",
    "aspect_histogram",
    "write_manifest",
]
