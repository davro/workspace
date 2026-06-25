"""
WhisperDialog — Model picker + source selector for Whisper transcription.

Opens when the user clicks 🎙 Transcribe in the VideoEditorWidget toolbar.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QButtonGroup, QRadioButton, QFrame, QWidget,
    QSizePolicy, QCheckBox,
)
from PyQt6.QtCore import Qt

from .WhisperWorker import MODEL_SIZES


# ---------------------------------------------------------------------------
# Device detection
# ---------------------------------------------------------------------------

def detect_devices() -> List[Tuple[str, str, str]]:
    """
    Return a list of (label, device_str, compute_type) tuples for the
    device combo box.  CPU is always present.  CUDA devices are added if
    torch is installed and at least one GPU is available.

    compute_type choices
    --------------------
    CPU              -> "int8"         (fastest on CPU, universally supported)
    CUDA (fp16 cap)  -> "float16"      (full GPU precision, requires >= 3GB VRAM)
    CUDA (int8 cap)  -> "int8_float16" (lower VRAM, good for 4-6 GB cards)
    """
    devices: List[Tuple[str, str, str]] = []

    try:
        import torch
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                props   = torch.cuda.get_device_properties(i)
                name    = props.name                       # e.g. "NVIDIA GeForce RTX 3080"
                vram_gb = props.total_memory / (1024 ** 3)
                major   = props.major                      # CUDA compute capability major
                # fp16 reliable on compute capability >= 7.0 (Volta+) with >= 3 GB VRAM
                if major >= 7 and vram_gb >= 3.0:
                    compute = "float16"
                else:
                    compute = "int8_float16"
                label = f"GPU {i}  -  {name}  ({vram_gb:.1f} GB)"
                devices.append((label, f"cuda:{i}", compute))
    except Exception:
        # torch not installed, or any CUDA probe error - silently skip
        pass

    # CPU is always the safe fallback
    devices.append(("CPU  (slower, always available)", "cpu", "int8"))
    return devices


# Cache at import time so the dialog opens instantly
_DEVICES = detect_devices()


# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------

DIALOG_STYLE = """
QDialog {
    background: #1E1E1E;
    color: #CCCCCC;
}
QLabel#DialogTitle {
    color: #FFFFFF;
    font-size: 15px;
    font-weight: bold;
    padding: 4px 0 8px 0;
}
QLabel#SectionLabel {
    color: #AAAAAA;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1px;
    padding-bottom: 4px;
}
QLabel#HintLabel {
    color: #666666;
    font-size: 11px;
    padding: 2px 0 0 0;
}
QComboBox {
    background: #252525;
    border: 1px solid #3A3A3A;
    border-radius: 4px;
    color: #CCCCCC;
    padding: 5px 10px;
    font-size: 12px;
    min-width: 180px;
}
QComboBox:hover { border-color: #4A90D9; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background: #252525;
    color: #CCCCCC;
    selection-background-color: #1E3A5F;
    border: 1px solid #3A3A3A;
}
QRadioButton {
    color: #CCCCCC;
    font-size: 12px;
    spacing: 8px;
    padding: 3px 0;
}
QRadioButton::indicator {
    width: 14px; height: 14px;
    border-radius: 7px;
    border: 1px solid #555555;
    background: #252525;
}
QRadioButton::indicator:checked {
    background: #4A90D9;
    border-color: #4A90D9;
}
QRadioButton:disabled { color: #555555; }
QPushButton#ActionBtn {
    background: #1A3A6A;
    border: 1px solid #2A5FA0;
    border-radius: 4px;
    color: #FFFFFF;
    font-size: 13px;
    font-weight: bold;
    padding: 8px 24px;
    min-width: 100px;
}
QPushButton#ActionBtn:hover { background: #1E4A8A; }
QPushButton#ActionBtn:pressed { background: #0E2A5A; }
QPushButton#CancelBtn {
    background: transparent;
    border: 1px solid #3A3A3A;
    border-radius: 4px;
    color: #888888;
    font-size: 13px;
    padding: 8px 20px;
}
QPushButton#CancelBtn:hover { border-color: #666666; color: #CCCCCC; }
QFrame#Divider { color: #2A2A2A; }
QLabel#GpuBadge {
    color: #4A90D9;
    font-size: 11px;
    padding: 2px 0 0 0;
}
QLabel#NoGpuHint {
    color: #666666;
    font-size: 11px;
    padding: 2px 0 0 0;
}
"""

MODEL_HINTS = {
    "tiny":     "Fastest  •  least accurate  •  ~39 MB",
    "base":     "Fast  •  good balance  •  ~74 MB  ✓ Recommended",
    "small":    "Moderate speed  •  better accuracy  •  ~244 MB",
    "medium":   "Slower  •  high accuracy  •  ~769 MB",
    "large-v3": "Slowest  •  best accuracy  •  ~1.5 GB",
}

LANGUAGE_OPTIONS = [
    ("Auto-detect", None),
    ("English",     "en"),
    ("Spanish",     "es"),
    ("French",      "fr"),
    ("German",      "de"),
    ("Italian",     "it"),
    ("Portuguese",  "pt"),
    ("Dutch",       "nl"),
    ("Japanese",    "ja"),
    ("Korean",      "ko"),
    ("Chinese",     "zh"),
    ("Russian",     "ru"),
    ("Arabic",      "ar"),
    ("Hindi",       "hi"),
    ("Turkish",     "tr"),
    ("Polish",      "pl"),
    ("Swedish",     "sv"),
]


class WhisperDialog(QDialog):
    """
    Modal dialog that lets the user pick:
      - Whisper model size
      - Language (or auto-detect)
      - Source (selected bin clip, or all audio in the timeline)

    Result
    ------
    After exec(), if accepted():
        dialog.selected_model        → str        e.g. "base"
        dialog.selected_language     → str | None
        dialog.selected_source       → str        (file path)
        dialog.selected_vad          → bool
        dialog.selected_device       → str        e.g. "cuda:0" or "cpu"
        dialog.selected_compute_type → str        e.g. "float16" or "int8"
    """

    def __init__(
        self,
        bin_path:      Optional[str] = None,   # currently selected bin clip path
        bin_name:      Optional[str] = None,   # display name for that clip
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Transcribe Audio")
        self.setStyleSheet(DIALOG_STYLE)
        self.setModal(True)
        self.setMinimumWidth(380)
        self.setMaximumWidth(480)

        self.bin_path  = bin_path
        self.bin_name  = bin_name or (bin_path or "")

        # Outputs — defaults match WhisperWorker defaults
        self.selected_model:        str          = "base"
        self.selected_language:     Optional[str] = None
        self.selected_source:       str          = bin_path or ""
        self.selected_vad:          bool         = False
        # Device defaults: prefer first GPU if available, else CPU
        _default         = _DEVICES[0]
        self.selected_device:       str          = _default[1]
        self.selected_compute_type: str          = _default[2]

        self._build_ui()
        self._update_hints()

    # -------------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # Title
        title = QLabel("🎙 Transcribe Audio")
        title.setObjectName("DialogTitle")
        root.addWidget(title)

        div = self._divider()
        root.addWidget(div)

        # --- Source selection ---
        src_label = QLabel("SOURCE")
        src_label.setObjectName("SectionLabel")
        root.addWidget(src_label)

        self._source_group = QButtonGroup(self)

        self.radio_bin = QRadioButton(
            f"Selected clip:  {self.bin_name}" if self.bin_path
            else "Selected clip  (none selected)"
        )
        self.radio_bin.setEnabled(bool(self.bin_path))
        self.radio_bin.setChecked(bool(self.bin_path))
        self._source_group.addButton(self.radio_bin, 0)
        root.addWidget(self.radio_bin)

        root.addWidget(self._divider())

        # --- Model selection ---
        model_label = QLabel("MODEL")
        model_label.setObjectName("SectionLabel")
        root.addWidget(model_label)

        self.combo_model = QComboBox()
        for size in MODEL_SIZES:
            self.combo_model.addItem(size)
        self.combo_model.setCurrentText("base")
        self.combo_model.currentTextChanged.connect(self._update_hints)
        root.addWidget(self.combo_model)

        self.hint_label = QLabel()
        self.hint_label.setObjectName("HintLabel")
        root.addWidget(self.hint_label)

        root.addWidget(self._divider())

        # --- Language selection ---
        lang_label = QLabel("LANGUAGE")
        lang_label.setObjectName("SectionLabel")
        root.addWidget(lang_label)

        self.combo_lang = QComboBox()
        for display, code in LANGUAGE_OPTIONS:
            self.combo_lang.addItem(display, userData=code)
        self.combo_lang.setCurrentIndex(0)
        root.addWidget(self.combo_lang)

        root.addWidget(self._divider())

        # --- Options ---
        opt_label = QLabel("OPTIONS")
        opt_label.setObjectName("SectionLabel")
        root.addWidget(opt_label)

        self.chk_vad = QCheckBox("Enable Voice Activity Detection (VAD)")
        self.chk_vad.setStyleSheet("QCheckBox { color:#CCCCCC; font-size:12px; padding:3px 0; }")
        self.chk_vad.setChecked(False)
        self.chk_vad.setToolTip(
            "VAD skips silent sections - can cause 0 segments on music or short clips.\n"
            "Leave OFF for singing/music. Enable for speech with long silences."
        )
        root.addWidget(self.chk_vad)

        vad_hint = QLabel("⚠ Keep OFF for music or singing - VAD may drop all segments")
        vad_hint.setObjectName("HintLabel")
        root.addWidget(vad_hint)

        root.addWidget(self._divider())

        # --- Device selection ---
        dev_label = QLabel("DEVICE")
        dev_label.setObjectName("SectionLabel")
        root.addWidget(dev_label)

        self.combo_device = QComboBox()
        for label, device_str, compute in _DEVICES:
            self.combo_device.addItem(label, userData=(device_str, compute))
        # Default to first entry (GPU if detected, otherwise CPU)
        self.combo_device.setCurrentIndex(0)
        root.addWidget(self.combo_device)

        # Status hint — shows GPU name + compute type, or a nudge to install torch
        if len(_DEVICES) > 1:
            # At least one GPU was detected
            gpu_count = len(_DEVICES) - 1  # exclude the CPU entry
            plural    = "s" if gpu_count > 1 else ""
            dev_hint  = QLabel(f"✓ {gpu_count} CUDA GPU{plural} detected — significantly faster than CPU")
            dev_hint.setObjectName("GpuBadge")
        else:
            dev_hint = QLabel("No CUDA GPU detected  •  install PyTorch with CUDA for GPU speed-up")
            dev_hint.setObjectName("NoGpuHint")
        dev_hint.setWordWrap(True)
        root.addWidget(dev_hint)

        root.addStretch()

        # --- Buttons ---
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("CancelBtn")
        self.btn_cancel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_start = QPushButton("▶  Transcribe")
        self.btn_start.setObjectName("ActionBtn")
        self.btn_start.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_start.clicked.connect(self._on_start)
        self.btn_start.setEnabled(bool(self.bin_path))

        btn_row.addWidget(self.btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_start)
        root.addLayout(btn_row)

    # -------------------------------------------------------------------------

    def _divider(self) -> QFrame:
        d = QFrame()
        d.setObjectName("Divider")
        d.setFrameShape(QFrame.Shape.HLine)
        d.setStyleSheet("color:#2A2A2A;")
        return d

    def _update_hints(self):
        model = self.combo_model.currentText()
        self.hint_label.setText(MODEL_HINTS.get(model, ""))

    def _on_start(self):
        self.selected_model        = self.combo_model.currentText()
        self.selected_language     = self.combo_lang.currentData()
        self.selected_source       = self.bin_path or ""
        self.selected_vad          = self.chk_vad.isChecked()
        device_str, compute        = self.combo_device.currentData()
        self.selected_device       = device_str
        self.selected_compute_type = compute
        self.accept()