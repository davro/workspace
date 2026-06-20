"""
DownloadDialog — Professional URL import dialog.

Features:
- URL paste with instant platform detection
- Metadata preview (title, duration, thumbnail) before downloading
- Quality selector
- Real-time progress with speed/ETA
- yt-dlp log panel
- Auto-adds to Media Bin on completion
"""

import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QProgressBar, QTextEdit,
    QFrame, QFileDialog, QSizePolicy, QWidget, QGraphicsOpacityEffect
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QPixmap, QColor, QPalette

from .DownloadWorker import (
    DownloadWorker, MetadataWorker,
    check_ytdlp_available, platform_icon, platform_colour
)
from .ClipModel import seconds_to_tc

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

DIALOG_STYLE = """
QDialog {
    background: #1A1A1A;
    color: #CCCCCC;
}

/* URL input row */
QLineEdit#UrlInput {
    background: #141414;
    border: 2px solid #2A2A2A;
    border-radius: 6px;
    color: #FFFFFF;
    font-size: 13px;
    padding: 8px 12px;
    min-height: 36px;
}
QLineEdit#UrlInput:focus {
    border-color: #4A90D9;
    background: #161616;
}
QLineEdit#UrlInput[state="error"] {
    border-color: #CC4444;
}
QLineEdit#UrlInput[state="ok"] {
    border-color: #4CAF50;
}

/* Fetch button */
QPushButton#FetchBtn {
    background: #252525;
    border: 2px solid #333333;
    border-radius: 6px;
    color: #AAAAAA;
    font-size: 12px;
    font-weight: bold;
    padding: 8px 18px;
    min-height: 36px;
    min-width: 80px;
}
QPushButton#FetchBtn:hover {
    background: #2D2D2D;
    border-color: #4A90D9;
    color: #FFFFFF;
}
QPushButton#FetchBtn:disabled {
    color: #444;
    border-color: #222;
}

/* Metadata card */
QWidget#MetaCard {
    background: #141414;
    border: 1px solid #2A2A2A;
    border-radius: 8px;
}
QLabel#MetaTitle {
    color: #FFFFFF;
    font-size: 14px;
    font-weight: bold;
}
QLabel#MetaSub {
    color: #888888;
    font-size: 11px;
}
QLabel#PlatformBadge {
    border-radius: 4px;
    font-size: 11px;
    font-weight: bold;
    padding: 2px 8px;
}

/* Quality selector */
QComboBox#QualityCombo {
    background: #252525;
    border: 1px solid #3A3A3A;
    border-radius: 4px;
    color: #CCCCCC;
    padding: 4px 10px;
    min-height: 28px;
    min-width: 160px;
}
QComboBox#QualityCombo::drop-down { border: none; padding-right: 8px; }
QComboBox QAbstractItemView {
    background: #252525;
    border: 1px solid #3A3A3A;
    color: #CCC;
    selection-background-color: #1E3A5F;
}

/* Output dir */
QLineEdit#OutDir {
    background: #1C1C1C;
    border: 1px solid #333;
    border-radius: 4px;
    color: #AAA;
    padding: 4px 8px;
    font-size: 11px;
}

/* Progress bar */
QProgressBar#DLProgress {
    background: #1C1C1C;
    border: 1px solid #2A2A2A;
    border-radius: 4px;
    color: #FFFFFF;
    text-align: center;
    height: 24px;
    font-size: 11px;
}
QProgressBar#DLProgress::chunk {
    border-radius: 3px;
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #1E5FAA, stop:1 #4A90D9
    );
}
QProgressBar#DLProgress[state="done"]::chunk {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #1A6B3A, stop:1 #4CAF50
    );
}
QProgressBar#DLProgress[state="error"]::chunk {
    background: #8B2020;
}

/* Log panel */
QTextEdit#LogPanel {
    background: #0D0D0D;
    border: 1px solid #222;
    border-radius: 4px;
    color: #4A8A4A;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 10px;
}

/* Download button */
QPushButton#DownloadBtn {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1E5FAA, stop:1 #1A4A8A);
    border: 1px solid #2A6ABB;
    border-radius: 6px;
    color: #FFFFFF;
    font-size: 13px;
    font-weight: bold;
    padding: 8px 24px;
    min-height: 36px;
}
QPushButton#DownloadBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2A6FBB, stop:1 #1E5FAA);
}
QPushButton#DownloadBtn:disabled {
    background: #252525;
    border-color: #333;
    color: #555;
}

QPushButton#CancelBtn {
    background: #252525;
    border: 1px solid #333;
    border-radius: 6px;
    color: #AAAAAA;
    font-size: 12px;
    padding: 8px 18px;
    min-height: 36px;
}
QPushButton#CancelBtn:hover {
    background: #2D2D2D;
    color: #FFFFFF;
}

QLabel#SectionLabel {
    color: #666666;
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 1px;
}
QFrame#Divider {
    color: #2A2A2A;
    max-height: 1px;
}

/* yt-dlp warning banner */
QWidget#YtdlpWarn {
    background: #2A1A00;
    border: 1px solid #5A3A00;
    border-radius: 6px;
}
QLabel#WarnText {
    color: #E8A838;
    font-size: 12px;
}
"""


