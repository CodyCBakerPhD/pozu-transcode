"""Result dataclasses produced by the core transcode operations.

These are the data structures that flow between the private helpers in
`pozu_transcode._core` and are returned to callers of the public API.
"""

from dataclasses import dataclass


@dataclass
class ProbeResult:
    """What ffprobe tells us about a source video's first video stream.

    Attributes
    ----------
    width : int
        Pixel width of the video stream.
    height : int
        Pixel height of the video stream.
    nominal_frames_per_second : float
        Nominal frame rate as reported by ffprobe's ``r_frame_rate`` (the
        lowest rate that can exactly represent every frame's timestamp).
    average_frames_per_second : float
        Actual average frame rate as reported by ffprobe's ``avg_frame_rate``.
    codec : str
        Codec name (e.g. ``"h264"``).
    duration : float
        Container duration in seconds.
    """

    width: int
    height: int
    nominal_frames_per_second: float
    average_frames_per_second: float
    codec: str
    duration: float

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height

    @property
    def has_variable_frame_rate(self) -> bool:
        return abs(self.nominal_frames_per_second - self.average_frames_per_second) > 0.01


@dataclass
class Letterbox:
    """Active (scaled) dimensions plus the pad offsets inside a canvas.

    Attributes
    ----------
    active_width : int
        Width of the scaled source region inside the canvas.
    active_height : int
        Height of the scaled source region inside the canvas.
    pad_x : int
        Horizontal padding added on each side (left/right).
    pad_y : int
        Vertical padding added on each side (top/bottom).
    """

    active_width: int
    active_height: int
    pad_x: int
    pad_y: int


@dataclass
class EncodePlan:
    """A fully-resolved plan for one transcode — enough to build the ffmpeg command.

    Attributes
    ----------
    src_path : str
        Absolute or relative path to the source video file.
    out_path : str
        Absolute or relative path for the encoded output file.
    source_width : int
        Source video width in pixels.
    source_height : int
        Source video height in pixels.
    bucket : str
        Name of the chosen `AspectCanvas`.
    canvas_width : int
        Total output canvas width in pixels.
    canvas_height : int
        Total output canvas height in pixels.
    active_width : int
        Scaled source width within the canvas (before padding).
    active_height : int
        Scaled source height within the canvas (before padding).
    pad_x : int
        Horizontal offset of the active region within the canvas.
    pad_y : int
        Vertical offset of the active region within the canvas.
    frames_per_second : int
        Target constant frame rate.
    group_of_pictures : int
        GOP size in frames (``frames_per_second × group_of_pictures_in_seconds``).
    constant_rate_factor : int
        x264 constant rate factor.
    preset : str
        x264 encoding speed preset.
    audio_bitrate : str
        AAC audio encode bitrate (e.g. ``"128k"``).
    """

    src_path: str
    out_path: str
    source_width: int
    source_height: int
    bucket: str
    canvas_width: int
    canvas_height: int
    active_width: int
    active_height: int
    pad_x: int
    pad_y: int
    frames_per_second: int
    group_of_pictures: int
    constant_rate_factor: int
    preset: str
    audio_bitrate: str


@dataclass
class TranscodeRecord:
    """One manifest entry: everything needed to locate and reason about an output.

    Attributes
    ----------
    video_id : str
        Output filename used as a unique identifier.
    src_path : str
        Path to the original source file.
    out_path : str
        Path to the transcoded output file.
    source_width : int
        Source video width in pixels.
    source_height : int
        Source video height in pixels.
    frame_count : int
        Total number of frames in the output.
    bucket : str
        Name of the `AspectCanvas` used.
    canvas_width : int
        Total output canvas width in pixels.
    canvas_height : int
        Total output canvas height in pixels.
    active_width : int
        Scaled source width within the canvas (before padding).
    active_height : int
        Scaled source height within the canvas (before padding).
    pad_x : int
        Horizontal offset of the active region within the canvas.
    pad_y : int
        Vertical offset of the active region within the canvas.
    frames_per_second : int
        Constant frame rate of the output.
    """

    video_id: str
    src_path: str
    out_path: str
    source_width: int
    source_height: int
    frame_count: int
    bucket: str
    canvas_width: int
    canvas_height: int
    active_width: int
    active_height: int
    pad_x: int
    pad_y: int
    frames_per_second: int


@dataclass
class SurveyEntry:
    """One source video's geometry and assigned canvas (no transcoding).

    Attributes
    ----------
    path : str
        Path to the source video file.
    width : int
        Source video width in pixels.
    height : int
        Source video height in pixels.
    aspect_ratio : float
        Width-to-height ratio of the source video.
    codec : str
        Codec name reported by ffprobe (e.g. ``"h264"``).
    nominal_frames_per_second : float
        Nominal frame rate as reported by ffprobe's ``r_frame_rate``.
    has_variable_frame_rate : bool
        ``True`` if the source has variable frame rate.
    bucket : str
        Name of the nearest `AspectCanvas`.
    """

    path: str
    width: int
    height: int
    aspect_ratio: float
    codec: str
    nominal_frames_per_second: float
    has_variable_frame_rate: bool
    bucket: str
