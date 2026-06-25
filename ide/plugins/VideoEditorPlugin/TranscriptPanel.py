"""
TranscriptPanel — Dockable scrollable panel showing Whisper transcription results.

Features
--------
- Clickable timestamp labels → seek preview to that position
- Segments stream in live as WhisperWorker emits segment_ready
- Copy full transcript to clipboard
- Export as .srt / .vtt / .txt
- Progress bar + status while transcribing
"""

from __future__ import annotations

import os
from typing import List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QProgressBar, QFileDialog, QApplication,
    QSizePolicy, QLineEdit,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

from .WhisperWorker import TranscriptSegment
from .ClipModel import seconds_to_tc


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

PANEL_STYLE = """
QWidget#TranscriptPanel {
    background: #1C1C1C;
    border-left: 1px solid #2A2A2A;
}

QLabel#PanelTitle {
    color: #AAAAAA;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1px;
    padding: 8px 10px 4px 10px;
}

QScrollArea#TranscriptScroll {
    background: #1C1C1C;
    border: none;
}

QWidget#ScrollContents {
    background: #1C1C1C;
}

QFrame#SegmentRow {
    background: transparent;
    border-bottom: 1px solid #252525;
}
QFrame#SegmentRow:hover {
    background: #232323;
}

QPushButton#TimestampBtn {
    background: transparent;
    border: none;
    color: #4A90D9;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 11px;
    padding: 2px 6px;
    text-align: left;
    min-width: 70px;
}
QPushButton#TimestampBtn:hover {
    color: #6AAEE8;
    text-decoration: underline;
}

QLabel#SegmentText {
    color: #CCCCCC;
    font-size: 12px;
    padding: 4px 6px 4px 0;
}

QPushButton#PanelBtn {
    background: #252525;
    border: 1px solid #333333;
    border-radius: 4px;
    color: #CCCCCC;
    font-size: 11px;
    padding: 4px 10px;
}
QPushButton#PanelBtn:hover {
    background: #2D2D2D;
    border-color: #4A90D9;
    color: #FFFFFF;
}
QPushButton#PanelBtn:pressed {
    background: #1E3A5F;
}
QPushButton#PanelBtn:disabled {
    color: #555555;
    border-color: #2A2A2A;
}

QProgressBar#TranscriptProgress {
    background: #252525;
    border: 1px solid #333333;
    border-radius: 3px;
    height: 6px;
    text-align: center;
    color: transparent;
}
QProgressBar#TranscriptProgress::chunk {
    background: #4A90D9;
    border-radius: 3px;
}

QLabel#StatusLabel {
    color: #666666;
    font-size: 11px;
    padding: 2px 10px;
    font-style: italic;
}

QLabel#EmptyLabel {
    color: #444444;
    font-size: 12px;
    padding: 20px;
}

QLineEdit#SearchBox {
    background: #252525;
    border: 1px solid #333333;
    border-radius: 4px;
    color: #CCCCCC;
    font-size: 12px;
    padding: 4px 8px 4px 26px;
    selection-background-color: #1E3A5F;
}
QLineEdit#SearchBox:focus {
    border-color: #4A90D9;
}
QLineEdit#SearchBox:placeholder {
    color: #555555;
}

QLabel#SearchIcon {
    color: #555555;
    font-size: 12px;
}

QLabel#SearchCount {
    color: #666666;
    font-size: 11px;
    padding: 0 8px;
    min-width: 48px;
}
"""


# ---------------------------------------------------------------------------
# Segment row widget
# ---------------------------------------------------------------------------

class SegmentRow(QFrame):
    """One row in the transcript — timestamp button + text label."""

    seek_requested = pyqtSignal(float)

    def __init__(self, segment: TranscriptSegment, parent=None):
        super().__init__(parent)
        self.setObjectName("SegmentRow")
        self.segment = segment

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 3, 8, 3)
        layout.setSpacing(4)

        # Timestamp button
        tc = seconds_to_tc(segment.start)
        self.btn_ts = QPushButton(tc)
        self.btn_ts.setObjectName("TimestampBtn")
        self.btn_ts.setToolTip(f"Seek to {tc}")
        self.btn_ts.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_ts.clicked.connect(lambda: self.seek_requested.emit(segment.start))
        layout.addWidget(self.btn_ts)

        # Text
        self.lbl_text = QLabel(segment.text.strip())
        self.lbl_text.setObjectName("SegmentText")
        self.lbl_text.setWordWrap(True)
        self.lbl_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.lbl_text, stretch=1)


# ---------------------------------------------------------------------------
# Main panel
# ---------------------------------------------------------------------------

