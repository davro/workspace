"""
Example Plugin for Workspace IDE

Plugin structure:
- PLUGIN_NAME: Display name for the plugin
- PLUGIN_VERSION: Plugin version
- get_widget(parent): Returns a QWidget to display in tab
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QTextEdit
from PyQt6.QtCore import Qt

PLUGIN_NAME = "Example Plugin"
PLUGIN_VERSION = "1.0.0"


def get_widget(parent=None):
    """
    This function must return a QWidget that will be displayed in the editor tab.
    
    Args:
        parent: Parent widget (usually None or the tab widget)
    
    Returns:
        QWidget: Your plugin's main widget
    """
    widget = QWidget(parent)
    layout = QVBoxLayout(widget)
    
    # Add your plugin UI here
    title = QLabel("🔌 Example Plugin")
    title.setStyleSheet("font-size: 18px; font-weight: bold; color: #4A9EFF;")
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(title)
    
    info = QLabel(
        "This is an example plugin.\n\n"
        "Create your own plugin by copying this file and modifying it.\n"
        "Your plugin must have:\n"
        "  • PLUGIN_NAME constant\n"
        "  • get_widget() function that returns a QWidget"
    )
    info.setStyleSheet("color: #CCC; padding: 20px;")
    info.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(info)
    
    # Example interactive element
    button = QPushButton("Click Me!")
    button.clicked.connect(lambda: text_area.append("Button clicked!\n"))
    layout.addWidget(button)
    
    text_area = QTextEdit()
    text_area.setPlaceholderText("Plugin output will appear here...")
    text_area.setStyleSheet("background: #1E1E1E; color: #CCC; border: 1px solid #555;")
    layout.addWidget(text_area)
    
    return widget


# Optional: Add cleanup function if needed
def cleanup():
    """Called when plugin is unloaded (optional)"""
    pass
