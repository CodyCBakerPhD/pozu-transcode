"""Transcode local videos into the canonical pozu space.

The implementation lives in private submodules (:mod:`pozu_transcode._core`,
:mod:`pozu_transcode._config`, :mod:`pozu_transcode._models`,
:mod:`pozu_transcode._cli`, :mod:`pozu_transcode._version`). The public API is
intentionally small and mirrors the CLI commands.

Routines
--------
transcode
    Transcode one file (``pozu transcode video``).
transcode_batch
    Transcode a list of files (``pozu transcode batch``).
survey
    Resolution + aspect-ratio histogram (``pozu survey``).

Notes
-----
The configuration types (:class:`TranscodeConfig`, :class:`AspectCanvas`) and
the dataclasses those functions accept and return are also public. Intermediate
helpers (probing, planning, ffmpeg-command building, …) are private to
:mod:`pozu_transcode._core` and not re-exported here.
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
