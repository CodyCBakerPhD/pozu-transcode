"""pozu-transcode: transcode local videos into the canonical pozu space.

The implementation lives in private submodules (:mod:`pozu_transcode._core`,
:mod:`pozu_transcode._config`, :mod:`pozu_transcode._cli`); the public API is
everything re-exported here.
"""

from ._config import (
    DEFAULT_BUCKETS,
    Bucket,
    TranscodeConfig,
)
from ._core import (
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
    read_path_list,
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
    "read_path_list",
    "survey",
    "aspect_histogram",
    "write_manifest",
]
