"""Transcode local videos into the canonical pozu space.

The implementation lives in private submodules (`pozu_transcode._core`,
`pozu_transcode._config`, `pozu_transcode._models`,
`pozu_transcode._cli`, `pozu_transcode._version`).

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
The configuration types (`TranscodeConfig`, `AspectCanvas`) and
the dataclasses those functions accept and return are also public. Intermediate
helpers (probing, planning, ffmpeg-command building, ...) are private to
`pozu_transcode._core` and not re-exported here.
"""

from beartype import BeartypeConf
from beartype.claw import beartype_this_package

# Runtime type-check every submodule as it is imported. `is_pep484_tower` honors
# PEP 484's numeric tower (an ``int`` satisfies a ``float`` hint), matching mypy.
beartype_this_package(conf=BeartypeConf(is_pep484_tower=True))

from ._config import (
    DEFAULT_CANVASES,
    DEFAULT_CONFIG,
    AspectCanvas,
    TranscodeConfig,
)
from ._core import (
    survey,
    transcode,
    transcode_batch,
)
from ._models import (
    EncodePlan,
    Letterbox,
    ProbeResult,
    SurveyEntry,
    TranscodeRecord,
)
from ._version import __version__

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
