# ============================================================================
# SettingsDialog.py - Dynamic settings dialog
# ============================================================================

"""
SettingsDialog - Automatically builds UI from SettingDescriptors
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QSpinBox, QCheckBox, QComboBox,
    QDialogButtonBox, QLabel, QGroupBox, QDoubleSpinBox, QLineEdit, QScrollArea,
    QWidget
)
from PyQt6.QtCore import Qt
from ide.core.SettingDescriptor import SettingType, SettingsProvider, SettingDescriptor
from typing import Dict, Any


class SettingsDialog(QDialog, SettingsProvider):
    """Dynamic settings dialog that builds UI from SettingDescriptors"""

    SETTINGS_DESCRIPTORS = [
        SettingDescriptor(
            key='widget_resizable',
            label='Widget Resizable',
            setting_type=SettingType.BOOLEAN,
            default=True,
            description='Settings Widget Resizable',
            section='Settings'
        ),
    ]

    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.widgets: Dict[str, Any] = {}  # Map setting key to widget
        
        self.setWindowTitle("IDE Settings")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self.setModal(True)

        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Scroll area for settings
        scroll = QScrollArea()
        # scroll.setWidgetResizable(True)
        scroll.setWidgetResizable(self.settings_manager.get('widget_resizable', True))
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # Build UI from settings descriptors
        self._build_ui(scroll_layout)
        
        scroll.setWidget(scroll_widget)
        main_layout.addWidget(scroll)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)
        
        # Load current settings
        self.set_settings(settings_manager.settings)

    def _build_ui(self, layout):
        """Build UI from all registered setting descriptors"""
        # Group by section
        sections = self.settings_manager.get_settings_by_section()
        
        for section_name in sorted(sections.keys()):
            descriptors = sections[section_name]
            
            # Create group box for section
            group = QGroupBox(section_name)
            form = QFormLayout()
            form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
            form.setFormAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
            )
            
            for desc in descriptors:
                widget = self._create_widget_for_descriptor(desc)
                self.widgets[desc.key] = widget
                
                label = QLabel(desc.label + ":")
                if desc.description:
                    widget.setToolTip(desc.description)
                    label.setToolTip(desc.description)
                
                form.addRow(label, widget)
            
            group.setLayout(form)
            layout.addWidget(group)
        
        layout.addStretch(1)

    def _create_widget_for_descriptor(self, desc: SettingDescriptor):
        """Create appropriate Qt widget based on descriptor type"""
        
        if desc.setting_type == SettingType.INTEGER:
            widget = QSpinBox()
            if desc.min_value is not None:
                widget.setRange(int(desc.min_value), int(desc.max_value or 999999))
            if desc.suffix:
                widget.setSuffix(desc.suffix)
            widget.setValue(desc.default)
            return widget
        
        elif desc.setting_type == SettingType.FLOAT:
            widget = QDoubleSpinBox()
            if desc.min_value is not None:
                widget.setRange(desc.min_value, desc.max_value or 999999.0)
            if desc.suffix:
                widget.setSuffix(desc.suffix)
            widget.setValue(desc.default)
            return widget
        
        elif desc.setting_type == SettingType.BOOLEAN:
            widget = QCheckBox()
            widget.setChecked(desc.default)
            return widget
        
        elif desc.setting_type == SettingType.CHOICE:
            widget = QComboBox()
            for display_text, value in desc.choices:
                widget.addItem(display_text, value)
            return widget
        
        elif desc.setting_type == SettingType.STRING:
            widget = QLineEdit()
            widget.setText(str(desc.default))
            return widget
        
        # Fallback
        return QLabel("Unsupported type")

    def get_settings(self) -> dict:
        """Extract current settings from all widgets"""
        settings = {}
        
        for desc in self.settings_manager.get_all_descriptors():
            widget = self.widgets.get(desc.key)
            if widget is None:
                continue
            
            if desc.setting_type == SettingType.INTEGER:
                settings[desc.key] = widget.value()
            
            elif desc.setting_type == SettingType.FLOAT:
                settings[desc.key] = widget.value()
            
            elif desc.setting_type == SettingType.BOOLEAN:
                settings[desc.key] = widget.isChecked()
            
            elif desc.setting_type == SettingType.CHOICE:
                settings[desc.key] = widget.currentData()
            
            elif desc.setting_type == SettingType.STRING:
                settings[desc.key] = widget.text()
        
        return settings

    def set_settings(self, settings: dict):
        """Load settings into all widgets"""
        for desc in self.settings_manager.get_all_descriptors():
            widget = self.widgets.get(desc.key)
            if widget is None:
                continue
            
            value = settings.get(desc.key, desc.default)
            
            if desc.setting_type == SettingType.INTEGER:
                widget.setValue(int(value))
            
            elif desc.setting_type == SettingType.FLOAT:
                widget.setValue(float(value))
            
            elif desc.setting_type == SettingType.BOOLEAN:
                widget.setChecked(bool(value))
            
            elif desc.setting_type == SettingType.CHOICE:
                # Find matching value in combo box
                for i in range(widget.count()):
                    if widget.itemData(i) == value:
                        widget.setCurrentIndex(i)
                        break
            
            elif desc.setting_type == SettingType.STRING:
                widget.setText(str(value))
