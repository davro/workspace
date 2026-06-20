"""
ExportDialog — Export settings and progress dialog.
"""

import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSlider, QProgressBar, QFileDialog, QLineEdit,
    QGroupBox, QFormLayout, QTextEdit, QDialogButtonBox, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from .ClipModel import Project
from .FFmpegWorker import ExportWorker

DIALOG_STYLE = """
QDialog {
    background: #1E1E1E;
    color: #CCCCCC;
}
QGroupBox {
    border: 1px solid #333333;
    border-radius: 4px;
    margin-top: 10px;
    padding: 8px;
    color: #AAAAAA;
    font-size: 11px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}
QLabel {
    color: #AAAAAA;
}
QLineEdit, QComboBox {
    background: #252525;
    border: 1px solid #3A3A3A;
    border-radius: 3px;
    color: #CCCCCC;
    padding: 4px 8px;
    min-height: 24px;
}
QLineEdit:focus, QComboBox:focus {
    border-color: #4A90D9;
}
QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}
QComboBox QAbstractItemView {
    background: #252525;
    border: 1px solid #3A3A3A;
    color: #CCC;
    selection-background-color: #1E3A5F;
}
QPushButton#ExportBtn {
    background: #1E4A8A;
    border: 1px solid #2A5FA0;
    border-radius: 4px;
    color: #FFFFFF;
    font-weight: bold;
    padding: 6px 20px;
    min-height: 28px;
}
QPushButton#ExportBtn:hover {
    background: #2255A0;
}
QPushButton#ExportBtn:disabled {
    background: #252525;
    color: #555;
    border-color: #333;
}
QPushButton#CancelBtn {
    background: #2A2A2A;
    border: 1px solid #3A3A3A;
    border-radius: 4px;
    color: #AAAAAA;
    padding: 6px 16px;
    min-height: 28px;
}
QPushButton#CancelBtn:hover {
    background: #333333;
    color: #FFFFFF;
}
QProgressBar {
    background: #252525;
    border: 1px solid #333;
    border-radius: 3px;
    color: #CCC;
    text-align: center;
    height: 20px;
}
QProgressBar::chunk {
    background: #4A90D9;
    border-radius: 2px;
}
QTextEdit#LogView {
    background: #141414;
    border: 1px solid #2A2A2A;
    color: #666666;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 10px;
}
QPushButton#BrowseBtn {
    background: #252525;
    border: 1px solid #3A3A3A;
    border-radius: 3px;
    color: #AAA;
    padding: 4px 10px;
}
QPushButton#BrowseBtn:hover {
    background: #2D2D2D;
    color: #FFF;
}
"""