class TranscriptPanel(QWidget):
    """
    Scrollable panel that shows Whisper segments as they arrive.

    Public API
    ----------
    add_segment(start, end, text)   — append a segment (called from worker signal)
    set_segments(segments)          — replace all segments at once
    set_progress(value: float)      — update progress bar 0.0–1.0
    set_status(msg: str)            — update status line
    clear()                         — reset to empty state
    seek_requested → float          — emitted when user clicks a timestamp
    """

    seek_requested  = pyqtSignal(float)
    close_requested = pyqtSignal()
    style_requested = pyqtSignal()   # user clicked the Style button      # emitted when user clicks ✕ in title bar

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TranscriptPanel")
        self.setStyleSheet(PANEL_STYLE)
        self.setMinimumWidth(200)

        self._segments: list[TranscriptSegment] = []
        self._rows:     list[SegmentRow]         = []

        self._build_ui()

    # -------------------------------------------------------------------------
    # UI
    # -------------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Title bar (label + close button)
        title_row = QWidget()
        title_row.setStyleSheet("background:transparent;")
        tr_layout = QHBoxLayout(title_row)
        tr_layout.setContentsMargins(0, 0, 4, 0)
        tr_layout.setSpacing(0)

        title = QLabel("TRANSCRIPT")
        title.setObjectName("PanelTitle")
        tr_layout.addWidget(title, stretch=1)

        btn_close_panel = QPushButton("✕")
        btn_close_panel.setObjectName("PanelBtn")
        btn_close_panel.setFixedSize(22, 22)
        btn_close_panel.setToolTip("Close transcript panel")
        btn_close_panel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_close_panel.setStyleSheet(
            "QPushButton#PanelBtn { padding:0; min-width:22px; font-size:10px; }"
        )
        btn_close_panel.clicked.connect(self.close_requested)
        tr_layout.addWidget(btn_close_panel)

        root.addWidget(title_row)

        # Action buttons
        btn_row = QWidget()
        btn_row.setStyleSheet("background:transparent;")
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(8, 4, 8, 4)
        bl.setSpacing(4)

        self.btn_copy   = QPushButton("📋 Copy")
        self.btn_export = QPushButton("💾 Export…")
        self.btn_style  = QPushButton("🎨 Style")
        self.btn_clear  = QPushButton("✕ Clear")
        for b in (self.btn_copy, self.btn_export, self.btn_style, self.btn_clear):
            b.setObjectName("PanelBtn")
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setEnabled(False)
            bl.addWidget(b)

        self.btn_copy.clicked.connect(self._copy_to_clipboard)
        self.btn_export.clicked.connect(self._export_dialog)
        self.btn_style.clicked.connect(self.style_requested)
        self.btn_clear.clicked.connect(self.clear)
        root.addWidget(btn_row)

        # Search bar
        search_row = QWidget()
        search_row.setStyleSheet("background:transparent;")
        sl = QHBoxLayout(search_row)
        sl.setContentsMargins(8, 2, 8, 4)
        sl.setSpacing(4)

        # Search icon overlaid via a label sitting in the layout — simpler than
        # stylesheet background-image which needs a resource file
        search_icon = QLabel("🔍")
        search_icon.setObjectName("SearchIcon")
        search_icon.setFixedWidth(18)
        sl.addWidget(search_icon)

        self.search_box = QLineEdit()
        self.search_box.setObjectName("SearchBox")
        self.search_box.setPlaceholderText("Search transcript…")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.setEnabled(False)
        self.search_box.textChanged.connect(self._on_search)
        # Enter / Return → seek to first visible match
        self.search_box.returnPressed.connect(self._seek_first_match)
        sl.addWidget(self.search_box, stretch=1)

        self.search_count = QLabel("")
        self.search_count.setObjectName("SearchCount")
        self.search_count.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        sl.addWidget(self.search_count)

        root.addWidget(search_row)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("color:#2A2A2A;")
        root.addWidget(div)

        # Progress bar (hidden when idle)
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("TranscriptProgress")
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.hide()
        root.addWidget(self.progress_bar)

        # Status
        self.status_label = QLabel("No transcript")
        self.status_label.setObjectName("StatusLabel")
        root.addWidget(self.status_label)

        # Scroll area
        self.scroll = QScrollArea()
        self.scroll.setObjectName("TranscriptScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.scroll_contents = QWidget()
        self.scroll_contents.setObjectName("ScrollContents")
        self.scroll_layout = QVBoxLayout(self.scroll_contents)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(0)
        self.scroll_layout.addStretch()   # pushes rows to top

        self.empty_label = QLabel("No transcript yet.\nClick 🎙 Transcribe in the toolbar.")
        self.empty_label.setObjectName("EmptyLabel")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.scroll_layout.insertWidget(0, self.empty_label)

        self.scroll.setWidget(self.scroll_contents)
        root.addWidget(self.scroll, stretch=1)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def add_segment(self, start: float, end: float, text: str):
        """Append one segment (connect to WhisperWorker.segment_ready)."""
        seg = TranscriptSegment(start=start, end=end, text=text)
        self._segments.append(seg)
        self._append_row(seg)
        self._update_buttons()

        # Auto-scroll to bottom as segments arrive
        QTimer.singleShot(0, self._scroll_to_bottom)

    def set_segments(self, segments: list):
        """Replace all segments at once (connect to WhisperWorker.finished)."""
        self.clear(keep_status=True)
        for seg in segments:
            self._segments.append(seg)
            self._append_row(seg)
        self._update_buttons()
        self.status_label.setText(f"{len(segments)} segment(s)")

    def set_progress(self, value: float):
        """Update progress bar.  value 0.0–1.0.  Hides bar at 1.0."""
        if value >= 1.0:
            self.progress_bar.setValue(1000)
            QTimer.singleShot(600, self.progress_bar.hide)
        else:
            self.progress_bar.show()
            self.progress_bar.setValue(int(value * 1000))

    def set_status(self, msg: str):
        self.status_label.setText(msg)

    def clear(self, keep_status: bool = False):
        """Remove all segments and rows."""
        self._segments.clear()
        for row in self._rows:
            self.scroll_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()

        self.empty_label.show()
        self.progress_bar.hide()
        self.progress_bar.setValue(0)

        if not keep_status:
            self.status_label.setText("No transcript")

        self._update_buttons()

    # -------------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------------

    def _append_row(self, seg: TranscriptSegment):
        if not self._rows:
            # First row — hide the empty-state label
            self.empty_label.hide()

        row = SegmentRow(seg, self.scroll_contents)
        row.seek_requested.connect(self.seek_requested)
        # Insert before the trailing stretch (last item)
        insert_pos = self.scroll_layout.count() - 1
        self.scroll_layout.insertWidget(insert_pos, row)
        self._rows.append(row)

    def _update_buttons(self):
        has = bool(self._segments)
        self.btn_copy.setEnabled(has)
        self.btn_export.setEnabled(has)
        self.btn_style.setEnabled(has)
        self.btn_clear.setEnabled(has)
        self.search_box.setEnabled(has)
        if not has:
            self.search_box.clear()
            self.search_count.setText("")

    def _scroll_to_bottom(self):
        sb = self.scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    # -------------------------------------------------------------------------
    # Search
    # -------------------------------------------------------------------------

    def _on_search(self, query: str):
        """
        Filter segment rows to those containing the query (case-insensitive).
        Empty query restores all rows.  Match count shown beside the box.
        Highlights the matching text in each visible row.
        """
        q = query.strip().lower()
        match_count = 0

        for row in self._rows:
            text = row.segment.text.strip()
            if not q:
                # No query — restore everything, clear any highlight
                row.setVisible(True)
                row.lbl_text.setText(text)
            else:
                if q in text.lower():
                    row.setVisible(True)
                    match_count += 1
                    # Highlight matching substring (case-preserving)
                    idx = text.lower().find(q)
                    highlighted = (
                        self._escape_html(text[:idx])
                        + f'<span style="background:#1E3A5F;color:#6AAEE8;">'
                        + self._escape_html(text[idx:idx + len(q)])
                        + "</span>"
                        + self._escape_html(text[idx + len(q):])
                    )
                    row.lbl_text.setText(highlighted)
                else:
                    row.setVisible(False)
                    row.lbl_text.setText(text)

        # Update count label
        if q:
            self.search_count.setText(f"{match_count} found" if match_count else "no match")
        else:
            self.search_count.setText("")

        # Scroll to first visible match so user doesn't have to hunt
        if q and match_count:
            first = next((r for r in self._rows if r.isVisible()), None)
            if first:
                QTimer.singleShot(0, lambda: self.scroll.ensureWidgetVisible(first))

    def _seek_first_match(self):
        """On Enter/Return — seek the preview to the first visible match."""
        first = next((r for r in self._rows if r.isVisible()), None)
        if first:
            self.seek_requested.emit(first.segment.start)

    @staticmethod
    def _escape_html(text: str) -> str:
        """Minimal HTML escaping for safe use in QLabel rich text."""
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # -------------------------------------------------------------------------
    # Copy / Export
    # -------------------------------------------------------------------------

    def _copy_to_clipboard(self):
        text = "\n".join(s.text.strip() for s in self._segments)
        QApplication.clipboard().setText(text)

    def _export_dialog(self):
        if not self._segments:
            return

        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Transcript",
            os.path.expanduser("~"),
            "SRT Subtitles (*.srt);;WebVTT (*.vtt);;Plain Text (*.txt)",
            "SRT Subtitles (*.srt)",
        )
        if not path:
            return

        ext = os.path.splitext(path)[1].lower()
        if not ext:
            if "vtt" in selected_filter:
                path += ".vtt"
                ext  = ".vtt"
            elif "txt" in selected_filter:
                path += ".txt"
                ext  = ".txt"
            else:
                path += ".srt"
                ext  = ".srt"

        try:
            with open(path, "w", encoding="utf-8") as f:
                if ext == ".srt":
                    f.write("".join(
                        seg.to_srt_block(i + 1) + "\n"
                        for i, seg in enumerate(self._segments)
                    ))
                elif ext == ".vtt":
                    f.write("WEBVTT\n\n")
                    f.write("".join(
                        seg.to_vtt_block() + "\n"
                        for seg in self._segments
                    ))
                else:
                    f.write("\n".join(s.text.strip() for s in self._segments))

            self.status_label.setText(f"Exported → {os.path.basename(path)}")
        except OSError as exc:
            self.status_label.setText(f"Export failed: {exc}")