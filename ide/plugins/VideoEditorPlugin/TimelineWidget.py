"""
TimelineWidget — QGraphicsView-based multi-track NLE timeline.

Supports:
- Multiple V (video) and A (audio) tracks, added/removed dynamically
- Clips draggable horizontally (reposition in time) AND vertically
  (move between tracks of the same type)
- Per-track mute / lock controls
- Adaptive zoom, ruler, playhead
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGraphicsView,
    QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem,
    QGraphicsLineItem, QLabel, QPushButton, QScrollBar,
    QSizePolicy, QMenu, QGraphicsItem, QGraphicsProxyWidget,
    QToolButton, QFrame, QInputDialog
)
from PyQt6.QtCore import (
    Qt, QRectF, QPointF, pyqtSignal, QTimer
)
from PyQt6.QtGui import (
    QColor, QPen, QBrush, QFont, QPainter, QLinearGradient,
    QCursor, QAction
)

from .ClipModel import (
    Clip, Track, Project, TrackType, ClipType,
    seconds_to_tc, next_clip_colour
)

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

TRACK_HEIGHT   = 44       # px per track row
HEADER_WIDTH   = 84       # px for track name column on left (wider — has buttons now)
RULER_HEIGHT   = 24       # px for time ruler at top
MIN_CLIP_WIDTH = 4        # px — minimum visual width before label hidden
PIXELS_PER_SEC = 80.0     # default zoom (pixels per second of media)

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------

C_BG           = QColor("#1A1A1A")
C_TRACK_EVEN_V = QColor("#1E2730")   # video tracks — cool tint
C_TRACK_ODD_V  = QColor("#1B232B")
C_TRACK_EVEN_A = QColor("#231E2A")   # audio tracks — warm/purple tint
C_TRACK_ODD_A  = QColor("#201C26")
C_TRACK_BORDER = QColor("#2A2A2A")
C_RULER_BG     = QColor("#161616")
C_RULER_TICK   = QColor("#444444")
C_RULER_TEXT   = QColor("#777777")
C_PLAYHEAD     = QColor("#E04040")
C_CLIP_BORDER  = QColor("#000000")
C_CLIP_LABEL   = QColor("#FFFFFF")
C_SELECTED     = QColor("#FFD700")
C_HEADER_BG    = QColor("#161616")
C_HEADER_TEXT  = QColor("#888888")
C_MUTED_OVERLAY = QColor(0, 0, 0, 140)
C_DROP_HINT    = QColor("#4A90D9")


# ---------------------------------------------------------------------------
# ClipItem — a clip rectangle on the scene
# ---------------------------------------------------------------------------

class ClipItem(QGraphicsRectItem):
    """
    Draggable clip block on the timeline.

    Supports:
    - Horizontal drag → retime (change timeline_position)
    - Vertical drag → move to a different track of the SAME type
    - Left/right edge drag → trim in_point / out_point

    Trim zones: the leftmost and rightmost TRIM_ZONE_PX pixels of the clip
    rect act as resize handles. The cursor changes to a resize arrow when
    hovering over them, and a drag from that zone trims rather than moves.
    """

    TRIM_ZONE_PX = 8   # width of the hot-zone at each edge

    # Internal drag mode
    _MODE_MOVE       = "move"
    _MODE_TRIM_START = "trim_start"
    _MODE_TRIM_END   = "trim_end"

    def __init__(self, clip: Clip, scene_ref, parent=None):
        self._scene_ref = scene_ref
        track_y = scene_ref.track_y_for(clip.track_type, clip.track_index)

        x = HEADER_WIDTH + clip.timeline_position * scene_ref.pps
        y = RULER_HEIGHT + track_y
        w = max(MIN_CLIP_WIDTH, clip.source_duration * scene_ref.pps)
        h = TRACK_HEIGHT - 2

        super().__init__(QRectF(0, 0, w, h), parent)
        self.setPos(x, y)

        self.clip = clip
        self.pps  = scene_ref.pps

        self._drag_mode      = self._MODE_MOVE
        self._drag_start_x   = 0.0   # scene X at press
        self._orig_tl_pos    = 0.0   # clip.timeline_position at press
        self._orig_in_point  = 0.0   # clip.in_point at press
        self._orig_out_point = 0.0   # clip.out_point at press

        self._build_appearance(w, h)

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))

    # ------------------------------------------------------------------
    # Appearance
    # ------------------------------------------------------------------

    def _build_appearance(self, w: float, h: float):
        colour = QColor(self.clip.color)
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, colour.lighter(130))
        grad.setColorAt(1.0, colour)
        self.setBrush(QBrush(grad))
        self.setPen(QPen(C_CLIP_BORDER, 1))

        self._label = QGraphicsTextItem(self.clip.display_name, self)
        self._label.setDefaultTextColor(C_CLIP_LABEL)
        font = QFont("Segoe UI", 8)
        font.setBold(True)
        self._label.setFont(font)
        self._label.setPos(4, (h - self._label.boundingRect().height()) / 2)
        self._label.setTextWidth(max(4, w - 8))

    def _rebuild(self):
        """Recompute geometry after a trim and update child label."""
        w = max(MIN_CLIP_WIDTH, self.clip.source_duration * self.pps)
        h = TRACK_HEIGHT - 2
        self.setRect(QRectF(0, 0, w, h))
        self._build_appearance(w, h)

    # ------------------------------------------------------------------
    # Hover — change cursor when over trim zones
    # ------------------------------------------------------------------

    def _trim_mode_at(self, local_x: float) -> str:
        w = self.rect().width()
        if local_x <= self.TRIM_ZONE_PX:
            return self._MODE_TRIM_START
        if local_x >= w - self.TRIM_ZONE_PX:
            return self._MODE_TRIM_END
        return self._MODE_MOVE

    def hoverMoveEvent(self, event):
        mode = self._trim_mode_at(event.pos().x())
        if mode in (self._MODE_TRIM_START, self._MODE_TRIM_END):
            self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        super().hoverLeaveEvent(event)

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        local_x = event.pos().x()
        self._drag_mode      = self._trim_mode_at(local_x)
        self._drag_start_x   = event.scenePos().x()
        self._orig_tl_pos    = self.clip.timeline_position
        self._orig_in_point  = self.clip.in_point
        self._orig_out_point = self.clip.out_point

        if self._drag_mode == self._MODE_MOVE:
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            # Let QGraphicsItem handle normal move drag
            super().mousePressEvent(event)
        else:
            # Trim drag: we handle it ourselves, don't call super
            # (super would start a move drag which conflicts)
            self.setSelected(True)
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_mode == self._MODE_MOVE:
            super().mouseMoveEvent(event)
            return

        # --- Trim drag ---
        delta_px  = event.scenePos().x() - self._drag_start_x
        delta_sec = delta_px / self.pps

        if self._drag_mode == self._MODE_TRIM_START:
            new_in = self._orig_in_point + delta_sec
            # Clamp: can't trim past timeline start or past out_point
            max_in = self._orig_out_point - Clip.MIN_CLIP_DURATION
            new_in = max(0.0, min(new_in, max_in))
            # Apply to data model
            in_delta = new_in - self.clip.in_point
            self.clip.in_point          = new_in
            self.clip.timeline_position += in_delta
            # Reposition the item on screen
            new_scene_x = HEADER_WIDTH + self.clip.timeline_position * self.pps
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, False)
            self.setX(new_scene_x)
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

        elif self._drag_mode == self._MODE_TRIM_END:
            new_out = self._orig_out_point + delta_sec
            min_out = self._orig_in_point + Clip.MIN_CLIP_DURATION
            new_out = max(min_out, min(new_out, self.clip.media_duration))
            self.clip.out_point = new_out

        # Update visual width
        w = max(MIN_CLIP_WIDTH, self.clip.source_duration * self.pps)
        self.setRect(QRectF(0, 0, w, TRACK_HEIGHT - 2))
        self._label.setTextWidth(max(4, w - 8))
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._drag_mode == self._MODE_MOVE:
            super().mouseReleaseEvent(event)
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))

            # Commit horizontal position
            new_x = self.pos().x()
            self.clip.timeline_position = max(0.0, (new_x - HEADER_WIDTH) / self.pps)

            # Commit vertical position → which track did we land on?
            track_index = self._scene_ref.track_index_at_y(
                self.clip.track_type, self.pos().y()
            )
            if track_index is not None:
                self.clip.track_index = track_index
        else:
            # Trim done — rebuild appearance for cleanliness
            self._rebuild()
            self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
            event.accept()

        self._scene_ref.clip_moved.emit(self.clip)

    # ------------------------------------------------------------------
    # itemChange — only used during MOVE drags
    # ------------------------------------------------------------------

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            if self._drag_mode != self._MODE_MOVE:
                return value   # let trim handle its own positioning
            new_pos = QPointF(value)
            new_x   = max(HEADER_WIDTH, new_pos.x())
            snapped_y = self._scene_ref.snap_y_for_drag(
                self.clip.track_type, new_pos.y()
            )
            return QPointF(new_x, snapped_y)

        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedChange:
            self.setPen(QPen(C_SELECTED if value else C_CLIP_BORDER,
                              2 if value else 1))

        return super().itemChange(change, value)

    # ------------------------------------------------------------------
    # Zoom update
    # ------------------------------------------------------------------

    def update_pps(self, pps: float):
        """Re-layout clip when zoom changes."""
        self.pps = pps
        track_y = self._scene_ref.track_y_for(self.clip.track_type, self.clip.track_index)
        x = HEADER_WIDTH + self.clip.timeline_position * pps
        y = RULER_HEIGHT + track_y
        w = max(MIN_CLIP_WIDTH, self.clip.source_duration * pps)
        self.setPos(x, y)
        self.setRect(QRectF(0, 0, w, TRACK_HEIGHT - 2))
        self._label.setTextWidth(max(4, w - 8))

    # ------------------------------------------------------------------
    # Context menu — right-click
    # ------------------------------------------------------------------

    def contextMenuEvent(self, event):
        clip = self.clip

        from pathlib import Path as _Path
        from .ClipModel import ClipType as _CT, seconds_to_tc as _tc

        # Click position and playhead position in seconds
        click_seconds    = max(0.0, (event.scenePos().x() - HEADER_WIDTH) / self.pps)
        playhead_seconds = self._scene_ref.get_playhead_seconds()

        type_label = {
            _CT.VIDEO: "🎬 Video",
            _CT.AUDIO: "🎵 Audio",
            _CT.IMAGE: "🖼 Image",
        }.get(clip.clip_type, clip.clip_type)

        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background: #1E1E1E;
                border: 1px solid #3A3A3A;
                border-radius: 4px;
                color: #CCCCCC;
                font-size: 12px;
                padding: 4px 0;
            }
            QMenu::item { padding: 5px 18px 5px 12px; }
            QMenu::item:selected { background: #2A4A70; color: #FFFFFF; }
            QMenu::item:disabled { color: #555555; }
            QMenu::separator { height: 1px; background: #333333; margin: 3px 8px; }
        """)

        def _info(text: str):
            a = QAction(text, menu)
            a.setEnabled(False)
            menu.addAction(a)

        # ---- Info header ----
        _info(f"  {clip.display_name}")
        menu.addSeparator()
        _info(f"  {type_label}")
        _info(f"  Source duration   {_tc(clip.media_duration)}")
        _info(f"  In point          {_tc(clip.in_point)}")
        _info(f"  Out point         {_tc(clip.out_point)}")
        _info(f"  Trimmed duration  {_tc(clip.source_duration)}")
        _info(f"  Timeline pos      {_tc(clip.timeline_position)}")
        _info(f"  Track             {clip.track_type.upper()} {clip.track_index + 1}")

        menu.addSeparator()

        # ---- Split here (at right-click position) ----
        can_split_here = (clip.timeline_position + 0.1 < click_seconds <
                          clip.timeline_end - 0.1)
        act_split_here = QAction(f"✂  Split here  ({_tc(click_seconds)})", menu)
        act_split_here.setEnabled(can_split_here)
        menu.addAction(act_split_here)

        # ---- Split at playhead ----
        can_split_playhead = (clip.timeline_position + 0.1 < playhead_seconds <
                              clip.timeline_end - 0.1)
        act_split_playhead = QAction(f"✂  Split at playhead  ({_tc(playhead_seconds)})", menu)
        act_split_playhead.setEnabled(can_split_playhead)
        menu.addAction(act_split_playhead)

        act_rename = QAction("✏  Rename clip…", menu)
        menu.addAction(act_rename)

        menu.addSeparator()

        act_delete = QAction("🗑  Delete clip", menu)
        menu.addAction(act_delete)

        # screenPos() returns QPoint directly in PyQt6 — no .toPoint() needed
        chosen = menu.exec(event.screenPos())

        def _do_split(split_at: float):
            right = self._scene_ref.project.split_clip(clip.clip_id, split_at)
            if right is not None:
                for ci in self._scene_ref._clip_items.values():
                    ci.update_pps(self.pps)
                ci_right = ClipItem(right, self._scene_ref)
                self._scene_ref.addItem(ci_right)
                self._scene_ref._clip_items[right.clip_id] = ci_right
                self._scene_ref.clip_split.emit(right)
                self._scene_ref.track_changed.emit()

        if chosen == act_split_here:
            _do_split(click_seconds)
            # Move playhead to the split point so the preview engine re-evaluates
            # its clip state — without this the playhead stays inside the old left
            # clip, _tl_clip still matches, and the gap is silently skipped.
            self._scene_ref.set_playhead(click_seconds)
            self._scene_ref.seek_requested.emit(click_seconds)

        elif chosen == act_split_playhead:
            _do_split(playhead_seconds)

        elif chosen == act_rename:
            new_name, ok = QInputDialog.getText(
                None,
                "Rename Clip",
                "Clip name:",
                text=clip.label or _Path(clip.source_path).stem,
            )
            if ok and new_name.strip():
                clip.label = new_name.strip()
                self._label.setPlainText(clip.display_name)
                self._scene_ref.clip_moved.emit(clip)

        elif chosen == act_delete:
            self._scene_ref.project.remove_clip(clip.clip_id)
            self._scene_ref.removeItem(self)
            self._scene_ref.track_changed.emit()

        event.accept()


