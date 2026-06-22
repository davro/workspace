"""
SubtitleStyleDialog — Visual subtitle style editor.

Shows a live mini-preview of text appearance as the user adjusts settings.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QComboBox, QSlider, QSpinBox, QCheckBox,
    QFrame, QWidget, QSizePolicy, QColorDialog, QFontComboBox,
    QGroupBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QPalette

from .SubtitleStyle import SubtitleStyle, POSITION_PRESETS, FONT_SIZES, FONT_WEIGHTS


DIALOG_STYLE = """
QDialog { background: #1E1E1E; color: #CCCCCC; }
QGroupBox {
    border: 1px solid #333;
    border-radius: 4px;
    margin-top: 10px;
    padding: 8px 6px 6px 6px;
    color: #888;
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 1px;
}
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
QLabel { color: #AAAAAA; font-size: 12px; }
QComboBox, QSpinBox, QFontComboBox {
    background: #252525;
    border: 1px solid #3A3A3A;
    border-radius: 3px;
    color: #CCCCCC;
    padding: 3px 8px;
    min-height: 22px;
    font-size: 12px;
}
QComboBox:hover, QSpinBox:hover, QFontComboBox:hover { border-color: #4A90D9; }
QComboBox QAbstractItemView {
    background: #252525; color: #CCC;
    selection-background-color: #1E3A5F;
    border: 1px solid #3A3A3A;
}
QSlider::groove:horizontal {
    height: 4px; background: #333; border-radius: 2px;
}
QSlider::sub-page:horizontal { background: #4A90D9; border-radius: 2px; }
QSlider::handle:horizontal {
    width: 12px; height: 12px; margin: -4px 0;
    border-radius: 6px; background: #FFF;
}
QCheckBox { color: #CCCCCC; font-size: 12px; spacing: 6px; }
QCheckBox::indicator {
    width: 14px; height: 14px;
    border: 1px solid #555; border-radius: 3px; background: #252525;
}
QCheckBox::indicator:checked { background: #4A90D9; border-color: #4A90D9; }
QPushButton#ColourBtn {
    border: 2px solid #3A3A3A;
    border-radius: 4px;
    min-width: 52px;
    min-height: 24px;
    font-size: 11px;
}
QPushButton#ColourBtn:hover { border-color: #4A90D9; }
QPushButton#ActionBtn {
    background: #1A3A6A; border: 1px solid #2A5FA0;
    border-radius: 4px; color: #FFF;
    font-size: 12px; font-weight: bold;
    padding: 6px 20px; min-height: 28px;
}
QPushButton#ActionBtn:hover { background: #1E4A8A; }
QPushButton#CancelBtn {
    background: transparent; border: 1px solid #3A3A3A;
    border-radius: 4px; color: #888;
    font-size: 12px; padding: 6px 16px; min-height: 28px;
}
QPushButton#CancelBtn:hover { border-color: #666; color: #CCC; }
"""


class _PreviewLabel(QLabel):
    """Renders a mini subtitle preview swatch."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.style_obj = SubtitleStyle()
        self.setMinimumHeight(80)
        self.setStyleSheet("background: #2A4A2A;")   # green-ish to simulate video

    def update_style(self, s: SubtitleStyle):
        self.style_obj = s
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        s = self.style_obj
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        text = "Sample subtitle text"
        font = QFont(s.font_family, max(8, s.font_size // 2))
        font.setBold(s.font_weight == "Bold")
        p.setFont(font)
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(text)
        th = fm.height()

        # Position
        preset = POSITION_PRESETS.get(s.position, POSITION_PRESETS["Bottom Centre"])
        w, h = self.width(), self.height()
        if "Right" in s.position:
            x = w - tw - 12
        elif "Left" in s.position:
            x = 12
        else:
            x = (w - tw) // 2
        if "Top" in s.position:
            y = 12 + th
        elif "Centre" == s.position.split()[-1] and "Top" not in s.position and "Bottom" not in s.position:
            y = (h + th) // 2
        else:
            y = h - 12

        # Background box
        if s.bg_enabled:
            pad = 6
            r, g, b, a = s.bg_color
            p.fillRect(x - pad, y - th, tw + pad * 2, th + 4, QColor(r, g, b, a))

        # Outline
        if s.outline_width > 0:
            r, g, b, a = s.outline_color
            oc = QColor(r, g, b, a)
            p.setPen(QPen(oc, s.outline_width * 2))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx or dy:
                        p.drawText(x + dx, y + dy, text)

        # Text
        r, g, b, a = s.text_color
        p.setPen(QColor(r, g, b, a))
        p.drawText(x, y, text)
        p.end()


class SubtitleStyleDialog(QDialog):
    """
    Style editor for subtitle overlay.

    After exec():
        dialog.style  → SubtitleStyle
    """

    def __init__(self, initial: SubtitleStyle | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Subtitle Style")
        self.setStyleSheet(DIALOG_STYLE)
        self.setModal(True)
        self.setMinimumWidth(460)
        self.setMaximumWidth(560)

        self.style = SubtitleStyle() if initial is None else initial
        # Work on a copy so Cancel discards changes
        self._s = SubtitleStyle(
            font_size    = self.style.font_size,
            font_weight  = self.style.font_weight,
            font_family  = self.style.font_family,
            text_color   = self.style.text_color,
            outline_color= self.style.outline_color,
            bg_color     = self.style.bg_color,
            outline_width= self.style.outline_width,
            bg_enabled   = self.style.bg_enabled,
            position     = self.style.position,
        )
        self._build_ui()
        self._refresh_preview()

    # -------------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        title = QLabel("🎨  Subtitle Style")
        title.setStyleSheet("font-size:15px; font-weight:bold; color:#FFF; padding-bottom:4px;")
        root.addWidget(title)

        # --- Preview ---
        self._preview = _PreviewLabel()
        root.addWidget(self._preview)

        # --- Font ---
        font_grp = QGroupBox("FONT")
        fg = QGridLayout(font_grp)
        fg.setSpacing(6)

        fg.addWidget(QLabel("Family:"), 0, 0)
        self.combo_family = QFontComboBox()
        self.combo_family.setCurrentFont(QFont(self._s.font_family))
        self.combo_family.currentFontChanged.connect(
            lambda f: self._set("font_family", f.family()))
        fg.addWidget(self.combo_family, 0, 1)

        fg.addWidget(QLabel("Size:"), 1, 0)
        self.combo_size = QComboBox()
        for sz in FONT_SIZES:
            self.combo_size.addItem(str(sz), sz)
        self.combo_size.setCurrentText(str(self._s.font_size))
        self.combo_size.currentIndexChanged.connect(
            lambda: self._set("font_size", self.combo_size.currentData()))
        fg.addWidget(self.combo_size, 1, 1)

        fg.addWidget(QLabel("Weight:"), 2, 0)
        self.combo_weight = QComboBox()
        self.combo_weight.addItems(FONT_WEIGHTS)
        self.combo_weight.setCurrentText(self._s.font_weight)
        self.combo_weight.currentTextChanged.connect(
            lambda v: self._set("font_weight", v))
        fg.addWidget(self.combo_weight, 2, 1)

        root.addWidget(font_grp)

        # --- Colours ---
        col_grp = QGroupBox("COLOURS")
        cg = QGridLayout(col_grp)
        cg.setSpacing(6)

        self.btn_text_col = self._colour_btn(self._s.text_color,
            lambda: self._pick_colour("text_color", self.btn_text_col))
        cg.addWidget(QLabel("Text:"), 0, 0)
        cg.addWidget(self.btn_text_col, 0, 1)

        self.btn_outline_col = self._colour_btn(self._s.outline_color,
            lambda: self._pick_colour("outline_color", self.btn_outline_col))
        cg.addWidget(QLabel("Outline:"), 1, 0)
        cg.addWidget(self.btn_outline_col, 1, 1)

        outline_size_row = QHBoxLayout()
        self.spin_outline = QSpinBox()
        self.spin_outline.setRange(0, 8)
        self.spin_outline.setValue(self._s.outline_width)
        self.spin_outline.setSuffix(" px")
        self.spin_outline.valueChanged.connect(lambda v: self._set("outline_width", v))
        outline_size_row.addWidget(self.spin_outline)
        outline_size_row.addWidget(QLabel("(0 = off)"))
        outline_size_row.addStretch()
        cg.addWidget(QLabel("Outline width:"), 2, 0)
        cg.addLayout(outline_size_row, 2, 1)

        self.chk_bg = QCheckBox("Background box")
        self.chk_bg.setChecked(self._s.bg_enabled)
        self.chk_bg.toggled.connect(lambda v: self._set("bg_enabled", v))
        cg.addWidget(self.chk_bg, 3, 0, 1, 2)

        self.btn_bg_col = self._colour_btn(self._s.bg_color,
            lambda: self._pick_colour("bg_color", self.btn_bg_col, alpha=True))
        cg.addWidget(QLabel("  Box colour:"), 4, 0)
        cg.addWidget(self.btn_bg_col, 4, 1)

        root.addWidget(col_grp)

        # --- Position ---
        pos_grp = QGroupBox("POSITION")
        pg = QHBoxLayout(pos_grp)
        pg.setSpacing(6)
        pg.addWidget(QLabel("Preset:"))
        self.combo_pos = QComboBox()
        self.combo_pos.addItems(list(POSITION_PRESETS.keys()))
        self.combo_pos.setCurrentText(self._s.position)
        self.combo_pos.currentTextChanged.connect(lambda v: self._set("position", v))
        pg.addWidget(self.combo_pos, stretch=1)
        root.addWidget(pos_grp)

        # --- Buttons ---
        root.addStretch()
        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setObjectName("CancelBtn")
        btn_cancel.clicked.connect(self.reject)

        btn_ok = QPushButton("Apply Style")
        btn_ok.setObjectName("ActionBtn")
        btn_ok.clicked.connect(self._on_apply)

        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(btn_ok)
        root.addLayout(btn_row)

    # -------------------------------------------------------------------------

    def _colour_btn(self, rgba, callback) -> QPushButton:
        r, g, b, a = rgba
        btn = QPushButton()
        btn.setObjectName("ColourBtn")
        btn.setStyleSheet(
            f"QPushButton#ColourBtn {{ background: rgba({r},{g},{b},{a}); }}")
        btn.clicked.connect(callback)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return btn

    def _pick_colour(self, attr: str, btn: QPushButton, alpha: bool = False):
        r, g, b, a = getattr(self._s, attr)
        initial = QColor(r, g, b, a)
        if alpha:
            col = QColorDialog.getColor(
                initial, self,
                options=QColorDialog.ColorDialogOption.ShowAlphaChannel)
        else:
            col = QColorDialog.getColor(initial, self)
        if col.isValid():
            new_rgba = (col.red(), col.green(), col.blue(), col.alpha())
            setattr(self._s, attr, new_rgba)
            btn.setStyleSheet(
                f"QPushButton#ColourBtn {{ background: rgba{new_rgba}; }}")
            self._refresh_preview()

    def _set(self, attr, value):
        setattr(self._s, attr, value)
        self._refresh_preview()

    def _refresh_preview(self):
        self._preview.update_style(self._s)

    def _on_apply(self):
        self.style = self._s
        self.accept()
