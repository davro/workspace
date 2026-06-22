"""
PreviewWidget — Video preview panel with Source / Timeline monitor modes.

SOURCE mode:   plays a single bin clip (raw source file).
TIMELINE mode: plays the assembled timeline sequence, switching clips
               automatically as the virtual playhead advances.
               The scrubber represents the full timeline duration.
               Gaps show a black screen with the player paused.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QSlider, QLabel, QSizePolicy
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import Qt, QUrl, QTimer, pyqtSignal

from .ClipModel import seconds_to_tc, Clip, TrackType
from .SubtitleOverlay import SubtitleOverlay
from .SubtitleStyle import SubtitleStyle

_UNSET = object()  # sentinel for _tl_clip — distinct from None

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

PREVIEW_STYLE = """
QWidget#PreviewContainer {
    background: #111111;
}
QVideoWidget {
    background: #000000;
}
QWidget#ModeBar {
    background: #161616;
    border-bottom: 1px solid #222222;
}
QPushButton#ModeBtn {
    background: #252525;
    border: 1px solid #333333;
    color: #777777;
    font-size: 11px;
    font-weight: bold;
    padding: 3px 14px;
    min-height: 22px;
}
QPushButton#ModeBtn:first-child {
    border-radius: 3px 0 0 3px;
    border-right: none;
}
QPushButton#ModeBtn:last-child {
    border-radius: 0 3px 3px 0;
}
QPushButton#ModeBtn[active="true"] {
    background: #1E3A5F;
    border-color: #4A90D9;
    color: #FFFFFF;
}
QPushButton#ModeBtn:hover:!pressed {
    background: #2D2D2D;
    color: #CCCCCC;
}
QLabel#ModeLabel {
    color: #555555;
    font-size: 10px;
    letter-spacing: 1px;
    padding: 0 10px;
}
QWidget#ControlBar {
    background: #1A1A1A;
    border-top: 1px solid #2A2A2A;
}
QPushButton#TransportBtn {
    background: transparent;
    border: none;
    color: #CCCCCC;
    font-size: 16px;
    padding: 4px 8px;
    border-radius: 4px;
    min-width: 32px;
    min-height: 32px;
}
QPushButton#TransportBtn:hover  { background: #2D2D2D; color: #FFFFFF; }
QPushButton#TransportBtn:pressed{ background: #3A3A3A; }
QSlider#Scrubber::groove:horizontal {
    height: 4px; background: #333333; border-radius: 2px;
}
QSlider#Scrubber::sub-page:horizontal {
    background: #4A90D9; border-radius: 2px;
}
QSlider#Scrubber::handle:horizontal {
    width: 12px; height: 12px; margin: -4px 0;
    border-radius: 6px; background: #FFFFFF;
}
QSlider#Scrubber::handle:horizontal:hover { background: #4A90D9; }
QSlider#VolumeSlider::groove:horizontal {
    height: 3px; background: #333333; border-radius: 2px;
}
QSlider#VolumeSlider::sub-page:horizontal {
    background: #666666; border-radius: 2px;
}
QSlider#VolumeSlider::handle:horizontal {
    width: 10px; height: 10px; margin: -4px 0;
    border-radius: 5px; background: #AAAAAA;
}
QLabel#TimeLabel {
    color: #AAAAAA;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    padding: 0 6px;
}
QLabel#NoMediaLabel {
    color: #444444;
    font-size: 14px;
    background: #111111;
}
"""

# How often (ms) the timeline engine ticks to check clip transitions
TIMELINE_TICK_MS = 80


class PreviewWidget(QWidget):
    """
    Dual-mode preview:
      SOURCE   — load_source(path) plays one file, scrubber = that file's duration
      TIMELINE — play_timeline(project) plays the full assembled sequence,
                 scrubber = full project duration, clips auto-switch on playback
    """

    # Emits virtual timeline position in seconds (for timeline playhead sync)
    position_changed = pyqtSignal(float)

    MODE_SOURCE   = "source"
    MODE_TIMELINE = "timeline"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PreviewContainer")
        self.setStyleSheet(PREVIEW_STYLE)

        # Shared state
        self._mode           = self.MODE_SOURCE
        self._scrubbing      = False
        self._current_source = None   # path currently loaded in player

        # Source-mode state
        self._source_duration = 0.0

        # Timeline-mode state
        self._project        = None   # Project reference
        self._tl_position    = 0.0   # virtual playhead (seconds in project timeline)
        self._tl_duration    = 0.0   # total project duration
        self._tl_playing     = False
        self._tl_clip        = _UNSET  # currently active Clip (_UNSET = never evaluated)
        self._tl_clip_offset = 0.0   # seconds into current source file
        self._tl_timer       = QTimer(self)
        self._tl_timer.setInterval(TIMELINE_TICK_MS)
        self._tl_timer.timeout.connect(self._tl_tick)
        self._tl_last_tick_ms = 0    # QElapsedTimer alternative via QTimer

        self._setup_player()
        self._build_ui()
        self._connect_signals()
        self._subtitle_overlay: SubtitleOverlay | None = None

    # =========================================================================
    # Player setup
    # =========================================================================

    def _setup_player(self):
        self.player       = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.8)

    # =========================================================================
    # UI
    # =========================================================================

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- Mode bar ----
        mode_bar = QWidget()
        mode_bar.setObjectName("ModeBar")
        mode_bar.setFixedHeight(32)
        mb_layout = QHBoxLayout(mode_bar)
        mb_layout.setContentsMargins(8, 4, 8, 4)
        mb_layout.setSpacing(0)

        self.btn_source   = QPushButton("SOURCE")
        self.btn_timeline = QPushButton("TIMELINE")
        for b in (self.btn_source, self.btn_timeline):
            b.setObjectName("ModeBtn")
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setCheckable(False)

        self.btn_source.clicked.connect(lambda: self.set_mode(self.MODE_SOURCE))
        self.btn_timeline.clicked.connect(lambda: self.set_mode(self.MODE_TIMELINE))

        mb_layout.addStretch()
        mb_layout.addWidget(self.btn_source)
        mb_layout.addWidget(self.btn_timeline)
        mb_layout.addStretch()

        # Mode label (right side)
        self._mode_label = QLabel("SOURCE")
        self._mode_label.setObjectName("ModeLabel")
        mb_layout.addWidget(self._mode_label)

        root.addWidget(mode_bar)

        # ---- Video area ----
        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumHeight(160)
        self.video_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.video_widget.setStyleSheet("background:#000;")
        self.player.setVideoOutput(self.video_widget)
        root.addWidget(self.video_widget, stretch=1)

        # Subtitle overlay
        self._subtitle_overlay = SubtitleOverlay(self.video_widget)
        self._subtitle_overlay.resize(self.video_widget.size())
        self._subtitle_overlay.show()

        # No-media placeholder
        self.no_media_label = QLabel("No media loaded\nImport a clip to begin")
        self.no_media_label.setObjectName("NoMediaLabel")
        self.no_media_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.no_media_label, stretch=1)
        self.video_widget.hide()
        self.no_media_label.show()

        # ---- Scrubber ----
        scrub_bar = QWidget()
        scrub_bar.setFixedHeight(22)
        sb_layout = QHBoxLayout(scrub_bar)
        sb_layout.setContentsMargins(8, 0, 8, 0)
        self.scrubber = QSlider(Qt.Orientation.Horizontal)
        self.scrubber.setObjectName("Scrubber")
        self.scrubber.setRange(0, 10000)
        self.scrubber.setValue(0)
        sb_layout.addWidget(self.scrubber)
        root.addWidget(scrub_bar)

        # ---- Control bar ----
        ctrl_bar = QWidget()
        ctrl_bar.setObjectName("ControlBar")
        ctrl_bar.setFixedHeight(50)
        cl = QHBoxLayout(ctrl_bar)
        cl.setContentsMargins(8, 4, 8, 4)
        cl.setSpacing(2)

        def _btn(icon, tip):
            b = QPushButton(icon)
            b.setObjectName("TransportBtn")
            b.setToolTip(tip)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            return b

        self.btn_goto_start = _btn("⏮", "Go to Start")
        self.btn_prev_frame = _btn("⏪", "Previous Frame")
        self.btn_play_pause = _btn("▶", "Play / Pause  [Space]")
        self.btn_next_frame = _btn("⏩", "Next Frame")
        self.btn_goto_end   = _btn("⏭", "Go to End")
        self.btn_play_pause.setStyleSheet(
            "QPushButton#TransportBtn { font-size: 20px; }"
        )

        for w in (self.btn_goto_start, self.btn_prev_frame, None,
                  self.btn_play_pause, None,
                  self.btn_next_frame, self.btn_goto_end):
            if w is None:
                cl.addSpacing(4)
            else:
                cl.addWidget(w)

        cl.addStretch()

        self.lbl_current  = QLabel("00:00:00.00")
        self.lbl_current.setObjectName("TimeLabel")
        self.lbl_current.setStyleSheet("color:#FFF; font-size:13px; padding:0 6px;")
        self.lbl_sep      = QLabel("/")
        self.lbl_sep.setStyleSheet("color:#555; padding:0 2px;")
        self.lbl_duration = QLabel("00:00:00.00")
        self.lbl_duration.setObjectName("TimeLabel")

        for w in (self.lbl_current, self.lbl_sep, self.lbl_duration):
            cl.addWidget(w)

        cl.addStretch()

        vol_icon = QLabel("🔊")
        vol_icon.setStyleSheet("color:#666; font-size:13px; padding-right:2px;")
        cl.addWidget(vol_icon)
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setObjectName("VolumeSlider")
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(80)
        self.vol_slider.setFixedWidth(70)
        cl.addWidget(self.vol_slider)

        root.addWidget(ctrl_bar)

        self._update_mode_buttons()

    def _connect_signals(self):
        # Player signals (used in both modes)
        self.player.durationChanged.connect(self._on_player_duration_changed)
        self.player.positionChanged.connect(self._on_player_position_changed)
        self.player.playbackStateChanged.connect(self._on_playback_state_changed)
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)

        # Transport buttons
        self.btn_play_pause.clicked.connect(self.toggle_play)
        self.btn_goto_start.clicked.connect(self.goto_start)
        self.btn_goto_end.clicked.connect(self.goto_end)
        self.btn_prev_frame.clicked.connect(self.prev_frame)
        self.btn_next_frame.clicked.connect(self.next_frame)

        # Scrubber
        self.scrubber.sliderPressed.connect(self._scrub_start)
        self.scrubber.sliderReleased.connect(self._scrub_end)
        self.scrubber.sliderMoved.connect(self._scrub_move)

        # Volume
        self.vol_slider.valueChanged.connect(
            lambda v: self.audio_output.setVolume(v / 100.0)
        )

    # =========================================================================
    # Mode switching
    # =========================================================================

    def set_mode(self, mode: str):
        """Switch between SOURCE and TIMELINE modes."""
        if mode == self._mode:
            return

        # Stop everything cleanly
        self._tl_stop()
        self.player.stop()

        self._mode = mode
        self._update_mode_buttons()

        if mode == self.MODE_SOURCE:
            self._mode_label.setText("SOURCE")
            # Clear timeline state, restore source if any
            if self._current_source:
                self.player.setSource(QUrl.fromLocalFile(self._current_source))
                self.video_widget.show()
                self.no_media_label.hide()
            else:
                self.no_media_label.show()
                self.video_widget.hide()
            self.scrubber.setValue(0)

        else:  # TIMELINE
            self._mode_label.setText("TIMELINE")
            if self._project and self._project.duration > 0:
                self._tl_duration = self._live_duration()
                self.lbl_duration.setText(seconds_to_tc(self._tl_duration))
                self._tl_seek(0.0)
            else:
                self.no_media_label.setText(
                    "No clips on timeline\nAdd clips to use Timeline mode"
                )
                self.no_media_label.show()
                self.video_widget.hide()
                self.lbl_duration.setText("00:00:00.00")

    def _update_mode_buttons(self):
        src_active = self._mode == self.MODE_SOURCE
        self.btn_source.setProperty("active", "true" if src_active else "false")
        self.btn_timeline.setProperty("active", "false" if src_active else "true")
        # Force style refresh
        for b in (self.btn_source, self.btn_timeline):
            b.style().unpolish(b)
            b.style().polish(b)

    # =========================================================================
    # Public API — Source mode
    # =========================================================================

    def load_source(self, path: str):
        """Load a file for SOURCE mode preview (called from bin click)."""
        self._current_source = path
        if self._mode == self.MODE_SOURCE:
            self.player.setSource(QUrl.fromLocalFile(path))
            self.video_widget.show()
            self.no_media_label.hide()

    def clear(self):
        self._tl_stop()
        self.player.stop()
        self.player.setSource(QUrl())
        self._current_source = None
        self._tl_position    = 0.0
        self.scrubber.setValue(0)
        self.lbl_current.setText("00:00:00.00")
        self.lbl_duration.setText("00:00:00.00")
        self.btn_play_pause.setText("▶")
        self.video_widget.hide()
        self.no_media_label.setText("No media loaded\nImport a clip to begin")
        self.no_media_label.show()

    # =========================================================================
    # Public API — Timeline mode
    # =========================================================================

    def set_project(self, project):
        """Give the preview a reference to the current Project."""
        self._project     = project
        self._tl_duration = project.duration if project else 0.0
        if self._mode == self.MODE_TIMELINE:
            self.lbl_duration.setText(seconds_to_tc(self._tl_duration))

    def _live_duration(self) -> float:
        if self._project:
            return self._project.duration
        return self._tl_duration

    def timeline_seek(self, seconds: float):
        """
        Seek the timeline monitor to `seconds`.
        Called by VideoEditorWidget when the user clicks the timeline ruler.
        Switches to Timeline mode automatically if not already there.
        """
        if self._mode != self.MODE_TIMELINE:
            self.set_mode(self.MODE_TIMELINE)
        self._tl_seek(seconds)

    # =========================================================================
    # Transport (work in both modes)
    # =========================================================================

    def toggle_play(self):
        if self._mode == self.MODE_TIMELINE:
            if self._tl_playing:
                self._tl_pause()
            else:
                self._tl_play()
        else:
            state = self.player.playbackState()
            if state == QMediaPlayer.PlaybackState.PlayingState:
                self.player.pause()
            else:
                self.player.play()

    def goto_start(self):
        if self._mode == self.MODE_TIMELINE:
            self._tl_seek(0.0)
        else:
            self.player.setPosition(0)

    def goto_end(self):
        if self._mode == self.MODE_TIMELINE:
            self._tl_seek(self._tl_duration)
        else:
            self.player.setPosition(self.player.duration())

    def prev_frame(self):
        if self._mode == self.MODE_TIMELINE:
            fps = self._project.fps if self._project else 25.0
            self._tl_seek(max(0.0, self._tl_position - 1.0 / fps))
        else:
            self.player.setPosition(max(0, self.player.position() - 40))

    def next_frame(self):
        if self._mode == self.MODE_TIMELINE:
            fps = self._project.fps if self._project else 25.0
            self._tl_seek(min(self._tl_duration, self._tl_position + 1.0 / fps))
        else:
            self.player.setPosition(
                min(self.player.duration(), self.player.position() + 40)
            )

    def seek_to(self, seconds: float):
        """Legacy seek used by VideoEditorWidget — routes to correct mode."""
        if self._mode == self.MODE_TIMELINE:
            self._tl_seek(seconds)
        else:
            self.player.setPosition(int(seconds * 1000))

    # =========================================================================
    # Timeline engine
    # =========================================================================

    def _tl_play(self):
        """Start timeline playback."""
        if not self._project or self._live_duration() <= 0:
            return
        dur = self._live_duration()
        self._tl_duration = dur
        if self._tl_position >= dur:
            self._tl_seek(0.0)
        self._tl_playing = True
        self.btn_play_pause.setText("⏸")

        clip = self._clip_at(self._tl_position)
        if clip:
            offset = self._tl_position - clip.timeline_position + clip.in_point
            self._load_clip(clip, offset)
            self.player.play()
        else:
            self.player.stop()
            self._current_source = None
            self.video_widget.hide()
            self.no_media_label.setText("◼  Gap")
            self.no_media_label.show()

        self._tl_clip = _UNSET
        self._tl_last_wall = _wall_ms()
        self._tl_timer.start()

    def _tl_pause(self):
        self._tl_playing = False
        self._tl_timer.stop()
        self.player.pause()
        self.btn_play_pause.setText("▶")

    def _tl_stop(self):
        self._tl_playing = False
        self._tl_timer.stop()
        self._tl_clip = None

    def _tl_seek(self, seconds: float):
        """Jump timeline virtual playhead to `seconds`."""
        dur = self._live_duration()
        self._tl_duration = dur
        seconds = max(0.0, min(seconds, dur))
        self._tl_position = seconds
        self._tl_clip = _UNSET

        self.lbl_duration.setText(seconds_to_tc(dur))
        self._update_tl_scrubber()
        self.lbl_current.setText(seconds_to_tc(seconds))
        self.position_changed.emit(seconds)
        if self._subtitle_overlay:
            self._subtitle_overlay.update_position(seconds)

        clip = self._clip_at(seconds)
        if clip:
            offset = (seconds - clip.timeline_position) + clip.in_point
            self._load_clip(clip, offset)
            if self._tl_playing:
                self.player.play()
        else:
            self.player.stop()
            self._current_source = None
            self.video_widget.hide()
            self.no_media_label.setText("◼  Gap")
            self.no_media_label.show()

        self._tl_last_wall = _wall_ms()

    def _tl_tick(self):
        if not self._tl_playing:
            return

        now     = _wall_ms()
        elapsed = (now - self._tl_last_wall) / 1000.0
        self._tl_last_wall = now
        new_pos = self._tl_position + elapsed

        dur = self._live_duration()
        self._tl_duration = dur

        if new_pos >= dur:
            self._tl_seek(dur)
            self._tl_pause()
            return

        self._tl_position = new_pos
        self._update_tl_scrubber()
        self.lbl_current.setText(seconds_to_tc(self._tl_position))
        self.position_changed.emit(self._tl_position)
        if self._subtitle_overlay:
            self._subtitle_overlay.update_position(self._tl_position)

        clip_now = self._clip_at(self._tl_position)
        if clip_now is not self._tl_clip:
            if clip_now:
                offset = (self._tl_position - clip_now.timeline_position) + clip_now.in_point
                self._load_clip(clip_now, offset)
                self.player.play()
            else:
                self.player.stop()
                self._current_source = None
                self.video_widget.hide()
                self.no_media_label.setText("◼  Gap")
                self.no_media_label.show()
                self._tl_clip = None

    def _load_clip(self, clip: Clip, offset_seconds: float):
        """
        Load a clip into the player and seek to offset_seconds.

        _current_source is set to None whenever we enter a gap, so even if
        the next clip shares the same source file we always call setSource —
        this is the only reliable way to seek after player.stop().
        Seeking is deferred to _on_media_status_changed (BufferedMedia) because
        setPosition on LoadedMedia fires too early and gets ignored by Qt.
        """
        self._pending_seek_ms  = int(offset_seconds * 1000)
        self._pending_play     = self._tl_playing   # remember if we should autoplay

        if self._current_source != clip.source_path:
            self._current_source = clip.source_path
            self.player.setSource(QUrl.fromLocalFile(clip.source_path))
            # Seek happens in _on_media_status_changed once BufferedMedia fires
        else:
            # Same source, player still loaded — seek immediately and play
            self.player.setPosition(self._pending_seek_ms)
            self._pending_seek_ms = None
            if self._tl_playing:
                self.player.play()

        self.video_widget.show()
        self.no_media_label.hide()
        self._tl_clip = clip

    def _clip_at(self, seconds: float):
        """
        Return the video Clip that should be VISIBLE at `seconds`.

        With multiple V tracks, higher track_index = higher stacking layer
        (V2 overlays V1, matching the timeline's visual order and the
        export compositing order). We return the topmost track that has
        a clip covering this position, falling back to lower tracks if
        the top one is empty here (a "gap" on V2 reveals V1 underneath).
        """
        if not self._project:
            return None

        candidates = [
            c for c in self._project.clips
            if c.track_type == TrackType.VIDEO
            and c.timeline_position <= seconds < c.timeline_end
        ]
        if not candidates:
            return None

        # Highest track_index wins (topmost layer)
        return max(candidates, key=lambda c: c.track_index)

    def _update_tl_scrubber(self):
        if self._tl_duration > 0:
            val = int((self._tl_position / self._tl_duration) * 10000)
            self.scrubber.blockSignals(True)
            self.scrubber.setValue(val)
            self.scrubber.blockSignals(False)

    # =========================================================================
    # Player signal handlers
    # =========================================================================

    def _on_player_duration_changed(self, duration_ms: int):
        if self._mode == self.MODE_SOURCE:
            self._source_duration = duration_ms / 1000.0
            self.lbl_duration.setText(seconds_to_tc(self._source_duration))

    def _on_player_position_changed(self, position_ms: int):
        if self._scrubbing:
            return
        if self._mode == self.MODE_SOURCE:
            seconds = position_ms / 1000.0
            self.lbl_current.setText(seconds_to_tc(seconds))
            if self._source_duration > 0:
                val = int((seconds / self._source_duration) * 10000)
                self.scrubber.blockSignals(True)
                self.scrubber.setValue(val)
                self.scrubber.blockSignals(False)
            self.position_changed.emit(seconds)
            if self._subtitle_overlay:
                self._subtitle_overlay.update_position(seconds)
        # In TIMELINE mode the tick loop manages position — ignore player pos events

    def _on_playback_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.btn_play_pause.setText("⏸")
        else:
            if not self._tl_playing:
                self.btn_play_pause.setText("▶")

    def _on_media_status_changed(self, status):
        """After a source change, seek to the pending position once buffered.

        BufferedMedia is used instead of LoadedMedia — LoadedMedia fires before
        Qt is ready to honour setPosition, causing playback to start from 0.
        BufferedMedia fires once enough data is buffered to seek reliably.
        """
        if status == QMediaPlayer.MediaStatus.BufferedMedia:
            if hasattr(self, "_pending_seek_ms") and self._pending_seek_ms is not None:
                self.player.setPosition(self._pending_seek_ms)
                self._pending_seek_ms = None
                if getattr(self, "_pending_play", False) and self._tl_playing:
                    self.player.play()
                    self._pending_play = False

    # =========================================================================
    # Scrubber handlers
    # =========================================================================

    def _scrub_start(self):
        self._scrubbing = True
        if self._mode == self.MODE_TIMELINE:
            self._tl_timer.stop()

    def _scrub_end(self):
        self._scrubbing = False
        val = self.scrubber.value()
        if self._mode == self.MODE_TIMELINE:
            if self._tl_duration > 0:
                self._tl_seek((val / 10000.0) * self._tl_duration)
            if self._tl_playing:
                self._tl_timer.start()
        else:
            if self._source_duration > 0:
                seconds = (val / 10000.0) * self._source_duration
                self.player.setPosition(int(seconds * 1000))

    def _scrub_move(self, value: int):
        if self._mode == self.MODE_TIMELINE:
            if self._tl_duration > 0:
                seconds = (value / 10000.0) * self._tl_duration
                self.lbl_current.setText(seconds_to_tc(seconds))
                # Don't seek player during scrub — just update label + pos
                self._tl_position = seconds
                self.position_changed.emit(seconds)
        else:
            if self._source_duration > 0:
                seconds = (value / 10000.0) * self._source_duration
                self.lbl_current.setText(seconds_to_tc(seconds))
                self.player.setPosition(int(seconds * 1000))
                self.position_changed.emit(seconds)

    # =========================================================================
    # Cleanup
    # =========================================================================

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._subtitle_overlay and self.video_widget:
            self._subtitle_overlay.resize(self.video_widget.size())

    def set_subtitle_segments(self, segments: list):
        if self._subtitle_overlay:
            self._subtitle_overlay.set_segments(segments)

    def set_subtitle_style(self, style):
        if self._subtitle_overlay:
            self._subtitle_overlay.set_style(style)

    def clear_subtitles(self):
        if self._subtitle_overlay:
            self._subtitle_overlay.clear_segments()

    def set_subtitles_visible(self, visible: bool):
        if self._subtitle_overlay:
            self._subtitle_overlay.set_subtitles_visible(visible)

    def cleanup(self):
        self._tl_timer.stop()
        self.player.stop()


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _wall_ms() -> int:
    """Current wall-clock time in milliseconds."""
    import time
    return int(time.monotonic() * 1000)