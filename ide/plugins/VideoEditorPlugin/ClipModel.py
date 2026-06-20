"""
ClipModel — Pure data layer for the Video Editor.

No Qt dependencies. Everything here is serialisable to JSON
for project save/load.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import uuid
import json
from pathlib import Path


# ---------------------------------------------------------------------------
# Enums / constants
# ---------------------------------------------------------------------------

class TrackType:
    VIDEO = "video"
    AUDIO = "audio"


class ClipType:
    VIDEO = "video"   # has video stream (may also have audio)
    AUDIO = "audio"   # audio-only
    IMAGE = "image"   # static image / PNG / JPG


# ---------------------------------------------------------------------------
# MediaInfo  — populated by FFmpegWorker.probe()
# ---------------------------------------------------------------------------

@dataclass
class MediaInfo:
    path:       str      = ""
    clip_type:  str      = ClipType.VIDEO
    duration:   float    = 0.0      # seconds
    width:      int      = 0
    height:     int      = 0
    fps:        float    = 0.0
    codec:      str      = ""
    audio_codec:str      = ""
    file_size:  int      = 0        # bytes
    thumbnail:  Optional[str] = None  # path to extracted thumbnail PNG

    @property
    def resolution(self) -> str:
        if self.width and self.height:
            return f"{self.width}×{self.height}"
        return "—"

    @property
    def duration_tc(self) -> str:
        """Return HH:MM:SS.ms timecode string."""
        return seconds_to_tc(self.duration)

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "MediaInfo":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Clip  — a segment placed on the timeline
# ---------------------------------------------------------------------------

@dataclass
class Clip:
    clip_id:          str   = field(default_factory=lambda: str(uuid.uuid4())[:8])
    source_path:      str   = ""
    clip_type:        str   = ClipType.VIDEO
    track_index:      int   = 0        # 0 = V1, 1 = V2 … (audio tracks share index space)
    track_type:       str   = TrackType.VIDEO

    # Source in/out in seconds (slice of the source file)
    in_point:         float = 0.0
    out_point:        float = 0.0      # must be set to actual duration — never leave as 0

    # Total source duration stored explicitly (used as fallback)
    media_duration:   float = 0.0

    # Position on the timeline (seconds from t=0)
    timeline_position: float = 0.0

    # Display
    label:            str   = ""
    color:            str   = "#4A90D9"   # hex colour for the timeline block

    @property
    def source_duration(self) -> float:
        """Duration of this clip's used segment."""
        if self.out_point > self.in_point:
            return self.out_point - self.in_point
        # Fallback: use stored media duration minus in_point
        if self.media_duration > 0:
            return self.media_duration - self.in_point
        return 0.0

    @property
    def timeline_end(self) -> float:
        return self.timeline_position + self.source_duration

    @property
    def display_name(self) -> str:
        return self.label or Path(self.source_path).name

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "Clip":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Track  — a named row on the timeline
# ---------------------------------------------------------------------------

@dataclass
class Track:
    track_id:   str  = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name:       str  = "Track"
    track_type: str  = TrackType.VIDEO
    muted:      bool = False
    locked:     bool = False

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "Track":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Project  — top-level container
# ---------------------------------------------------------------------------

@dataclass
class Project:
    name:        str          = "Untitled Project"
    output_dir:  str          = ""
    width:       int          = 1920
    height:      int          = 1080
    fps:         float        = 25.0
    tracks:      list[Track]  = field(default_factory=list)
    clips:       list[Clip]   = field(default_factory=list)
    media_bin:   list[str]    = field(default_factory=list)   # source file paths

    def __post_init__(self):
        if not self.tracks:
            self.tracks = [
                Track(name="V1", track_type=TrackType.VIDEO),
                Track(name="A1", track_type=TrackType.AUDIO),
            ]

    # --- clip management ---

    def add_clip(self, clip: Clip):
        self.clips.append(clip)

    def remove_clip(self, clip_id: str):
        self.clips = [c for c in self.clips if c.clip_id != clip_id]

    def get_clip(self, clip_id: str) -> Optional[Clip]:
        for c in self.clips:
            if c.clip_id == clip_id:
                return c
        return None

    def clips_on_track(self, track_index: int, track_type: str) -> list[Clip]:
        return [c for c in self.clips
                if c.track_index == track_index and c.track_type == track_type]

    @property
    def duration(self) -> float:
        """Total timeline duration — end of last clip."""
        if not self.clips:
            return 0.0
        return max(c.timeline_end for c in self.clips)

    @property
    def duration_tc(self) -> str:
        return seconds_to_tc(self.duration)

    # --- media bin ---

    def add_to_bin(self, path: str):
        if path not in self.media_bin:
            self.media_bin.append(path)

    # --- serialisation ---

    def to_dict(self) -> dict:
        return {
            "name":       self.name,
            "output_dir": self.output_dir,
            "width":      self.width,
            "height":     self.height,
            "fps":        self.fps,
            "tracks":     [t.to_dict() for t in self.tracks],
            "clips":      [c.to_dict() for c in self.clips],
            "media_bin":  self.media_bin,
        }

    def save(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str) -> "Project":
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        proj = cls(
            name=d.get("name", "Untitled"),
            output_dir=d.get("output_dir", ""),
            width=d.get("width", 1920),
            height=d.get("height", 1080),
            fps=d.get("fps", 25.0),
            media_bin=d.get("media_bin", []),
        )
        proj.tracks = [Track.from_dict(t) for t in d.get("tracks", [])]
        proj.clips  = [Clip.from_dict(c)  for c in d.get("clips",  [])]
        return proj


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def seconds_to_tc(seconds: float) -> str:
    """Convert float seconds → HH:MM:SS.mm display string."""
    if seconds < 0:
        seconds = 0.0
    h  = int(seconds // 3600)
    m  = int((seconds % 3600) // 60)
    s  = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 100)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:02d}"


def tc_to_seconds(tc: str) -> float:
    """Parse HH:MM:SS.ms → float seconds."""
    try:
        parts = tc.replace(",", ".").split(":")
        if len(parts) == 3:
            h, m, rest = parts
            return int(h) * 3600 + int(m) * 60 + float(rest)
        elif len(parts) == 2:
            m, rest = parts
            return int(m) * 60 + float(rest)
        return float(tc)
    except (ValueError, IndexError):
        return 0.0


# Colour palette for auto-assigning clip colours
CLIP_COLOURS = [
    "#4A90D9",  # blue
    "#7B68EE",  # medium slate blue
    "#50C878",  # emerald
    "#FF7F50",  # coral
    "#FFD700",  # gold
    "#DA70D6",  # orchid
    "#40E0D0",  # turquoise
    "#FF6B6B",  # light red
]

_colour_index = 0

def next_clip_colour() -> str:
    global _colour_index
    colour = CLIP_COLOURS[_colour_index % len(CLIP_COLOURS)]
    _colour_index += 1
    return colour