class ExportDialog(QDialog):
    """
    Export settings + progress dialog.
    """

    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self.project  = project
        self._worker: ExportWorker | None = None

        self.setWindowTitle("Export Video")
        self.setModal(True)
        self.setMinimumWidth(520)
        self.setStyleSheet(DIALOG_STYLE)

        self._build_ui()
        self._set_defaults()

    # -------------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # ---- Output file ----
        out_group = QGroupBox("Output File")
        out_form  = QFormLayout(out_group)
        out_form.setSpacing(8)

        path_row = QHBoxLayout()
        self.out_path = QLineEdit()
        self.out_path.setPlaceholderText("Choose output path…")
        browse = QPushButton("Browse…")
        browse.setObjectName("BrowseBtn")
        browse.clicked.connect(self._browse_output)
        path_row.addWidget(self.out_path)
        path_row.addWidget(browse)
        out_form.addRow("Save to:", path_row)
        layout.addWidget(out_group)

        # ---- Format / codec ----
        fmt_group = QGroupBox("Format & Quality")
        fmt_form  = QFormLayout(fmt_group)
        fmt_form.setSpacing(8)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["MP4 (H.264)", "MP4 (H.265 / HEVC)", "WebM (VP9)", "MOV (ProRes)"])
        fmt_form.addRow("Format:", self.format_combo)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(["ultrafast", "superfast", "veryfast", "faster",
                                     "fast", "medium", "slow", "slower", "veryslow"])
        self.preset_combo.setCurrentText("medium")
        fmt_form.addRow("Encode speed:", self.preset_combo)

        crf_row = QHBoxLayout()
        self.crf_slider = QSlider(Qt.Orientation.Horizontal)
        self.crf_slider.setRange(0, 51)
        self.crf_slider.setValue(23)
        self.crf_label  = QLabel("23  (good quality)")
        self.crf_slider.valueChanged.connect(self._on_crf_changed)
        crf_row.addWidget(self.crf_slider)
        crf_row.addWidget(self.crf_label)
        fmt_form.addRow("Quality (CRF):", crf_row)

        self.res_combo = QComboBox()
        self.res_combo.addItems([
            f"{self.project.width}×{self.project.height} (Project)",
            "3840×2160 (4K)", "1920×1080 (1080p)",
            "1280×720 (720p)",  "854×480 (480p)",
        ])
        fmt_form.addRow("Resolution:", self.res_combo)

        layout.addWidget(fmt_group)

        # ---- Progress ----
        prog_group = QGroupBox("Progress")
        prog_layout = QVBoxLayout(prog_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Ready")
        prog_layout.addWidget(self.progress_bar)

        self.log_view = QTextEdit()
        self.log_view.setObjectName("LogView")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(100)
        prog_layout.addWidget(self.log_view)

        layout.addWidget(prog_group)

        # ---- Buttons ----
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("CancelBtn")
        self.btn_cancel.clicked.connect(self._on_cancel)

        self.btn_export = QPushButton("▶  Export")
        self.btn_export.setObjectName("ExportBtn")
        self.btn_export.clicked.connect(self._on_export)

        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_export)
        layout.addLayout(btn_row)

    def _set_defaults(self):
        home = os.path.expanduser("~")
        name = self.project.name.replace(" ", "_") or "export"
        self.out_path.setText(os.path.join(home, f"{name}.mp4"))

    # -------------------------------------------------------------------------

    def _browse_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Video As", self.out_path.text(),
            "MP4 (*.mp4);;MOV (*.mov);;WebM (*.webm);;All Files (*)"
        )
        if path:
            self.out_path.setText(path)

    def _on_crf_changed(self, value: int):
        if value <= 18:
            quality = "visually lossless"
        elif value <= 23:
            quality = "good quality"
        elif value <= 28:
            quality = "moderate quality"
        else:
            quality = "lower quality / smaller file"
        self.crf_label.setText(f"{value}  ({quality})")

    # -------------------------------------------------------------------------

    def _on_export(self):
        out_path = self.out_path.text().strip()
        if not out_path:
            self.log_view.append("⚠ Please choose an output path.")
            return

        if not self.project.clips:
            self.log_view.append("⚠ No clips on the timeline.")
            return

        self.btn_export.setEnabled(False)
        self.progress_bar.setFormat("Exporting…  %p%")

        self._worker = ExportWorker(
            project     = self.project,
            output_path = out_path,
            preset      = self.preset_combo.currentText(),
            crf         = self.crf_slider.value(),
            parent      = self,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.log.connect(self._on_log)
        self._worker.start()

    def _on_cancel(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(2000)
            self.log_view.append("Export cancelled.")
            self.progress_bar.setFormat("Cancelled")
            self.btn_export.setEnabled(True)
        else:
            self.reject()

    def _on_progress(self, pct: float):
        self.progress_bar.setValue(int(pct * 100))

    def _on_finished(self, path: str):
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("Complete ✓")
        self.log_view.append(f"✅ Exported to: {path}")
        self.btn_export.setEnabled(True)

    def _on_error(self, msg: str):
        self.progress_bar.setFormat("Error")
        self.log_view.append(f"❌ {msg}")
        self.btn_export.setEnabled(True)

    def _on_log(self, line: str):
        # Only show meaningful lines (skip blank / stats noise)
        if line and not line.startswith("frame=") and not line.startswith("fps="):
            self.log_view.append(line)

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(2000)
        super().closeEvent(event)
