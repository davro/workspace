"""
MediaBin — Left panel showing imported clips with thumbnails and metadata.
"""

import os
import tempfile
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QAbstractItemView, QMenu,
    QFileDialog, QSizePolicy, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QThread
from PyQt6.QtGui import QPixmap, QIcon, QColor, QFont

from .ClipModel import MediaInfo, ClipType, seconds_to_tc
from .FFmpegWorker import ProbeWorker, ThumbnailWorker, check_ffmpeg_available

# ---------------------------------------------------------------------------

BIN_STYLE = """
QWidget#MediaBin {
    background: #1C1C1C;
    border-right: 1px solid #2A2A2A;
}

QLabel#BinTitle {
    color: #AAAAAA;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1px;
    padding: 8px 10px 4px 10px;
    text-transform: uppercase;
}

QPushButton#BinBtn {
    background: #252525;
    border: 1px solid #333333;
    border-radius: 4px;
    color: #CCCCCC;
    font-size: 12px;
    padding: 5px 10px;
    text-align: left;
}
QPushButton#BinBtn:hover {
    background: #2D2D2D;
    border-color: #4A90D9;
    color: #FFFFFF;
}
QPushButton#BinBtn:pressed {
    background: #1E3A5F;
}

QListWidget#ClipList {
    background: #1C1C1C;
    border: none;
    outline: none;
    color: #CCCCCC;
}
QListWidget#ClipList::item {
    padding: 4px 6px;
    border-bottom: 1px solid #252525;
    border-radius: 0px;
}
QListWidget#ClipList::item:selected {
    background: #1E3A5F;
    color: #FFFFFF;
}
QListWidget#ClipList::item:hover:!selected {
    background: #252525;
}

QLabel#PropsLabel {
    color: #888888;
    font-size: 11px;
    padding: 4px 10px;
    font-family: 'Consolas', monospace;
}

QFrame#Divider {
    color: #2A2A2A;
}

QLabel#StatusLabel {
    color: #666666;
    font-size: 11px;
    padding: 4px 10px;
    font-style: italic;
}
"""

SUPPORTED_VIDEO = "Video Files (*.mp4 *.mov *.avi *.mkv *.webm *.m4v *.mpg *.mpeg *.wmv *.flv)"
SUPPORTED_AUDIO = "Audio Files (*.mp3 *.wav *.aac *.m4a *.flac *.ogg *.opus)"
SUPPORTED_IMAGE = "Image Files (*.jpg *.jpeg *.png *.bmp *.gif *.tiff *.webp)"
ALL_MEDIA       = f"All Media ({SUPPORTED_VIDEO} {SUPPORTED_AUDIO} {SUPPORTED_IMAGE})"


class BinItem:
    """Holds a MediaInfo + probe/thumbnail state for a bin entry."""
    def __init__(self, path: str):
        self.path      = path
        self.name      = Path(path).name
        self.info: MediaInfo | None = None
        self.thumbnail: str | None  = None
        self.loading   = True
        self.error     = ""


