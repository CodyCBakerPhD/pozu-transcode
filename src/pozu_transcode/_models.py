"""Result dataclasses produced by the core transcode operations.

These are the data structures that flow between the private helpers in
:mod:`pozu_transcode._core` and are returned to callers of the public API.
"""

from dataclasses import dataclass


@dataclass
class ProbeResult:
    """What ffprobe tells us about a source video's first video stream.

    Attributes:
        width: Pixel width of the video stream.
        height: Pixel height of the video stream.
        fps_r: Nominal frame rate as reported by ``r_frame_rate``.
        fps_avg: Actual average frame rate as reported by ``avg_frame_rate``.
        codec: Codec name (e.g. ``"h264"``).
        duration: Container duration in seconds.
    """

    width: int
    height: int
    fps_r: float
    fps_avg: float
    codec: str
    duration: float

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height

    @property
    def is_vfr(self) -> bool:
        return abs(self.fps_r - self.fps_avg) > 0.01


@dataclass
class Letterbox:
    """Active (scaled) dimensions plus the pad offsets inside a canvas.

    Attributes:
        active_w: Width of the scaled source region inside the canvas.
        active_h: Height of the scaled source region inside the canvas.
        pad_x: Horizontal padding added on each side (left/right).
        pad_y: Vertical padding added on each side (top/bottom).
    """

    active_w: int
    active_h: int
    pad_x: int
    pad_y: int


@dataclass
class EncodePlan:
    """A fully-resolved plan for one transcode — enough to build the ffmpeg command.

    Attributes:
        src_path: Absolute or relative path to the source video file.
        out_path: Absolute or relative path for the encoded output file.
        src_w: Source video width in pixels.
        src_h: Source video height in pixels.
        bucket: Name of the chosen :class:`~pozu_transcode.AspectCanvas`.
        canvas_w: Total output canvas width in pixels.
        canvas_h: Total output canvas height in pixels.
        active_w: Scaled source width within the canvas (before padding).
        active_h: Scaled source height within the canvas (before padding).
        pad_x: Horizontal offset of the active region within the canvas.
        pad_y: Vertical offset of the active region within the canvas.
        fps: Target constant frame rate.
        gop: GOP size in frames (``fps × gop_seconds``).
        crf: x264 constant rate factor.
        preset: x264 encoding speed preset.
        audio_bitrate: AAC audio encode bitrate (e.g. ``"128k"``).
    """

    src_path: str
    out_path: str
    src_w: int
    src_h: int
    bucket: str
    canvas_w: int
    canvas_h: int
    active_w: int
    active_h: int
    pad_x: int
    pad_y: int
    fps: int
    gop: int
    crf: int
    preset: str
    audio_bitrate: str


@dataclass
class TranscodeRecord:
    """One manifest entry: everything needed to locate and reason about an output.

    Attributes:
        video_id: Output filename used as a unique identifier.
        src_path: Path to the original source file.
        out_path: Path to the transcoded output file.
        src_w: Source video width in pixels.
        src_h: Source video height in pixels.
        frame_count: Total number of frames in the output.
        bucket: Name of the :class:`~pozu_transcode.AspectCanvas` used.
        canvas_w: Total output canvas width in pixels.
        canvas_h: Total output canvas height in pixels.
        active_w: Scaled source width within the canvas (before padding).
        active_h: Scaled source height within the canvas (before padding).
        pad_x: Horizontal offset of the active region within the canvas.
        pad_y: Vertical offset of the active region within the canvas.
        fps: Constant frame rate of the output.
    """

    video_id: str
    src_path: str
    out_path: str
    src_w: int
    src_h: int
    frame_count: int
    bucket: str
    canvas_w: int
    canvas_h: int
    active_w: int
    active_h: int
    pad_x: int
    pad_y: int
    fps: int


@dataclass
class SurveyEntry:
    """One source video's geometry and assigned canvas (no transcoding).

    Attributes:
        path: Path to the source video file.
        width: Source video width in pixels.
        height: Source video height in pixels.
        aspect_ratio: Width-to-height ratio of the source video.
        codec: Codec name reported by ffprobe (e.g. ``"h264"``).
        fps_r: Nominal frame rate as reported by ``r_frame_rate``.
        is_vfr: ``True`` if the source has variable frame rate.
        bucket: Name of the nearest :class:`~pozu_transcode.AspectCanvas`.
    """

    path: str
    width: int
    height: int
    aspect_ratio: float
    codec: str
    fps_r: float
    is_vfr: bool
    bucket: str