class DownloadDialog(QDialog):
    """
    Professional URL import dialog.
    Emits file_downloaded(path) when a clip is ready.
    """

    file_downloaded = None   # set by caller, not a signal (dialog is modal)

    def __init__(self, download_dir: str, on_downloaded=None, parent=None):
        super().__init__(parent)
        self.download_dir   = download_dir
        self._on_downloaded = on_downloaded   # callback(path)
        self._meta          = None            # last fetched metadata dict
        self._formats       = []              # format list from metadata
        self._dl_worker: DownloadWorker | None   = None
        self._meta_worker: MetadataWorker | None = None

        self._ytdlp_ok, self._ytdlp_msg = check_ytdlp_available()

        self.setWindowTitle("Import from URL")
        self.setModal(True)
        self.setMinimumWidth(580)
        self.setMinimumHeight(460)
        self.setStyleSheet(DIALOG_STYLE)

        self._build_ui()

        # Auto-read clipboard
        self._try_paste_clipboard()

    # =========================================================================
    # UI
    # =========================================================================

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # ---- yt-dlp warning if not installed ----
        if not self._ytdlp_ok:
            warn_card = QWidget()
            warn_card.setObjectName("YtdlpWarn")
            wl = QVBoxLayout(warn_card)
            wl.setContentsMargins(12, 10, 12, 10)
            icon_row = QHBoxLayout()
            icon_lbl = QLabel("⚠")
            icon_lbl.setStyleSheet("font-size:20px; color:#E8A838;")
            icon_row.addWidget(icon_lbl)
            warn_text = QLabel(
                "<b>yt-dlp is not installed.</b><br>"
                "Install it to enable URL import:<br>"
                "<code style='color:#AAA'>pip install yt-dlp</code>"
            )
            warn_text.setObjectName("WarnText")
            warn_text.setTextFormat(Qt.TextFormat.RichText)
            icon_row.addWidget(warn_text, stretch=1)
            wl.addLayout(icon_row)
            layout.addWidget(warn_card)

        # ---- URL input ----
        self._section("URL", layout)
        url_row = QHBoxLayout()
        url_row.setSpacing(8)

        self.url_input = QLineEdit()
        self.url_input.setObjectName("UrlInput")
        self.url_input.setPlaceholderText(
            "Paste URL — YouTube, Kick, TikTok, Twitch, Twitter/X, Instagram, Vimeo…"
        )
        self.url_input.returnPressed.connect(self._fetch_metadata)
        self.url_input.textChanged.connect(self._on_url_changed)

        self.btn_fetch = QPushButton("🔍 Preview")
        self.btn_fetch.setObjectName("FetchBtn")
        self.btn_fetch.clicked.connect(self._fetch_metadata)
        self.btn_fetch.setEnabled(self._ytdlp_ok)

        url_row.addWidget(self.url_input, stretch=1)
        url_row.addWidget(self.btn_fetch)
        layout.addLayout(url_row)

        # ---- Metadata card (hidden until fetch) ----
        self.meta_card = self._build_meta_card()
        self.meta_card.hide()
        layout.addWidget(self.meta_card)

        # ---- Output settings ----
        self._section("SAVE TO", layout)
        dir_row = QHBoxLayout()
        dir_row.setSpacing(8)
        self.out_dir_input = QLineEdit(self.download_dir)
        self.out_dir_input.setObjectName("OutDir")
        self.out_dir_input.setReadOnly(True)
        btn_browse = QPushButton("…")
        btn_browse.setFixedWidth(32)
        btn_browse.setStyleSheet(
            "background:#252525; border:1px solid #333; border-radius:4px;"
            "color:#AAA; font-size:14px; padding:0; min-height:28px;"
        )
        btn_browse.clicked.connect(self._browse_dir)
        dir_row.addWidget(self.out_dir_input, stretch=1)
        dir_row.addWidget(btn_browse)
        layout.addLayout(dir_row)

        # ---- Progress ----
        self._section("PROGRESS", layout)
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("DLProgress")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Ready to download")
        layout.addWidget(self.progress_bar)

        self.log_panel = QTextEdit()
        self.log_panel.setObjectName("LogPanel")
        self.log_panel.setReadOnly(True)
        self.log_panel.setMaximumHeight(110)
        layout.addWidget(self.log_panel)

        layout.addStretch()

        # ---- Buttons ----
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_close = QPushButton("Close")
        self.btn_close.setObjectName("CancelBtn")
        self.btn_close.clicked.connect(self._on_close)

        self.btn_download = QPushButton("⬇  Download")
        self.btn_download.setObjectName("DownloadBtn")
        self.btn_download.clicked.connect(self._start_download)
        self.btn_download.setEnabled(False)

        btn_row.addWidget(self.btn_close)
        btn_row.addWidget(self.btn_download)
        layout.addLayout(btn_row)

    def _build_meta_card(self) -> QWidget:
        card = QWidget()
        card.setObjectName("MetaCard")
        cl = QHBoxLayout(card)
        cl.setContentsMargins(12, 10, 12, 10)
        cl.setSpacing(12)

        # Platform icon (large emoji)
        self.lbl_platform_icon = QLabel("🌐")
        self.lbl_platform_icon.setStyleSheet("font-size: 32px;")
        self.lbl_platform_icon.setFixedWidth(44)
        cl.addWidget(self.lbl_platform_icon)

        # Info column
        info_col = QVBoxLayout()
        info_col.setSpacing(3)

        self.lbl_meta_title = QLabel("—")
        self.lbl_meta_title.setObjectName("MetaTitle")
        self.lbl_meta_title.setWordWrap(True)
        info_col.addWidget(self.lbl_meta_title)

        row2 = QHBoxLayout()
        self.lbl_platform_badge = QLabel("—")
        self.lbl_platform_badge.setObjectName("PlatformBadge")
        self.lbl_meta_duration   = QLabel("")
        self.lbl_meta_duration.setObjectName("MetaSub")
        self.lbl_meta_uploader   = QLabel("")
        self.lbl_meta_uploader.setObjectName("MetaSub")
        row2.addWidget(self.lbl_platform_badge)
        row2.addWidget(self.lbl_meta_duration)
        row2.addWidget(self.lbl_meta_uploader)
        row2.addStretch()
        info_col.addLayout(row2)

        # Quality selector row
        qual_row = QHBoxLayout()
        qual_lbl = QLabel("Quality:")
        qual_lbl.setObjectName("MetaSub")
        self.quality_combo = QComboBox()
        self.quality_combo.setObjectName("QualityCombo")
        qual_row.addWidget(qual_lbl)
        qual_row.addWidget(self.quality_combo)
        qual_row.addStretch()
        info_col.addLayout(qual_row)

        cl.addLayout(info_col, stretch=1)
        return card

    def _section(self, text: str, layout):
        lbl = QLabel(text)
        lbl.setObjectName("SectionLabel")
        layout.addWidget(lbl)

    # =========================================================================
    # Clipboard
    # =========================================================================

    def _try_paste_clipboard(self):
        from PyQt6.QtWidgets import QApplication
        clip = QApplication.clipboard().text().strip()
        if clip and (clip.startswith("http://") or clip.startswith("https://")):
            self.url_input.setText(clip)
            if self._ytdlp_ok:
                QTimer.singleShot(300, self._fetch_metadata)

    # =========================================================================
    # URL / fetch
    # =========================================================================

    def _on_url_changed(self, text: str):
        self.url_input.setProperty("state", "")
        self.url_input.style().unpolish(self.url_input)
        self.url_input.style().polish(self.url_input)
        self.btn_download.setEnabled(False)
        self.meta_card.hide()

    def _fetch_metadata(self):
        url = self.url_input.text().strip()
        if not url:
            return
        if not (url.startswith("http://") or url.startswith("https://")):
            self._set_url_state("error")
            self._log("⚠ Please enter a valid URL starting with http:// or https://")
            return

        self.btn_fetch.setEnabled(False)
        self.btn_fetch.setText("⏳ Loading…")
        self.meta_card.hide()
        self._log(f"Fetching metadata for:\n{url}\n")

        self._meta_worker = MetadataWorker(url, self)
        self._meta_worker.finished.connect(self._on_meta_done)
        self._meta_worker.error.connect(self._on_meta_error)
        self._meta_worker.start()

    def _on_meta_done(self, meta: dict):
        self._meta    = meta
        self._formats = meta.get("formats", [])

        self.btn_fetch.setText("🔍 Preview")
        self.btn_fetch.setEnabled(True)
        self._set_url_state("ok")

        # Populate metadata card
        title    = meta["title"]
        platform = meta["platform"]
        duration = meta["duration"]
        uploader = meta.get("uploader", "")

        self.lbl_meta_title.setText(title[:120])
        self.lbl_platform_icon.setText(platform_icon(platform))

        colour = platform_colour(platform)
        self.lbl_platform_badge.setText(f" {platform} ")
        self.lbl_platform_badge.setStyleSheet(
            f"background: {colour}22; color: {colour}; "
            f"border: 1px solid {colour}55; border-radius: 4px; "
            "font-size: 11px; font-weight: bold; padding: 2px 8px;"
        )

        self.lbl_meta_duration.setText(
            f"⏱ {seconds_to_tc(duration)}" if duration else ""
        )
        self.lbl_meta_uploader.setText(
            f"  👤 {uploader}" if uploader else ""
        )

        # Quality options
        self.quality_combo.clear()
        for fmt in self._formats:
            size_str = ""
            if fmt["filesize"] > 0:
                size_str = f"  ({fmt['filesize'] / 1024 / 1024:.0f} MB)"
            self.quality_combo.addItem(
                f"{fmt['label']}{size_str}",
                userData=fmt["format_id"]
            )

        self.meta_card.show()
        self.btn_download.setEnabled(True)
        self._log(f"✓ Found: {title}\n  Platform: {platform}  •  Duration: {seconds_to_tc(duration)}\n")

    def _on_meta_error(self, error: str):
        self.btn_fetch.setText("🔍 Preview")
        self.btn_fetch.setEnabled(True)
        self._set_url_state("error")
        self._log(f"❌ {error}\n")

    def _set_url_state(self, state: str):
        self.url_input.setProperty("state", state)
        self.url_input.style().unpolish(self.url_input)
        self.url_input.style().polish(self.url_input)

    # =========================================================================
    # Download
    # =========================================================================

    def _browse_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, "Save Downloads To", self.download_dir
        )
        if path:
            self.download_dir = path
            self.out_dir_input.setText(path)

    def _start_download(self):
        url = self.url_input.text().strip()
        if not url:
            return

        format_id = "bestvideo+bestaudio/best"
        if self.quality_combo.count() > 0:
            format_id = self.quality_combo.currentData() or format_id

        self.btn_download.setEnabled(False)
        self.btn_download.setText("⬇  Downloading…")
        self.btn_fetch.setEnabled(False)
        self._set_progress(0, "Starting download…", "")

        self._dl_worker = DownloadWorker(
            url        = url,
            output_dir = self.download_dir,
            format_id  = format_id,
            parent     = self,
        )
        self._dl_worker.progress.connect(self._on_dl_progress)
        self._dl_worker.finished.connect(self._on_dl_finished)
        self._dl_worker.error.connect(self._on_dl_error)
        self._dl_worker.log.connect(self._log)
        self._dl_worker.start()

    def _on_dl_progress(self, pct: float, status: str):
        self._set_progress(int(pct * 100), status, "")

    def _on_dl_finished(self, path: str):
        self._set_progress(100, f"✓  Downloaded: {Path(path).name}", "done")
        self.btn_download.setText("⬇  Download Another")
        self.btn_download.setEnabled(True)
        self.btn_fetch.setEnabled(True)
        self.btn_close.setText("Close")
        self._log(f"\n✅ Saved to: {path}\n")

        # Fire callback to add to bin
        if self._on_downloaded:
            self._on_downloaded(path)

    def _on_dl_error(self, error: str):
        self._set_progress(0, f"Error", "error")
        self.btn_download.setText("⬇  Retry")
        self.btn_download.setEnabled(True)
        self.btn_fetch.setEnabled(True)
        self._log(f"\n❌ {error}\n")

    def _set_progress(self, value: int, label: str, state: str):
        self.progress_bar.setValue(value)
        self.progress_bar.setFormat(label if label else f"{value}%")
        self.progress_bar.setProperty("state", state)
        self.progress_bar.style().unpolish(self.progress_bar)
        self.progress_bar.style().polish(self.progress_bar)

    def _log(self, line: str):
        # Filter noisy lines
        skip = {"frame=", "fps=", "stream_", "bitrate=", "total_size",
                 "out_time", "dup_frames", "drop_frames", "speed=", "progress="}
        if any(line.startswith(s) for s in skip):
            return
        self.log_panel.append(line.rstrip())
        # Auto-scroll
        sb = self.log_panel.verticalScrollBar()
        sb.setValue(sb.maximum())

    # =========================================================================
    # Close
    # =========================================================================

    def _on_close(self):
        if self._dl_worker and self._dl_worker.isRunning():
            self._dl_worker.cancel()
            self._dl_worker.wait(2000)
        if self._meta_worker and self._meta_worker.isRunning():
            self._meta_worker.quit()
            self._meta_worker.wait(1000)
        self.reject()

    def closeEvent(self, event):
        self._on_close()
        super().closeEvent(event)
