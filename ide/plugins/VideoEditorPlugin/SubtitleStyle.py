"""
SubtitleStyle — shared dataclass describing subtitle appearance.

Used by SubtitleStyleDialog (editor UI), PreviewWidget (live QGraphicsScene
rendering), and SubtitleBurnWorker (FFmpeg ASS export).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Tuple


# Position presets — (drawtext x expr, drawtext y expr)
POSITION_PRESETS = {
    "Bottom Centre":  ("(w-text_w)/2",          "h-text_h-40"),
    "Bottom Left":    ("40",                     "h-text_h-40"),
    "Bottom Right":   ("w-text_w-40",            "h-text_h-40"),
    "Top Centre":     ("(w-text_w)/2",           "40"),
    "Top Left":       ("40",                     "40"),
    "Top Right":      ("w-text_w-40",            "40"),
    "Centre":         ("(w-text_w)/2",           "(h-text_h)/2"),
}

FONT_SIZES   = [18, 22, 26, 30, 36, 42, 48, 56, 64, 72]
FONT_WEIGHTS = ["Normal", "Bold"]


@dataclass
class SubtitleStyle:
    # Text
    font_size:   int   = 22
    font_weight: str   = "Bold"      # "Normal" | "Bold"
    font_family: str   = "Arial"

    # Colours  — (R, G, B, A)  A 0–255
    text_color:    Tuple[int, int, int, int] = (255, 255, 255, 255)   # white
    outline_color: Tuple[int, int, int, int] = (0,   0,   0,   255)   # black
    bg_color:      Tuple[int, int, int, int] = (0,   0,   0,   140)   # semi-transparent black

    # Layout
    outline_width: int  = 2      # 0 = no outline
    bg_enabled:    bool = False
    position:      str  = "Bottom Centre"
    margin:        int  = 40     # pixels from edge (overridden by drawtext exprs)

    def text_color_hex(self) -> str:
        r, g, b, _ = self.text_color
        return f"#{r:02X}{g:02X}{b:02X}"

    def outline_color_hex(self) -> str:
        r, g, b, _ = self.outline_color
        return f"#{r:02X}{g:02X}{b:02X}"

    def bg_color_qt_rgba(self) -> str:
        """Qt stylesheet rgba() string."""
        r, g, b, a = self.bg_color
        return f"rgba({r},{g},{b},{a})"

    def ffmpeg_fontcolor(self) -> str:
        """FFmpeg colour string including alpha: 0xRRGGBBAA"""
        r, g, b, a = self.text_color
        return f"0x{r:02X}{g:02X}{b:02X}{a:02X}"

    def ffmpeg_bordercolor(self) -> str:
        r, g, b, a = self.outline_color
        return f"0x{r:02X}{g:02X}{b:02X}{a:02X}"

    def ffmpeg_boxcolor(self) -> str:
        r, g, b, a = self.bg_color
        return f"0x{r:02X}{g:02X}{b:02X}{a:02X}"

    def ffmpeg_x(self) -> str:
        return POSITION_PRESETS.get(self.position, POSITION_PRESETS["Bottom Centre"])[0]

    def ffmpeg_y(self) -> str:
        return POSITION_PRESETS.get(self.position, POSITION_PRESETS["Bottom Centre"])[1]