class MediaBin(QWidget):
    """
    Left panel — imported media library.

    Signals
    -------
    clip_selected(BinItem)       user clicked a clip → preview it
    clip_add_to_timeline(BinItem) user double-clicked / hit Enter → add to timeline
    """

    clip_selected         = pyqtSignal(object)
    clip_add_to_timeline  = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MediaBin")
        self.setStyleSheet(BIN_STYLE)
        self.setMinimumWidth(180)
        self.setMaximumWidth(300)

        self._items: dict[str, BinItem] = {}   # path → BinItem
        self._probe_workers:     list = []
        self._thumb_workers:     list = []
        self._thumb_dir = tempfile.mkdtemp(prefix="vep_thumbs_")

        self._ffmpeg_ok, self._ffmpeg_msg = check_ffmpeg_available()

        self._build_ui()

    # -------------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title
        title = QLabel("MEDIA BIN")
        title.setObjectName("BinTitle")
        layout.addWidget(title)

        # Import button
        btn_row = QWidget()
        btn_row.setStyleSheet("background:transparent;")
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(8, 4, 8, 4)
        btn_layout.setSpacing(4)

        self.btn_import = QPushButton("＋  Import Media")
        self.btn_import.setObjectName("BinBtn")
        self.btn_import.clicked.connect(self.import_media)
        btn_layout.addWidget(self.btn_import)

        layout.addWidget(btn_row)

        # Divider
        div = QFrame()
        div.setObjectName("Divider")
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("color:#2A2A2A;")
        layout.addWidget(div)

        # Clip list
        self.clip_list = QListWidget()
        self.clip_list.setObjectName("ClipList")
        self.clip_list.setIconSize(QSize(56, 36))
        self.clip_list.setSpacing(1)
        self.clip_list.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.clip_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.clip_list.itemClicked.connect(self._on_item_clicked)
        self.clip_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.clip_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.clip_list.customContextMenuRequested.connect(self._context_menu)
        layout.addWidget(self.clip_list, stretch=1)

        # Properties panel
        div2 = QFrame()
        div2.setFrameShape(QFrame.Shape.HLine)
        div2.setStyleSheet("color:#2A2A2A;")
        layout.addWidget(div2)

        self.props_label = QLabel("Select a clip to\nview properties")
        self.props_label.setObjectName("PropsLabel")
        self.props_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.props_label.setMinimumHeight(80)
        layout.addWidget(self.props_label)

        # Status
        self.status_label = QLabel("")
        self.status_label.setObjectName("StatusLabel")
        layout.addWidget(self.status_label)

        # ffmpeg warning
        if not self._ffmpeg_ok:
            warn = QLabel(f"⚠ {self._ffmpeg_msg}")
            warn.setWordWrap(True)
            warn.setStyleSheet(
                "color:#E8A838; font-size:10px; padding:4px 8px;"
                "background:#2A1F00; border-top:1px solid #3A2F00;"
            )
            layout.addWidget(warn)

    # -------------------------------------------------------------------------
    # Import
    # -------------------------------------------------------------------------

    def import_media(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Import Media",
            os.path.expanduser("~"),
            f"{ALL_MEDIA};;{SUPPORTED_VIDEO};;{SUPPORTED_AUDIO};;{SUPPORTED_IMAGE};;All Files (*)"
        )
        for path in paths:
            self.add_file(path)

    def add_file(self, path: str):
        """Add a file to the bin (may be called programmatically)."""
        if path in self._items:
            return   # already in bin

        item = BinItem(path)
        self._items[path] = item

        list_item = QListWidgetItem(f"⏳  {item.name}")
        list_item.setData(Qt.ItemDataRole.UserRole, path)
        list_item.setForeground(QColor("#777777"))
        self.clip_list.addItem(list_item)

        self._probe(path)

    def _probe(self, path: str):
        worker = ProbeWorker(path, self)
        worker.finished.connect(lambda info: self._on_probe_done(path, info))
        worker.error.connect(lambda err: self._on_probe_error(path, err))
        self._probe_workers.append(worker)
        worker.finished.connect(lambda: self._probe_workers.remove(worker) if worker in self._probe_workers else None)
        worker.start()

    def _on_probe_done(self, path: str, info: MediaInfo):
        if path not in self._items:
            return
        item = self._items[path]
        item.info    = info
        item.loading = False

        # Update list item
        list_item = self._find_list_item(path)
        if list_item:
            icon_char = {"video": "🎬", "audio": "🎵", "image": "🖼"}.get(info.clip_type, "📄")
            list_item.setText(f"{icon_char}  {item.name}")
            list_item.setForeground(QColor("#CCCCCC"))
            list_item.setToolTip(
                f"{info.resolution}  •  {info.duration_tc}  •  {info.fps:.2f}fps\n{path}"
            )

        self.status_label.setText(f"{len(self._items)} clip(s)")

        # Extract thumbnail for video clips
        if info.clip_type == ClipType.VIDEO and self._ffmpeg_ok:
            thumb_path = os.path.join(self._thumb_dir, f"{abs(hash(path))}.jpg")
            seek_time  = min(info.duration * 0.1, 2.0)
            worker = ThumbnailWorker(path, thumb_path, seek=seek_time, parent=self)
            worker.finished.connect(self._on_thumb_done)
            worker.error.connect(lambda p, e: None)   # silent fail
            self._thumb_workers.append(worker)
            worker.start()

    def _on_probe_error(self, path: str, error: str):
        if path not in self._items:
            return
        item = self._items[path]
        item.loading = False
        item.error   = error
        list_item = self._find_list_item(path)
        if list_item:
            list_item.setText(f"⚠  {item.name}")
            list_item.setForeground(QColor("#CC4444"))
            list_item.setToolTip(f"Error: {error}")

    def _on_thumb_done(self, source_path: str, thumb_path: str):
        if source_path not in self._items:
            return
        self._items[source_path].thumbnail = thumb_path
        list_item = self._find_list_item(source_path)
        if list_item and os.path.exists(thumb_path):
            px = QPixmap(thumb_path).scaled(
                56, 36,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            list_item.setIcon(QIcon(px))

    # -------------------------------------------------------------------------
    # Selection / interaction
    # -------------------------------------------------------------------------

    def _on_item_clicked(self, list_item: QListWidgetItem):
        path = list_item.data(Qt.ItemDataRole.UserRole)
        if path and path in self._items:
            bin_item = self._items[path]
            self.clip_selected.emit(bin_item)
            self._show_props(bin_item)

    def _on_item_double_clicked(self, list_item: QListWidgetItem):
        path = list_item.data(Qt.ItemDataRole.UserRole)
        if path and path in self._items:
            self.clip_add_to_timeline.emit(self._items[path])

    def _show_props(self, item: BinItem):
        if not item.info:
            self.props_label.setText(f"{item.name}\n(loading…)")
            return
        info = item.info
        size_mb = info.file_size / (1024 * 1024)
        lines = [
            f"<b>{item.name}</b>",
            f"Duration:  {info.duration_tc}",
        ]
        if info.resolution != "—":
            lines.append(f"Size:       {info.resolution}")
        if info.fps:
            lines.append(f"FPS:        {info.fps:.3g}")
        if info.codec:
            lines.append(f"Video:      {info.codec}")
        if info.audio_codec:
            lines.append(f"Audio:      {info.audio_codec}")
        lines.append(f"File:       {size_mb:.1f} MB")
        self.props_label.setText("<br>".join(lines))

    def _context_menu(self, pos):
        list_item = self.clip_list.itemAt(pos)
        if not list_item:
            return
        path = list_item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background:#252525; border:1px solid #3A3A3A; color:#CCC; }
            QMenu::item:selected { background:#1E3A5F; }
        """)
        add_action    = menu.addAction("➕  Add to Timeline")
        menu.addSeparator()
        remove_action = menu.addAction("🗑  Remove from Bin")

        action = menu.exec(self.clip_list.mapToGlobal(pos))
        if action == add_action and path in self._items:
            self.clip_add_to_timeline.emit(self._items[path])
        elif action == remove_action:
            self._remove_item(path)

    def _remove_item(self, path: str):
        for i in range(self.clip_list.count()):
            item = self.clip_list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == path:
                self.clip_list.takeItem(i)
                break
        self._items.pop(path, None)
        self.status_label.setText(f"{len(self._items)} clip(s)")
        self.props_label.setText("Select a clip to\nview properties")

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _find_list_item(self, path: str) -> QListWidgetItem | None:
        for i in range(self.clip_list.count()):
            item = self.clip_list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == path:
                return item
        return None

    def get_bin_paths(self) -> list[str]:
        return list(self._items.keys())

    def get_item(self, path: str) -> BinItem | None:
        return self._items.get(path)

    def cleanup(self):
        for w in self._probe_workers + self._thumb_workers:
            try:
                w.quit()
                w.wait(500)
            except Exception:
                pass