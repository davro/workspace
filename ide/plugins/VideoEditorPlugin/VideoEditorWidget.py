"""
VideoEditorWidget — Top-level container for the Video Editor plugin UI.

Layout:
  ┌──────────────────────────────────────────────────────┐
  │  Toolbar                                             │
  ├──────────────┬───────────────────────────┬───────────┤
  │  Media Bin   │  Preview (QGraphicsView)  │ Transcript│
  │  (left)      │                           │  Panel    │
  │              ├───────────────────────────┤ (right,   │
  │              │  Transport controls       │  hidden   │
  ├──────────────┴───────────────────────────┴───────────┤
  │  Timeline (QGraphicsView)                            │
  └──────────────────────────────────────────────────────┘
"""

import os
import json
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QFileDialog,
    QSizePolicy, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QKeySequence, QShortcut

from .ClipModel import (
    Project, Clip, Track, TrackType, ClipType,
    next_clip_colour, seconds_to_tc
)
from .MediaBin import MediaBin, BinItem
from .PreviewWidget import PreviewWidget
from .TimelineWidget import TimelineWidget
from .FFmpegWorker import check_ffmpeg_available
from .WhisperWorker import WhisperWorker
from .WhisperDialog import WhisperDialog
from .TranscriptPanel import TranscriptPanel
from .SubtitleStyle import SubtitleStyle
from .SubtitleStyleDialog import SubtitleStyleDialog


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

EDITOR_STYLE = """
QWidget#VideoEditor {
    background: #1A1A1A;
    color: #CCCCCC;
}

/* ---- Toolbar ---- */
QWidget#EditorToolbar {
    background: #141414;
    border-bottom: 1px solid #2A2A2A;
}

QPushButton#ToolBtn {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    color: #AAAAAA;
    font-size: 12px;
    padding: 4px 12px;
    min-height: 28px;
}
QPushButton#ToolBtn:hover {
    background: #252525;
    border-color: #3A3A3A;
    color: #FFFFFF;
}
QPushButton#ToolBtn:pressed {
    background: #1E3A5F;
    border-color: #4A90D9;
}

QPushButton#ToolBtn:checked {
    background: #1E3A5F;
    border-color: #4A90D9;
    color: #6AAEE8;
}
QPushButton#ToolBtn:checked:hover {
    background: #1E4A8A;
    color: #FFFFFF;
}

QPushButton#ToolBtn[accent="true"] {
    background: #1A3A6A;
    border-color: #2A5FA0;
    color: #6AAEE8;
}
QPushButton#ToolBtn[accent="true"]:hover {
    background: #1E4A8A;
    color: #FFFFFF;
}

QLabel#ToolSep {
    color: #333333;
    padding: 0 4px;
    font-size: 18px;
}

QLabel#ProjectLabel {
    color: #666666;
    font-size: 11px;
    font-style: italic;
    padding: 0 8px;
}

/* ---- Splitters ---- */
QSplitter::handle {
    background: #2A2A2A;
}
QSplitter::handle:hover {
    background: #4A90D9;
}
QSplitter::handle:horizontal {
    width: 3px;
}
QSplitter::handle:vertical {
    height: 3px;
}

/* ---- Status bar ---- */
QLabel#StatusBar {
    background: #111111;
    border-top: 1px solid #222222;
    color: #555555;
    font-size: 11px;
    font-family: 'Consolas', monospace;
    padding: 2px 10px;
}
"""