# ---------------------------------------------------------------------------
# PlayheadItem
# ---------------------------------------------------------------------------

class PlayheadItem(QGraphicsLineItem):
    def __init__(self, scene_height: float):
        super().__init__(0, 0, 0, scene_height)
        pen = QPen(C_PLAYHEAD, 2)
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setZValue(100)

    def set_position(self, x: float):
        self.setX(x)


# ---------------------------------------------------------------------------
# TrackHeaderWidget — mute/lock buttons + name, embedded via QGraphicsProxyWidget
# ---------------------------------------------------------------------------

HEADER_BTN_STYLE = """
QWidget#TrackHeader {
    background: transparent;
}
QLabel#TrackName {
    color: #AAAAAA;
    font-size: 11px;
    font-weight: bold;
}
QLabel#TrackName[trackType="audio"] {
    color: #C9A8E0;
}
QLabel#TrackName[trackType="video"] {
    color: #8AB8E0;
}
QToolButton#TrackToggle {
    background: #1E1E1E;
    border: 1px solid #333;
    border-radius: 3px;
    color: #666;
    font-size: 10px;
    padding: 0px;
    min-width: 18px;
    max-width: 18px;
    min-height: 18px;
    max-height: 18px;
}
QToolButton#TrackToggle:hover {
    border-color: #4A90D9;
    color: #CCC;
}
QToolButton#TrackToggle[active="true"] {
    background: #3A2020;
    border-color: #CC4444;
    color: #FF8888;
}
"""


