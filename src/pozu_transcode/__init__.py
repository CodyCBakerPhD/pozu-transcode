"""pozu-transcode: transcode local videos into the canonical pozu space.

The implementation lives in private submodules (:mod:`pozu_transcode._core`,
:mod:`pozu_transcode._config`, :mod:`pozu_transcode._cli`). The public API is
intentionally small and mirrors the CLI commands:

- :func:`transcode`        — one file        (``pozu transcode video``)
- :func:`transcode_batch`  — a list of files (``pozu transcode batch``)
- :func:`survey`           — AR histogram    (``pozu survey``)

plus the configuration types and the dataclasses those functions accept and
return. Intermediate helpers (probing, planning, ffmpeg-command building, …)
are private to ``_core`` and not re-exported here.
"""

from ._version import __version__
from ._config import (
    DEFAULT_CANVASES,
    DEFAULT_CONFIG,
    AspectCanvas,
    TranscodeConfig,
)
from ._models import (
    EncodePlan,
    Letterbox,
    ProbeResult,
    SurveyEntry,
    TranscodeRecord,
)
from ._core import (
    survey,
    transcode,
    transcode_batch,
)

__all__ = [
    "__version__",
    # configuration
    "TranscodeConfig",
    "AspectCanvas",
    "DEFAULT_CANVASES",
    "DEFAULT_CONFIG",
    # dataclasses (accepted / returned by the public operations)
    "ProbeResult",
    "Letterbox",
    "EncodePlan",
    "TranscodeRecord",
    "SurveyEntry",
    # operations (mirror the CLI commands)
    "transcode",
    "transcode_batch",
    "survey",
]
