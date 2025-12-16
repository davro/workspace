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

# If you're using PySide6 instead, replace the imports above with:
# from PySide6.QtWidgets import (
#     QDialog, QVBoxLayout, QFormLayout, QSpinBox,
#     QCheckBox, QDialogButtonBox, QLabel
# )
# from PySide6.QtCore import Qt


class SettingsDialog(QDialog):
    """Settings dialog for IDE configuration"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("IDE Settings")
        self.setMinimumWidth(500)
        self.setModal(True)  # Good practice: block interaction with main window

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

        # Terminal Height
        self.terminal_height = QSpinBox()
        self.terminal_height.setRange(100, 800)
        self.terminal_height.setValue(200)
        self.terminal_height.setSuffix(" px")
        form.addRow("Terminal Height:", self.terminal_height)

        # Editor Font Size
        self.editor_font_size = QSpinBox()
        self.editor_font_size.setRange(8, 32)
        self.editor_font_size.setValue(11)
        form.addRow("Editor Font Size:", self.editor_font_size)

        # Terminal Font Size
        self.terminal_font_size = QSpinBox()
        self.terminal_font_size.setRange(8, 24)
        self.terminal_font_size.setValue(10)
        form.addRow("Terminal Font Size:", self.terminal_font_size)

        # Tab Width
        self.tab_width = QSpinBox()
        self.tab_width.setRange(2, 8)
        self.tab_width.setValue(4)
        self.tab_width.setSuffix(" spaces")
        form.addRow("Tab Width:", self.tab_width)

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

        # Add some spacing before buttons
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
            'terminal_height': self.terminal_height.value(),
            'editor_font_size': self.editor_font_size.value(),
            'terminal_font_size': self.terminal_font_size.value(),
            'tab_width': self.tab_width.value(),
            'restore_session': self.restore_session.isChecked(),
            'show_line_numbers': self.show_line_numbers.isChecked(),
            'auto_save': self.auto_save.isChecked(),
            'ollama_timeout': self.ollama_timeout.value(),
        }

    def set_settings(self, settings: dict):
        """Load settings into dialog"""
        self.explorer_width.setValue(settings.get('explorer_width', 300))
        self.terminal_height.setValue(settings.get('terminal_height', 200))
        self.editor_font_size.setValue(settings.get('editor_font_size', 11))
        self.terminal_font_size.setValue(settings.get('terminal_font_size', 10))
        self.tab_width.setValue(settings.get('tab_width', 4))
        self.restore_session.setChecked(settings.get('restore_session', True))
        self.show_line_numbers.setChecked(settings.get('show_line_numbers', True))
        self.auto_save.setChecked(settings.get('auto_save', False))
        self.ollama_timeout.setValue(settings.get('ollama_timeout', 180))



#OLD
# ---------------------- Settings Dialog ----------------------
# class SettingsDialog(QDialog):
    # """Settings dialog for IDE configuration"""

    # def __init__(self, parent=None):
        # super().__init__(parent)
        # self.setWindowTitle("IDE Settings")
        # self.setMinimumWidth(500)

        # layout = QVBoxLayout(self)
        # form = QFormLayout()

        # self.explorer_width = QSpinBox()
        # self.explorer_width.setRange(150, 500)
        # self.explorer_width.setValue(300)
        # self.explorer_width.setSuffix(" px")
        # form.addRow("Explorer Width:", self.explorer_width)

        # self.terminal_height = QSpinBox()
        # self.terminal_height.setRange(100, 600)
        # self.terminal_height.setValue(200)
        # self.terminal_height.setSuffix(" px")
        # form.addRow("Terminal Height:", self.terminal_height)

        # self.editor_font_size = QSpinBox()
        # self.editor_font_size.setRange(8, 24)
        # self.editor_font_size.setValue(11)
        # form.addRow("Editor Font Size:", self.editor_font_size)

        # self.terminal_font_size = QSpinBox()
        # self.terminal_font_size.setRange(8, 18)
        # self.terminal_font_size.setValue(10)
        # form.addRow("Terminal Font Size:", self.terminal_font_size)

        # self.tab_width = QSpinBox()
        # self.tab_width.setRange(2, 8)
        # self.tab_width.setValue(4)
        # self.tab_width.setSuffix(" spaces")
        # form.addRow("Tab Width:", self.tab_width)

        # self.restore_session = QCheckBox()
        # self.restore_session.setChecked(True)
        # form.addRow("Restore Open Tabs:", self.restore_session)

        # self.show_line_numbers = QCheckBox()
        # self.show_line_numbers.setChecked(True)
        # form.addRow("Show Line Numbers:", self.show_line_numbers)

        # self.auto_save = QCheckBox()
        # self.auto_save.setChecked(False)
        # form.addRow("Auto-save on Tab Switch:", self.auto_save)

        # self.ollama_timeout = QSpinBox()
        # self.ollama_timeout.setRange(30, 600)
        # self.ollama_timeout.setValue(180)
        # self.ollama_timeout.setSuffix(" seconds")
        # form.addRow("Ollama Timeout:", self.ollama_timeout)

        # layout.addLayout(form)

        # buttons = QDialogButtonBox(
            # QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        # )
        # buttons.accepted.connect(self.accept)
        # buttons.rejected.connect(self.reject)
        # layout.addWidget(buttons)

    # def get_settings(self):
        # """Return current settings as dict"""
        # return {
            # 'explorer_width': self.explorer_width.value(),
            # 'terminal_height': self.terminal_height.value(),
            # 'editor_font_size': self.editor_font_size.value(),
            # 'terminal_font_size': self.terminal_font_size.value(),
            # 'tab_width': self.tab_width.value(),
            # 'restore_session': self.restore_session.isChecked(),
            # 'show_line_numbers': self.show_line_numbers.isChecked(),
            # 'auto_save': self.auto_save.isChecked(),
            # 'ollama_timeout': self.ollama_timeout.value()
        # }

    # def set_settings(self, settings):
        # """Load settings into dialog"""
        # self.explorer_width.setValue(settings.get('explorer_width', 300))
        # self.terminal_height.setValue(settings.get('terminal_height', 200))
        # self.editor_font_size.setValue(settings.get('editor_font_size', 11))
        # self.terminal_font_size.setValue(settings.get('terminal_font_size', 10))
        # self.tab_width.setValue(settings.get('tab_width', 4))
        # self.restore_session.setChecked(settings.get('restore_session', True))
        # self.show_line_numbers.setChecked(settings.get('show_line_numbers', True))
        # self.auto_save.setChecked(settings.get('auto_save', False))
        # self.ollama_timeout.setValue(settings.get('ollama_timeout', 180))