class TrackHeaderWidget(QWidget):
    """Small widget embedded in the track header column: name + mute/lock."""

    mute_toggled   = pyqtSignal(str, bool)   # track_id, muted
    locked_toggled = pyqtSignal(str, bool)   # track_id, locked
    remove_clicked = pyqtSignal(str)         # track_id

    def __init__(self, track: Track, parent=None):
        super().__init__(parent)
        self.setObjectName("TrackHeader")
        self.setStyleSheet(HEADER_BTN_STYLE)
        self.track = track
        self.setFixedSize(HEADER_WIDTH - 4, TRACK_HEIGHT - 4)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 2, 4, 2)
        layout.setSpacing(2)

        top_row = QHBoxLayout()
        top_row.setSpacing(4)
        self.lbl_name = QLabel(track.name)
        self.lbl_name.setObjectName("TrackName")
        self.lbl_name.setProperty("trackType", track.track_type)
        top_row.addWidget(self.lbl_name)
        top_row.addStretch()
        layout.addLayout(top_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(3)

        self.btn_mute = QToolButton()
        self.btn_mute.setObjectName("TrackToggle")
        self.btn_mute.setText("🔇" if track.muted else "🔊")
        self.btn_mute.setToolTip("Mute track")
        self.btn_mute.setProperty("active", "true" if track.muted else "false")
        self.btn_mute.clicked.connect(self._toggle_mute)

        self.btn_lock = QToolButton()
        self.btn_lock.setObjectName("TrackToggle")
        self.btn_lock.setText("🔒" if track.locked else "🔓")
        self.btn_lock.setToolTip("Lock track")
        self.btn_lock.setProperty("active", "true" if track.locked else "false")
        self.btn_lock.clicked.connect(self._toggle_lock)

        self.btn_remove = QToolButton()
        self.btn_remove.setObjectName("TrackToggle")
        self.btn_remove.setText("✕")
        self.btn_remove.setToolTip("Remove track")
        self.btn_remove.clicked.connect(lambda: self.remove_clicked.emit(self.track.track_id))

        btn_row.addWidget(self.btn_mute)
        btn_row.addWidget(self.btn_lock)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_remove)
        layout.addLayout(btn_row)

    def _toggle_mute(self):
        self.track.muted = not self.track.muted
        self.btn_mute.setText("🔇" if self.track.muted else "🔊")
        self.btn_mute.setProperty("active", "true" if self.track.muted else "false")
        self.btn_mute.style().unpolish(self.btn_mute)
        self.btn_mute.style().polish(self.btn_mute)
        self.mute_toggled.emit(self.track.track_id, self.track.muted)

    def _toggle_lock(self):
        self.track.locked = not self.track.locked
        self.btn_lock.setText("🔒" if self.track.locked else "🔓")
        self.btn_lock.setProperty("active", "true" if self.track.locked else "false")
        self.btn_lock.style().unpolish(self.btn_lock)
        self.btn_lock.style().polish(self.btn_lock)
        self.locked_toggled.emit(self.track.track_id, self.track.locked)