class VideoEditorWidget(QWidget):
    """
    The main UI panel returned by VideoEditorPlugin.get_widget().
    """

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self.setObjectName("VideoEditor")
        self.setStyleSheet(EDITOR_STYLE)

        # Project state
        self.project      = Project(name="Untitled Project")
        self._project_path: str | None = None
        self._modified    = False

        # FFmpeg check
        self._ffmpeg_ok, self._ffmpeg_msg = check_ffmpeg_available()

        # Whisper worker tracking (REQUIRED — GC kills workers without a reference)
        self._whisper_workers: list = []
        # Subtitle state
        self._subtitle_style    = SubtitleStyle()
        self._subtitle_segments: list = []   # last completed transcription
        self._subs_visible:     bool  = True  # toggle state for overlay

        self._build_ui()
        self._connect_signals()
        self._setup_shortcuts()
        self._refresh_status()

    # =========================================================================
    # UI construction
    # =========================================================================

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Toolbar
        root.addWidget(self._build_toolbar())

        # Main content area (vertical splitter: upper + timeline)
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.setHandleWidth(3)

        # Upper area (horizontal: bin + preview)
        self._upper_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._upper_splitter.setHandleWidth(3)

        # Media Bin
        self.media_bin = MediaBin()
        self._upper_splitter.addWidget(self.media_bin)

        # Preview
        self.preview = PreviewWidget()
        self._upper_splitter.addWidget(self.preview)

        # Transcript panel (right side, hidden until first transcription)
        self.transcript_panel = TranscriptPanel()
        self.transcript_panel.hide()
        self._upper_splitter.addWidget(self.transcript_panel)

        # Proportions: bin ~220px, preview takes rest, transcript collapsed
        self._upper_splitter.setSizes([220, 9999, 0])
        self._upper_splitter.setStretchFactor(0, 0)
        self._upper_splitter.setStretchFactor(1, 1)
        self._upper_splitter.setStretchFactor(2, 0)

        main_splitter.addWidget(self._upper_splitter)

        # Timeline
        self.timeline = TimelineWidget()
        self.timeline.setMinimumHeight(130)
        main_splitter.addWidget(self.timeline)

        # Upper 65%, timeline 35%
        main_splitter.setSizes([650, 350])
        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 1)

        root.addWidget(main_splitter, stretch=1)

        # Status bar
        self.status_bar = QLabel()
        self.status_bar.setObjectName("StatusBar")
        self.status_bar.setFixedHeight(20)
        root.addWidget(self.status_bar)

        # Load empty project into timeline and preview
        self.timeline.load_project(self.project)
        # Give preview a reference so Timeline mode knows the project
        self.preview.set_project(self.project)

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("EditorToolbar")
        bar.setFixedHeight(42)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        def _btn(text: str, tip: str, accent: bool = False) -> QPushButton:
            b = QPushButton(text)
            b.setObjectName("ToolBtn")
            b.setToolTip(tip)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            if accent:
                b.setProperty("accent", True)
            return b

        def _sep() -> QLabel:
            s = QLabel("|")
            s.setObjectName("ToolSep")
            return s

        self.btn_new     = _btn("📄 New",    "New project")
        self.btn_open    = _btn("📂 Open",   "Open project file")
        self.btn_save    = _btn("💾 Save",   "Save project  [Ctrl+S]")
        self.btn_import  = _btn("＋ Import", "Import media files")
        self.btn_url     = _btn("🌐 URL Import", "Import from YouTube, Kick, TikTok, Twitch and more…")
        self.btn_transcribe = _btn("🎙 Transcribe", "Transcribe audio with Whisper AI")
        self.btn_subs    = _btn("💬 Subtitles", "Show / hide subtitle overlay  [T]")
        self.btn_subs.setCheckable(True)
        self.btn_subs.setChecked(True)    # on by default — matches _subs_visible = True
        self.btn_subs.setEnabled(False)   # enabled only after first transcription
        self.btn_export  = _btn("▶ Export", "Export / render timeline", accent=True)

        layout.addWidget(self.btn_new)
        layout.addWidget(self.btn_open)
        layout.addWidget(self.btn_save)
        layout.addWidget(_sep())
        layout.addWidget(self.btn_import)
        layout.addWidget(self.btn_url)
        layout.addWidget(_sep())
        layout.addWidget(self.btn_transcribe)
        layout.addWidget(self.btn_subs)
        layout.addWidget(_sep())
        layout.addWidget(self.btn_export)
        layout.addStretch()

        # Project name label
        self.project_label = QLabel("Untitled Project")
        self.project_label.setObjectName("ProjectLabel")
        layout.addWidget(self.project_label)

        # FFmpeg status indicator
        ffmpeg_indicator = QLabel(
            "✓ FFmpeg" if self._ffmpeg_ok else "⚠ No FFmpeg"
        )
        ffmpeg_indicator.setStyleSheet(
            f"color: {'#4CAF50' if self._ffmpeg_ok else '#E57373'};"
            "font-size: 11px; padding: 0 8px;"
        )
        ffmpeg_indicator.setToolTip(self._ffmpeg_msg)
        layout.addWidget(ffmpeg_indicator)

        return bar

    # =========================================================================
    # Signal wiring
    # =========================================================================

    def _connect_signals(self):
        # Toolbar
        self.btn_new.clicked.connect(self._new_project)
        self.btn_open.clicked.connect(self._open_project)
        self.btn_save.clicked.connect(self._save_project)
        self.btn_import.clicked.connect(self.media_bin.import_media)
        self.btn_url.clicked.connect(self._url_import)
        self.btn_export.clicked.connect(self._export)
        self.btn_transcribe.clicked.connect(self._transcribe)
        self.btn_subs.clicked.connect(self._toggle_subtitles)

        # Recover gracefully from audio device loss (suspend/resume, PipeWire restart)
        self.preview.player.errorOccurred.connect(self._on_player_error)

        # Transcript panel → preview seek + close
        self.transcript_panel.seek_requested.connect(self._on_seek)
        self.transcript_panel.close_requested.connect(self._hide_transcript_panel)
        self.transcript_panel.style_requested.connect(self._open_subtitle_style)

        # Media bin → preview + timeline
        self.media_bin.clip_selected.connect(self._on_bin_clip_selected)
        self.media_bin.clip_add_to_timeline.connect(self._on_add_to_timeline)

        # Preview ↔ timeline (playhead sync)
        self.preview.position_changed.connect(self.timeline.set_playhead)

        # Timeline → preview (click-to-seek)
        self.timeline.seek_requested.connect(self._on_seek)

    def _setup_shortcuts(self):
        # Space → play/pause
        space = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        space.activated.connect(self.preview.toggle_play)

        # Ctrl+S → save
        save_sc = QShortcut(QKeySequence("Ctrl+S"), self)
        save_sc.activated.connect(self._save_project)

        # S → split at playhead (timeline focused)
        split_sc = QShortcut(QKeySequence(Qt.Key.Key_S), self)
        split_sc.activated.connect(self.timeline._split_at_playhead)

        # T → toggle subtitle overlay
        subs_sc = QShortcut(QKeySequence(Qt.Key.Key_T), self)
        subs_sc.activated.connect(self._toggle_subtitles)

        # Delete / Backspace → delete selected clip
        del_sc = QShortcut(QKeySequence(Qt.Key.Key_Delete), self)
        del_sc.activated.connect(self.timeline._delete_selected)
        bsp_sc = QShortcut(QKeySequence(Qt.Key.Key_Backspace), self)
        bsp_sc.activated.connect(self.timeline._delete_selected)

    # =========================================================================
    # Media bin → preview
    # =========================================================================

    def _on_bin_clip_selected(self, bin_item: BinItem):
        """Single click in bin → preview the source file."""
        if bin_item.path and bin_item.info:
            self.preview.load_source(bin_item.path)
            self._set_status(f"Preview: {bin_item.name}  "
                             f"{bin_item.info.resolution}  "
                             f"{bin_item.info.duration_tc}")

    def _on_add_to_timeline(self, bin_item: BinItem):
        """Double-click or context menu 'Add to Timeline'."""
        if not bin_item.info:
            self._set_status("⚠ Still probing — try again in a moment")
            return

        info = bin_item.info
        duration = info.duration

        # Determine next free position on V1 — end of the last clip on that track
        existing = self.project.clips_on_track(0, TrackType.VIDEO)
        if existing:
            # Guard: only count clips that have a real duration
            ends = [c.timeline_end for c in existing if c.source_duration > 0]
            position = max(ends) if ends else 0.0
        else:
            position = 0.0

        clip = Clip(
            source_path       = bin_item.path,
            clip_type         = info.clip_type,
            track_index       = 0,
            track_type        = TrackType.VIDEO,
            in_point          = 0.0,
            out_point         = duration,       # always explicit — never rely on 0 default
            media_duration    = duration,
            timeline_position = position,
            label             = Path(bin_item.path).stem,
            color             = next_clip_colour(),
        )

        self.project.add_clip(clip)
        self.project.add_to_bin(bin_item.path)
        self.timeline.add_clip(clip)
        self.preview.set_project(self.project)  # refresh duration

        self._modified = True
        self._refresh_status()
        self.plugin.api.show_status_message(
            f"🎬 Added '{clip.display_name}' to timeline", 2000
        )

    # =========================================================================
    # Seek
    # =========================================================================

    def _on_seek(self, seconds: float):
        """
        Timeline ruler clicked — switch preview to Timeline mode and seek.
        The PreviewWidget handles clip lookup and source switching internally.
        """
        self.preview.timeline_seek(seconds)

    # =========================================================================
    # Project management
    # =========================================================================

    def _new_project(self):
        if self._modified:
            reply = QMessageBox.question(
                self, "New Project",
                "Discard unsaved changes and create a new project?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self.project       = Project(name="Untitled Project")
        self._project_path = None
        self._modified     = False
        self.preview.clear()
        self.timeline.load_project(self.project)
        self.preview.set_project(self.project)
        self.project_label.setText("Untitled Project")
        self._refresh_status()

    def _open_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", os.path.expanduser("~"),
            "Video Editor Project (*.vep);;All Files (*)"
        )
        if not path:
            return
        try:
            self.project       = Project.load(path)
            self._project_path = path
            self._modified     = False
            self.timeline.load_project(self.project)
            self.preview.set_project(self.project)
            self.project_label.setText(self.project.name)
            # Re-add bin items
            for p in self.project.media_bin:
                self.media_bin.add_file(p)
            self._load_sidecar(path)
            self._refresh_status()
            self.plugin.api.show_status_message(f"Opened: {Path(path).name}", 2000)
        except Exception as e:
            QMessageBox.critical(self, "Open Failed", str(e))

    def _save_project(self):
        if not self._project_path:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Project", os.path.expanduser("~"),
                "Video Editor Project (*.vep);;All Files (*)"
            )
            if not path:
                return
            if not path.endswith(".vep"):
                path += ".vep"
            self._project_path = path

        try:
            self.project.save(self._project_path)
            self._save_sidecar(self._project_path)
            self._modified = False
            self.project_label.setText(self.project.name)
            self.plugin.api.show_status_message(
                f"💾 Project saved: {Path(self._project_path).name}", 2000
            )
            self._refresh_status()
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", str(e))

    # =========================================================================
    # Whisper transcription
    # =========================================================================

    def _transcribe(self):
        """Open model-picker dialog then launch WhisperWorker on the selected clip."""
        # Check faster-whisper is available before opening the dialog
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            QMessageBox.warning(
                self,
                "faster-whisper Not Installed",
                "The Whisper transcription feature requires the faster-whisper package.\n\n"
                "Install it by running:\n\n"
                "    pip install faster-whisper\n\n"
                "Then restart the application."
            )
            return

        # Find currently selected bin clip (if any)
        bin_path: str | None = None
        bin_name: str | None = None
        selected_items = self.media_bin.clip_list.selectedItems()
        if selected_items:
            from PyQt6.QtCore import Qt as _Qt
            path = selected_items[0].data(_Qt.ItemDataRole.UserRole)
            if path:
                bin_path = path
                bin_name = self.media_bin._items[path].name if path in self.media_bin._items else path

        dlg = WhisperDialog(bin_path=bin_path, bin_name=bin_name, parent=self)
        if dlg.exec() != WhisperDialog.DialogCode.Accepted:
            return

        source_path = dlg.selected_source
        if not source_path:
            return

        # Get duration for progress reporting
        source_duration = 0.0
        if source_path in self.media_bin._items:
            item = self.media_bin._items[source_path]
            if item.info:
                source_duration = item.info.duration

        # Show the transcript panel.
        # Qt6 ignores setSizes on a hidden splitter widget; must show first then
        # defer setSizes past the current event loop tick via QTimer.singleShot.
        self.transcript_panel.clear()
        self.transcript_panel.show()

        def _resize_splitter():
            sizes = self._upper_splitter.sizes()
            total = sum(sizes)
            panel_width   = min(300, max(240, total // 4))
            bin_width     = sizes[0] if sizes else 220
            preview_width = max(200, total - bin_width - panel_width)
            self._upper_splitter.setSizes([bin_width, preview_width, panel_width])

        from PyQt6.QtCore import QTimer as _QTimer
        _QTimer.singleShot(0, _resize_splitter)
        self.transcript_panel.set_status(
            f"Transcribing with '{dlg.selected_model}' model…"
        )
        self.transcript_panel.set_progress(0.0)

        # Launch worker
        worker = WhisperWorker(
            source_path     = source_path,
            model_size      = dlg.selected_model,
            language        = dlg.selected_language,
            device          = dlg.selected_device,
            compute_type    = dlg.selected_compute_type,
            source_duration = source_duration,
            parent          = self,
        )
        worker.vad_filter = dlg.selected_vad
        worker.segment_ready.connect(self.transcript_panel.add_segment)
        worker.progress.connect(self.transcript_panel.set_progress)
        worker.finished.connect(self._on_whisper_finished)
        worker.error.connect(self._on_whisper_error)
        worker.start()
        self._whisper_workers.append(worker)

        self.plugin.api.show_status_message("🎙 Transcription started…", 2000)

    def _on_whisper_finished(self, segments: list):
        n = len(segments)
        self._subtitle_segments = segments   # keep for export
        # Push to preview overlay
        self.preview.set_subtitle_segments(segments)
        self.preview.set_subtitle_style(self._subtitle_style)
        # Enable the subtitle toggle now there's something to show
        self._subs_visible = True
        self.btn_subs.setChecked(True)
        self.btn_subs.setEnabled(True)
        self.transcript_panel.set_status(f"{n} segment{chr(115) if n != 1 else chr(0)[:0]} transcribed")
        self.plugin.api.show_status_message(
            f"🎙 Transcription complete — {n} segment{chr(115) if n != 1 else chr(0)[:0]}", 3000
        )
        self._whisper_workers = [w for w in self._whisper_workers if w.isRunning()]

    def _toggle_subtitles(self):
        """Toggle subtitle overlay visibility without clearing the transcription."""
        # btn_subs is checkable — its checked state already flipped on click.
        # When called from the keyboard shortcut we flip both manually.
        if self.sender() is not self.btn_subs:
            # Called from shortcut — flip state and sync button
            self._subs_visible = not self._subs_visible
            self.btn_subs.setChecked(self._subs_visible)
        else:
            self._subs_visible = self.btn_subs.isChecked()

        self.preview.set_subtitles_visible(self._subs_visible)
        state = "on" if self._subs_visible else "off"
        self.plugin.api.show_status_message(f"💬 Subtitles {state}", 1500)

    def _on_whisper_error(self, message: str):
        self.transcript_panel.set_status(f"⚠ Error: {message}")
        self.transcript_panel.set_progress(1.0)
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.warning(self, "Transcription Failed", message)
        self._whisper_workers = [w for w in self._whisper_workers if w.isRunning()]

    def _open_subtitle_style(self):
        """Open subtitle style dialog and apply changes to preview + store for export."""
        dlg = SubtitleStyleDialog(initial=self._subtitle_style, parent=self)
        if dlg.exec() == SubtitleStyleDialog.DialogCode.Accepted:
            self._subtitle_style = dlg.style
            self.preview.set_subtitle_style(self._subtitle_style)
            self.plugin.api.show_status_message("🎨 Subtitle style updated", 2000)

    def _hide_transcript_panel(self):
        """Collapse the transcript panel back into the splitter."""
        self.transcript_panel.hide()
        sizes = self._upper_splitter.sizes()
        total = sum(sizes)
        self._upper_splitter.setSizes([sizes[0], total - sizes[0], 0])

    # =========================================================================
    # URL import
    # =========================================================================

    def _url_import(self):
        """Open the URL import dialog."""
        import os
        from .DownloadDialog import DownloadDialog

        # Default download dir — prefer ~/Videos, fall back to home
        default_dir = os.path.join(os.path.expanduser("~"), "Videos")
        if not os.path.exists(default_dir):
            default_dir = os.path.expanduser("~")

        def _on_downloaded(path: str):
            """Called by DownloadDialog when a file is ready."""
            self.media_bin.add_file(path)
            self.plugin.api.show_status_message(
                f"🌐 Downloaded: {os.path.basename(path)}", 3000
            )

        dlg = DownloadDialog(
            download_dir  = default_dir,
            on_downloaded = _on_downloaded,
            parent        = self,
        )
        dlg.exec()

    def _export(self):
        if not self._ffmpeg_ok:
            QMessageBox.warning(
                self, "FFmpeg Not Found",
                f"FFmpeg is required for export.\n\n{self._ffmpeg_msg}\n\n"
                "Install FFmpeg and ensure it is on your system PATH."
            )
            return

        if not self.project.clips:
            QMessageBox.information(
                self, "Nothing to Export",
                "Add some clips to the timeline before exporting."
            )
            return

        from .ExportDialog import ExportDialog
        dlg = ExportDialog(
            self.project,
            parent             = self,
            subtitle_segments  = self._subtitle_segments if self._subtitle_segments else None,
            subtitle_style     = self._subtitle_style,
        )
        dlg.exec()

    # =========================================================================
    # Status
    # =========================================================================

    def _set_status(self, msg: str):
        self.status_bar.setText(msg)

    def _refresh_status(self):
        n_clips = len(self.project.clips)
        dur     = self.project.duration_tc
        mod     = "●  " if self._modified else ""
        name    = self.project.name
        self.project_label.setText(f"{mod}{name}")
        self._set_status(
            f"{name}  •  {n_clips} clip{'s' if n_clips != 1 else ''}  •  {dur}"
            + (f"  •  {self._project_path}" if self._project_path else "  •  unsaved")
        )

    # =========================================================================
    # Player error recovery (suspend/resume, PipeWire disconnect)
    # =========================================================================

    def _on_player_error(self, error, error_string: str):
        """
        Handle QMediaPlayer errors — most critically audio device loss on
        system suspend/resume.  When PipeWire drops the connection Qt's
        multimedia thread crashes with QSocketNotifier warnings and a segfault.
        We catch the error, stop the player cleanly, then reconnect audio
        output on a short delay to give PipeWire time to recover.
        """
        from PyQt6.QtMultimedia import QMediaPlayer as _QMP
        if error == _QMP.Error.ResourceError:
            # Audio device lost — stop cleanly and reconnect after 1 second
            self.preview.player.stop()
            QTimer.singleShot(1000, self._reconnect_audio)
        # Log other errors to the status bar but don't crash
        elif error != _QMP.Error.NoError:
            self.plugin.api.show_status_message(
                f"⚠ Player error: {error_string}", 4000
            )

    def _reconnect_audio(self):
        """Reconnect QAudioOutput after a device loss (e.g. resume from suspend)."""
        try:
            from PyQt6.QtMultimedia import QAudioOutput
            new_audio = QAudioOutput(self)
            new_audio.setVolume(self.preview.audio_output.volume())
            self.preview.player.setAudioOutput(new_audio)
            self.preview.audio_output = new_audio
            self.plugin.api.show_status_message("🔊 Audio reconnected", 2000)
        except Exception as e:
            self.plugin.api.show_status_message(f"⚠ Audio reconnect failed: {e}", 3000)

    # =========================================================================
    # Sidecar — subtitle/transcript state alongside .vep project file
    # =========================================================================

    @staticmethod
    def _sidecar_path(project_path: str) -> str:
        return project_path + ".meta"

    def _save_sidecar(self, project_path: str):
        """
        Save subtitle segments, style and transcript panel visibility to a
        JSON sidecar file (<project>.vep.meta) alongside the project file.
        """
        from .WhisperWorker import TranscriptSegment
        segments_data = [
            {"start": s.start, "end": s.end, "text": s.text}
            for s in self._subtitle_segments
        ] if self._subtitle_segments else []

        s = self._subtitle_style
        style_data = {
            "font_size":    s.font_size,
            "font_weight":  s.font_weight,
            "font_family":  s.font_family,
            "text_color":   list(s.text_color),
            "outline_color":list(s.outline_color),
            "bg_color":     list(s.bg_color),
            "outline_width":s.outline_width,
            "bg_enabled":   s.bg_enabled,
            "position":     s.position,
            "margin":       s.margin,
        }

        meta = {
            "version":              1,
            "subtitle_segments":    segments_data,
            "subtitle_style":       style_data,
            "transcript_visible":   self.transcript_panel.isVisible(),
            "subs_visible":         self._subs_visible,
        }
        try:
            with open(self._sidecar_path(project_path), "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
        except OSError:
            pass   # sidecar is optional — never block a save

    def _load_sidecar(self, project_path: str):
        """
        Restore subtitle segments, style and transcript panel state from
        the sidecar file.  Silently ignored if the file doesn't exist.
        """
        path = self._sidecar_path(project_path)
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, json.JSONDecodeError):
            return

        # --- Subtitle segments ---
        from .WhisperWorker import TranscriptSegment
        segments = []
        for d in meta.get("subtitle_segments", []):
            try:
                segments.append(TranscriptSegment(
                    start=float(d["start"]),
                    end=float(d["end"]),
                    text=str(d["text"]),
                ))
            except (KeyError, ValueError):
                continue

        if segments:
            self._subtitle_segments = segments
            self.preview.set_subtitle_segments(segments)
            # Populate transcript panel
            self.transcript_panel.set_segments(segments)

        # --- Subtitle style ---
        sd = meta.get("subtitle_style", {})
        if sd:
            try:
                style = SubtitleStyle(
                    font_size    = int(sd.get("font_size",    22)),
                    font_weight  = str(sd.get("font_weight",  "Bold")),
                    font_family  = str(sd.get("font_family",  "Arial")),
                    text_color   = tuple(sd.get("text_color",   [255,255,255,255])),
                    outline_color= tuple(sd.get("outline_color",[0,0,0,255])),
                    bg_color     = tuple(sd.get("bg_color",     [0,0,0,140])),
                    outline_width= int(sd.get("outline_width", 2)),
                    bg_enabled   = bool(sd.get("bg_enabled",   False)),
                    position     = str(sd.get("position",      "Bottom Centre")),
                    margin       = int(sd.get("margin",        40)),
                )
                self._subtitle_style = style
                self.preview.set_subtitle_style(style)
            except Exception:
                pass

        # --- Transcript panel visibility ---
        if segments and meta.get("transcript_visible", False):
            self.transcript_panel.show()
            def _resize():
                sizes = self._upper_splitter.sizes()
                total = sum(sizes)
                panel_w   = min(300, max(240, total // 4))
                bin_w     = sizes[0] if sizes else 220
                preview_w = max(200, total - bin_w - panel_w)
                self._upper_splitter.setSizes([bin_w, preview_w, panel_w])
            QTimer.singleShot(0, _resize)

        # --- Subtitle toggle state ---
        self._subs_visible = meta.get("subs_visible", True)
        if segments:
            self.btn_subs.setEnabled(True)
            self.btn_subs.setChecked(self._subs_visible)
            self.preview.set_subtitles_visible(self._subs_visible)

    # =========================================================================
    # Cleanup
    # =========================================================================

    def cleanup(self):
        for w in self._whisper_workers:
            try:
                w.cancel()
                w.quit()
                w.wait(500)
            except Exception:
                pass
        self.preview.cleanup()
        self.media_bin.cleanup()