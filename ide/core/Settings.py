# ---------------------- Settings Dialog ----------------------
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QSpinBox,
    QCheckBox,
    QDialogButtonBox,
    QLabel,
)
from PyQt6.QtCore import Qt


class SettingsDialog(QDialog):
    """Settings dialog for IDE configuration"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("IDE Settings")
        self.setMinimumWidth(500)
        self.setModal(True)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        # Explorer Width
        self.explorer_width = QSpinBox()
        self.explorer_width.setRange(150, 600)
        self.explorer_width.setValue(300)
        self.explorer_width.setSuffix(" px")
        form.addRow("Explorer Width:", self.explorer_width)

        # Editor Font Size
        self.editor_font_size = QSpinBox()
        self.editor_font_size.setRange(8, 32)
        self.editor_font_size.setValue(11)
        form.addRow("Editor Font Size:", self.editor_font_size)

        # Tab Width
        self.tab_width = QSpinBox()
        self.tab_width.setRange(2, 8)
        self.tab_width.setValue(4)
        self.tab_width.setSuffix(" spaces")
        form.addRow("Tab Width:", self.tab_width)

        # Gutter Width - FIXED: use 'form' instead of 'editor_layout'
        self.gutter_spin = QSpinBox()
        self.gutter_spin.setRange(0, 50)
        self.gutter_spin.setValue(10)
        self.gutter_spin.setSuffix(" px")
        self.gutter_spin.setToolTip("Padding between line numbers and text")
        form.addRow("Gutter Width (padding):", self.gutter_spin)

        # Checkboxes
        self.restore_session = QCheckBox()
        self.restore_session.setChecked(True)
        form.addRow("Restore Open Tabs on Startup:", self.restore_session)

        self.show_line_numbers = QCheckBox()
        self.show_line_numbers.setChecked(True)
        form.addRow("Show Line Numbers:", self.show_line_numbers)

        self.auto_save = QCheckBox()
        self.auto_save.setChecked(False)
        form.addRow("Auto-save on Tab Switch:", self.auto_save)

        # Ollama Timeout
        self.ollama_timeout = QSpinBox()
        self.ollama_timeout.setRange(30, 1200)
        self.ollama_timeout.setValue(180)
        self.ollama_timeout.setSuffix(" seconds")
        form.addRow("Ollama Request Timeout:", self.ollama_timeout)

        layout.addLayout(form)
        layout.addStretch(1)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_settings(self) -> dict:
        """Return current settings as dict"""
        return {
            'explorer_width': self.explorer_width.value(),
            'editor_font_size': self.editor_font_size.value(),
            'tab_width': self.tab_width.value(),
            'restore_session': self.restore_session.isChecked(),
            'show_line_numbers': self.show_line_numbers.isChecked(),
            'gutter_width': self.gutter_spin.value(),
            'auto_save': self.auto_save.isChecked(),
            'ollama_timeout': self.ollama_timeout.value(),
        }

    def set_settings(self, settings: dict):
        """Load settings into dialog"""
        self.explorer_width.setValue(settings.get('explorer_width', 300))
        self.editor_font_size.setValue(settings.get('editor_font_size', 11))
        self.tab_width.setValue(settings.get('tab_width', 4))
        self.gutter_spin.setValue(settings.get('gutter_width', 10))
        self.restore_session.setChecked(settings.get('restore_session', True))
        self.show_line_numbers.setChecked(settings.get('show_line_numbers', True))
        self.auto_save.setChecked(settings.get('auto_save', False))
        self.ollama_timeout.setValue(settings.get('ollama_timeout', 180))