# ---------------------------------------------------------------------------
# TimelineScene
# ---------------------------------------------------------------------------

class TimelineScene(QGraphicsScene):
    """
    The QGraphicsScene that holds ruler, track backgrounds, clips, playhead.

    Track layout order (top to bottom): all Video tracks (V_n ... V1),
    then all Audio tracks (A1 ... A_n) — V tracks stack with V1 closest
    to the audio divider, matching standard NLE conventions where higher
    V-numbers are visually on top (rendered above V1 in compositing).
    """

    clip_selected  = pyqtSignal(object)    # Clip
    clip_moved     = pyqtSignal(object)    # Clip
    clip_split     = pyqtSignal(object)    # new right-half Clip
    seek_requested = pyqtSignal(float)     # seconds
    track_changed  = pyqtSignal()          # any track add/remove/mute/lock

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project: Project | None = None
        self.pps      = PIXELS_PER_SEC
        self._clip_items: dict[str, ClipItem] = {}
        self._track_order: list[Track] = []   # display order, top → bottom
        self.playhead: PlayheadItem | None    = None

    # -------------------------------------------------------------------------
    # Track ordering helpers
    # -------------------------------------------------------------------------

    def _compute_track_order(self):
        """Video tracks first (reverse index — highest V on top), then audio."""
        if not self.project:
            self._track_order = []
            return
        v_tracks = [t for t in self.project.tracks if t.track_type == TrackType.VIDEO]
        a_tracks = [t for t in self.project.tracks if t.track_type == TrackType.AUDIO]
        # Reverse video order so V2 sits above V1 visually (V2 = overlay)
        self._track_order = list(reversed(v_tracks)) + a_tracks

    def track_row_index(self, track_type: str, track_index: int) -> int:
        """Return the visual row (0 = top) for a given track_type/track_index."""
        for row, t in enumerate(self._track_order):
            if t.track_type == track_type:
                # track_index counts within same-type tracks, 0-based, in
                # creation order — find the Nth track of this type
                same_type = [tt for tt in self.project.tracks if tt.track_type == track_type]
                if track_index < len(same_type) and same_type[track_index].track_id == t.track_id:
                    return row
        return 0

    def track_y_for(self, track_type: str, track_index: int) -> float:
        row = self.track_row_index(track_type, track_index)
        return row * TRACK_HEIGHT

    def track_index_at_y(self, track_type: str, y: float):
        """Given a scene Y (already offset past ruler), find which track_index
        of `track_type` that Y falls into. Returns None if it's the wrong type."""
        row = int(round((y - RULER_HEIGHT) / TRACK_HEIGHT))
        row = max(0, min(row, len(self._track_order) - 1))
        if row >= len(self._track_order):
            return None
        target_track = self._track_order[row]
        if target_track.track_type != track_type:
            return None   # wrong type — drag rejected, caller should not commit
        same_type = [tt for tt in self.project.tracks if tt.track_type == track_type]
        for idx, tt in enumerate(same_type):
            if tt.track_id == target_track.track_id:
                return idx
        return None

    def snap_y_for_drag(self, track_type: str, raw_y: float) -> float:
        """While dragging, snap Y to the nearest row of a MATCHING track type."""
        candidate_rows = [
            row for row, t in enumerate(self._track_order)
            if t.track_type == track_type
        ]
        if not candidate_rows:
            return raw_y

        target_row = (raw_y - RULER_HEIGHT) / TRACK_HEIGHT
        nearest = min(candidate_rows, key=lambda r: abs(r - target_row))
        return RULER_HEIGHT + nearest * TRACK_HEIGHT

    # -------------------------------------------------------------------------

    def load_project(self, project: Project):
        self.project = project
        self.redraw()

    def redraw(self):
        self.clear()
        self._clip_items.clear()
        if not self.project:
            return

        self._compute_track_order()

        num_tracks  = len(self._track_order)
        total_sec   = max(self.project.duration + 10, 60)
        scene_w     = HEADER_WIDTH + total_sec * self.pps
        scene_h     = RULER_HEIGHT + max(num_tracks, 1) * TRACK_HEIGHT

        self.setSceneRect(0, 0, scene_w, scene_h)

        self._draw_ruler(scene_w, total_sec)
        self._draw_tracks(scene_w)
        self._draw_clips()
        self._draw_playhead(scene_h)

    def _draw_ruler(self, scene_w: float, total_sec: float):
        ruler_bg = self.addRect(
            QRectF(0, 0, scene_w, RULER_HEIGHT),
            QPen(Qt.PenStyle.NoPen), QBrush(C_RULER_BG)
        )
        ruler_bg.setZValue(1)

        corner = self.addRect(
            QRectF(0, 0, HEADER_WIDTH, RULER_HEIGHT),
            QPen(Qt.PenStyle.NoPen), QBrush(QColor("#111111"))
        )
        corner.setZValue(2)

        tick_interval = self._tick_interval()
        t = 0.0
        font = QFont("Consolas", 8)
        while t <= total_sec + tick_interval:
            x = HEADER_WIDTH + t * self.pps
            is_major = (round(t * 10) % max(1, round(tick_interval * 10 * 5))) == 0
            tick_h = 8 if is_major else 4
            tick_pen = QPen(C_RULER_TICK.lighter(130) if is_major else C_RULER_TICK, 1)
            line = self.addLine(x, RULER_HEIGHT - tick_h, x, RULER_HEIGHT, tick_pen)
            line.setZValue(2)

            if is_major:
                label = self.addText(seconds_to_tc(t)[:8], font)
                label.setDefaultTextColor(C_RULER_TEXT)
                label.setPos(x + 2, 2)
                label.setZValue(2)
            t += tick_interval

    def _tick_interval(self) -> float:
        sec_per_100px = 100 / self.pps
        for interval in [0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600]:
            if sec_per_100px <= interval * 2:
                return interval
        return 600

    def _draw_tracks(self, scene_w: float):
        for row, track in enumerate(self._track_order):
            y = RULER_HEIGHT + row * TRACK_HEIGHT

            is_video = track.track_type == TrackType.VIDEO
            if is_video:
                bg = C_TRACK_EVEN_V if row % 2 == 0 else C_TRACK_ODD_V
            else:
                bg = C_TRACK_EVEN_A if row % 2 == 0 else C_TRACK_ODD_A

            # Track lane background
            lane = self.addRect(
                QRectF(HEADER_WIDTH, y, scene_w, TRACK_HEIGHT),
                QPen(C_TRACK_BORDER, 1), QBrush(bg)
            )
            lane.setZValue(0)

            # Muted overlay tint
            if track.muted:
                mute_overlay = self.addRect(
                    QRectF(HEADER_WIDTH, y, scene_w, TRACK_HEIGHT),
                    QPen(Qt.PenStyle.NoPen), QBrush(C_MUTED_OVERLAY)
                )
                mute_overlay.setZValue(0.5)

            # Header background
            header_bg = self.addRect(
                QRectF(0, y, HEADER_WIDTH, TRACK_HEIGHT),
                QPen(C_TRACK_BORDER, 1), QBrush(C_HEADER_BG)
            )
            header_bg.setZValue(1)

            # Embedded header widget (name + mute/lock/remove buttons)
            header_widget = TrackHeaderWidget(track)
            header_widget.mute_toggled.connect(self._on_track_mute)
            header_widget.locked_toggled.connect(self._on_track_lock)
            header_widget.remove_clicked.connect(self._on_track_remove)

            proxy = QGraphicsProxyWidget()
            proxy.setWidget(header_widget)
            proxy.setPos(2, y + 2)
            proxy.setZValue(2)
            self.addItem(proxy)

    def _draw_clips(self):
        if not self.project:
            return
        for clip in self.project.clips:
            ci = ClipItem(clip, self)
            self.addItem(ci)
            self._clip_items[clip.clip_id] = ci

    def _draw_playhead(self, scene_h: float):
        self.playhead = PlayheadItem(scene_h)
        self.playhead.setX(HEADER_WIDTH)
        self.addItem(self.playhead)

    # ---- track toggle handlers ----

    def _on_track_mute(self, track_id: str, muted: bool):
        self.redraw()   # simplest correct way to refresh the muted tint
        self.track_changed.emit()

    def _on_track_lock(self, track_id: str, locked: bool):
        self.track_changed.emit()

    def _on_track_remove(self, track_id: str):
        if not self.project:
            return
        # Don't allow removing the last track of a type
        track = next((t for t in self.project.tracks if t.track_id == track_id), None)
        if not track:
            return
        same_type_count = sum(1 for t in self.project.tracks if t.track_type == track.track_type)
        if same_type_count <= 1:
            return   # keep at least one V and one A track

        # Remove clips that live on this track, then the track itself
        removed_index = None
        same_type = [t for t in self.project.tracks if t.track_type == track.track_type]
        for idx, t in enumerate(same_type):
            if t.track_id == track_id:
                removed_index = idx
                break

        self.project.clips = [
            c for c in self.project.clips
            if not (c.track_type == track.track_type and c.track_index == removed_index)
        ]
        # Shift down track_index for clips above the removed one
        for c in self.project.clips:
            if c.track_type == track.track_type and c.track_index > removed_index:
                c.track_index -= 1

        self.project.tracks = [t for t in self.project.tracks if t.track_id != track_id]
        self.redraw()
        self.track_changed.emit()

    # ---- public ----

    def set_playhead(self, seconds: float):
        if self.playhead:
            x = HEADER_WIDTH + seconds * self.pps
            self.playhead.setX(x)

    def get_playhead_seconds(self) -> float:
        """Return current playhead position in seconds."""
        if self.playhead:
            return max(0.0, (self.playhead.x() - HEADER_WIDTH) / self.pps)
        return 0.0

    def split_at_playhead(self) -> bool:
        """
        Split whichever clip(s) the playhead currently intersects.

        Walks all clips, finds any that contain the playhead position,
        calls Project.split_clip(), adds the resulting right-half ClipItem
        to the scene, and emits clip_split for each new half.

        Returns True if at least one clip was split.
        """
        if not self.project:
            return False

        split_sec = self.get_playhead_seconds()
        new_clips = []

        # Collect candidates first (list may grow during loop — iterate a copy)
        for clip in list(self.project.clips):
            tl_start = clip.timeline_position
            tl_end   = clip.timeline_end
            if tl_start < split_sec < tl_end:
                right = self.project.split_clip(clip.clip_id, split_sec)
                if right is not None:
                    new_clips.append(right)

        for right in new_clips:
            # Refresh the LEFT half's visual width (out_point shrank)
            left_item = self._clip_items.get(
                next(c.clip_id for c in self.project.clips
                     if c.timeline_end == split_sec
                     and c.track_index == right.track_index
                     and c.track_type  == right.track_type),
                None
            )
            # Simpler: just redraw all existing items at updated geometry
            for cid, ci in self._clip_items.items():
                ci.update_pps(self.pps)

            # Add the right half as a new ClipItem
            ci_right = ClipItem(right, self)
            self.addItem(ci_right)
            self._clip_items[right.clip_id] = ci_right
            self.clip_split.emit(right)

        # Expand scene rect if needed
        if new_clips:
            total_sec = max(self.project.duration + 10, 60)
            scene_w   = HEADER_WIDTH + total_sec * self.pps
            scene_h   = RULER_HEIGHT + max(len(self._track_order), 1) * TRACK_HEIGHT
            self.setSceneRect(0, 0, scene_w, scene_h)

        return bool(new_clips)

    def set_zoom(self, pps: float):
        self.pps = pps
        self.redraw()

    def add_clip_item(self, clip: Clip):
        if not self.project:
            return
        ci = ClipItem(clip, self)
        self.addItem(ci)
        self._clip_items[clip.clip_id] = ci
        total_sec = max(self.project.duration + 10, 60)
        scene_w   = HEADER_WIDTH + total_sec * self.pps
        scene_h   = RULER_HEIGHT + max(len(self._track_order), 1) * TRACK_HEIGHT
        self.setSceneRect(0, 0, scene_w, scene_h)

    def add_track(self, track_type: str):
        """Add a new track of the given type and refresh."""
        if not self.project:
            return
        same_type = [t for t in self.project.tracks if t.track_type == track_type]
        n = len(same_type) + 1
        prefix = "V" if track_type == TrackType.VIDEO else "A"
        new_track = Track(name=f"{prefix}{n}", track_type=track_type)
        self.project.tracks.append(new_track)
        self.redraw()
        self.track_changed.emit()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.scenePos()
            if pos.y() < RULER_HEIGHT and pos.x() > HEADER_WIDTH:
                seconds = max(0.0, (pos.x() - HEADER_WIDTH) / self.pps)
                self.set_playhead(seconds)
                self.seek_requested.emit(seconds)
                return
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# TimelineWidget  — the full timeline panel
# ---------------------------------------------------------------------------

