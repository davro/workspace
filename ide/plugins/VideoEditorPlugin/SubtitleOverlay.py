"""
SubtitleOverlay — transparent QWidget that sits on top of QVideoWidget
and renders the active subtitle segment during preview playback.

Usage
-----
    overlay = SubtitleOverlay(parent=video_widget)
    overlay.set_style(my_style)
    overlay.set_segments(list_of_TranscriptSegment)

    # In your position_changed handler:
    overlay.update_position(seconds)
"""

from __future__ import annotations

from typing import List, Optional

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QPen, QFontMetrics, QPainterPath,
)

from .SubtitleStyle import SubtitleStyle, POSITION_PRESETS
from .WhisperWorker import TranscriptSegment


class SubtitleOverlay(QWidget):
    """
    Frameless transparent tool window that floats over the video area.

    It is created as a top-level tool window (Qt.Tool | FramelessWindowHint |
    WindowTransparentForInput) rather than a child widget.  This is the only
    reliable way to paint over Qt6's FFmpeg multimedia backend, which renders
    video via a native OpenGL surface that sits above all child widgets in the
    X11 compositor regardless of z-order tricks.

    PreviewWidget owns the overlay, calls reposition(rect) whenever the video
    area moves or resizes, and show()/hide() to match video visibility.
    """

    def __init__(self, parent=None):
        # Tool window: frameless, transparent input, stays above parent
        super().__init__(
            parent,
            Qt.WindowType.Tool |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowTransparentForInput |
            Qt.WindowType.WindowDoesNotAcceptFocus |
            Qt.WindowType.NoDropShadowWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet("background: transparent;")

        self._segments: List[TranscriptSegment] = []
        self._current_text: Optional[str] = None
        self._style = SubtitleStyle()
        self._visible_sub = True

    def reposition(self, global_rect):
        """Move and resize the overlay to cover the given global screen rect."""
        self.setGeometry(global_rect)

        self._segments: List[TranscriptSegment] = []
        self._current_text: Optional[str] = None
        self._style = SubtitleStyle()
        self._visible_sub = True

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def set_style(self, style: SubtitleStyle):
        self._style = style
        self.update()

    def set_segments(self, segments: List[TranscriptSegment]):
        self._segments = segments
        self.update()

    def clear_segments(self):
        self._segments = []
        self._current_text = None
        self.update()

    def set_subtitles_visible(self, visible: bool):
        self._visible_sub = visible
        self.update()

    def update_position(self, seconds: float):
        """Call this whenever the preview position changes."""
        text = None
        for seg in self._segments:
            if seg.start <= seconds < seg.end:
                text = seg.text.strip()
                break
        if text != self._current_text:
            self._current_text = text
            self.update()

    # -------------------------------------------------------------------------
    # Paint
    # -------------------------------------------------------------------------

    def paintEvent(self, event):
        # Always clear to fully transparent first — without this, residue from
        # the previous subtitle frame remains when _current_text changes.
        p = QPainter(self)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        p.fillRect(self.rect(), Qt.GlobalColor.transparent)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        if not self._visible_sub or not self._current_text:
            p.end()
            return

        s = self._style
        text = self._current_text
        w, h = self.width(), self.height()

        font = QFont(s.font_family, s.font_size)
        font.setBold(s.font_weight == "Bold")
        p.setFont(font)
        fm = QFontMetrics(font)

        # Word-wrap at 85% of width
        max_w = int(w * 0.85)
        lines = self._wrap_text(text, fm, max_w)
        line_h = fm.height()
        total_h = line_h * len(lines)
        max_line_w = max(fm.horizontalAdvance(l) for l in lines) if lines else 0

        # Position
        margin = s.margin
        pos = s.position
        if "Right" in pos:
            tx = w - max_line_w - margin
        elif "Left" in pos:
            tx = margin
        else:
            tx = (w - max_line_w) // 2

        if "Top" in pos:
            ty = margin
        elif pos == "Centre":
            ty = (h - total_h) // 2
        else:   # Bottom
            ty = h - total_h - margin

        # Background box
        if s.bg_enabled:
            pad = 10
            r, g, b, a = s.bg_color
            p.fillRect(
                tx - pad, ty - 4,
                max_line_w + pad * 2, total_h + 8,
                QColor(r, g, b, a)
            )

        # Draw each line
        for i, line in enumerate(lines):
            lw = fm.horizontalAdvance(line)
            if "Right" in pos:
                lx = w - lw - margin
            elif "Left" in pos:
                lx = margin
            else:
                lx = (w - lw) // 2
            ly = ty + i * line_h + line_h - fm.descent()

            # Outline
            if s.outline_width > 0:
                r, g, b, a = s.outline_color
                oc = QColor(r, g, b, a)
                path = QPainterPath()
                path.addText(lx, ly, font, line)
                pen = QPen(oc, s.outline_width * 2)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(pen)
                p.strokePath(path, pen)

            # Text fill
            r, g, b, a = s.text_color
            p.setPen(QColor(r, g, b, a))
            p.drawText(lx, ly, line)

        p.end()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update()

    # -------------------------------------------------------------------------

    @staticmethod
    def _wrap_text(text: str, fm: QFontMetrics, max_w: int) -> list[str]:
        words = text.split()
        lines, current = [], ""
        for word in words:
            test = (current + " " + word).strip()
            if fm.horizontalAdvance(test) <= max_w:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines if lines else [text]