TIMELINE_STYLE = """
QWidget#TimelinePanel {
    background: #1A1A1A;
    border-top: 1px solid #2A2A2A;
}
QPushButton#TLBtn {
    background: #252525;
    border: 1px solid #333;
    border-radius: 3px;
    color: #AAAAAA;
    font-size: 11px;
    padding: 3px 8px;
    min-height: 22px;
}
QPushButton#TLBtn:hover {
    background: #2D2D2D;
    color: #FFFFFF;
    border-color: #4A90D9;
}
QPushButton#AddTrackBtn {
    background: #1A2E1A;
    border: 1px solid #2A4A2A;
    border-radius: 3px;
    color: #6ABF6A;
    font-size: 11px;
    font-weight: bold;
    padding: 3px 10px;
    min-height: 22px;
}
QPushButton#AddTrackBtn:hover {
    background: #1F3A1F;
    border-color: #4CAF50;
    color: #8AE08A;
}
QGraphicsView {
    background: #1A1A1A;
    border: none;
}
QLabel#TLLabel {
    color: #666;
    font-size: 11px;
    padding: 0 6px;
}
"""


class TimelineWidget(QWidget):
    """
    Full timeline panel — toolbar + QGraphicsView, multi-track.
    """

    seek_requested  = pyqtSignal(float)
    clip_added      = pyqtSignal(object)    # Clip
    project_changed = pyqtSignal()          # tracks added/removed/clip moved

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TimelinePanel")
        self.setStyleSheet(TIMELINE_STYLE)
        self.setMinimumHeight(160)

        self.project: Project | None = None
        self._pps = PIXELS_PER_SEC

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setStyleSheet("background:#161616; border-bottom:1px solid #2A2A2A;")
        toolbar.setFixedHeight(32)
        tbar_layout = QHBoxLayout(toolbar)
        tbar_layout.setContentsMargins(8, 4, 8, 4)
        tbar_layout.setSpacing(4)

        def _btn(text, tip, object_name="TLBtn"):
            b = QPushButton(text)
            b.setObjectName(object_name)
            b.setToolTip(tip)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            return b

        self.btn_split  = _btn("✂  Split",  "Split clip at playhead  [S]")
        self.btn_delete = _btn("🗑  Delete", "Delete selected clip  [Del]")
        self.btn_zoom_in  = _btn("🔍+", "Zoom In  [+]")
        self.btn_zoom_out = _btn("🔍−", "Zoom Out  [−]")
        self.btn_fit      = _btn("⟷ Fit", "Fit timeline to window")
        self.btn_add_v    = _btn("＋V", "Add video track", "AddTrackBtn")
        self.btn_add_a    = _btn("＋A", "Add audio track", "AddTrackBtn")

        tbar_layout.addWidget(self.btn_split)
        tbar_layout.addWidget(self.btn_delete)
        tbar_layout.addSpacing(8)
        tbar_layout.addWidget(self.btn_zoom_in)
        tbar_layout.addWidget(self.btn_zoom_out)
        tbar_layout.addWidget(self.btn_fit)
        tbar_layout.addSpacing(8)
        tbar_layout.addWidget(self.btn_add_v)
        tbar_layout.addWidget(self.btn_add_a)
        tbar_layout.addStretch()

        self.lbl_info = QLabel("No project loaded")
        self.lbl_info.setObjectName("TLLabel")
        tbar_layout.addWidget(self.lbl_info)

        layout.addWidget(toolbar)

        # Scene + View
        self.scene = TimelineScene(self)
        self.scene.seek_requested.connect(self.seek_requested)
        self.scene.track_changed.connect(self._on_project_changed)
        self.scene.clip_moved.connect(lambda c: self._on_project_changed())

        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.view, stretch=1)

        # Connect toolbar buttons
        self.btn_zoom_in.clicked.connect(self._zoom_in)
        self.btn_zoom_out.clicked.connect(self._zoom_out)
        self.btn_fit.clicked.connect(self._zoom_fit)
        self.btn_delete.clicked.connect(self._delete_selected)
        self.btn_split.clicked.connect(self._split_at_playhead)
        self.btn_add_v.clicked.connect(lambda: self._add_track(TrackType.VIDEO))
        self.btn_add_a.clicked.connect(lambda: self._add_track(TrackType.AUDIO))

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def load_project(self, project: Project):
        self.project = project
        self.scene.load_project(project)
        self._update_info()

    def set_playhead(self, seconds: float):
        self.scene.set_playhead(seconds)

    def add_clip(self, clip: Clip):
        """Add a clip to the timeline (already added to project.clips by caller)."""
        self.scene.add_clip_item(clip)
        self._update_info()

    # -------------------------------------------------------------------------
    # Tracks
    # -------------------------------------------------------------------------

    def _add_track(self, track_type: str):
        if not self.project:
            return
        self.scene.add_track(track_type)
        self._update_info()

    def _on_project_changed(self):
        self._update_info()
        self.project_changed.emit()

    # -------------------------------------------------------------------------
    # Zoom
    # -------------------------------------------------------------------------

    def _zoom_in(self):
        self._pps = min(self._pps * 1.5, 2000)
        self.scene.set_zoom(self._pps)

    def _zoom_out(self):
        self._pps = max(self._pps / 1.5, 4)
        self.scene.set_zoom(self._pps)

    def _zoom_fit(self):
        if not self.project or not self.project.duration:
            return
        available = self.view.width() - HEADER_WIDTH - 20
        self._pps  = available / self.project.duration
        self.scene.set_zoom(self._pps)

    # -------------------------------------------------------------------------
    # Edit actions
    # -------------------------------------------------------------------------

    def _delete_selected(self):
        if not self.project:
            return
        for item in self.scene.selectedItems():
            if isinstance(item, ClipItem):
                self.project.remove_clip(item.clip.clip_id)
                self.scene.removeItem(item)
        self._update_info()

    def _split_at_playhead(self):
        """Split clip(s) under the playhead. Bound to ✂ Split button and [S] key."""
        if not self.project:
            return
        did_split = self.scene.split_at_playhead()
        if did_split:
            self._on_project_changed()
        # If nothing was split (playhead not over a clip) the button is a no-op

    # -------------------------------------------------------------------------

    def _update_info(self):
        if self.project:
            n = len(self.project.clips)
            n_v = sum(1 for t in self.project.tracks if t.track_type == TrackType.VIDEO)
            n_a = sum(1 for t in self.project.tracks if t.track_type == TrackType.AUDIO)
            self.lbl_info.setText(
                f"{n} clip{'s' if n != 1 else ''}  •  "
                f"{n_v}V / {n_a}A  •  {self.project.duration_tc}"
            )
        else:
            self.lbl_info.setText("No project loaded")