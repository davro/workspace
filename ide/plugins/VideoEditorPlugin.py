"""
Video Editor Plugin for Workspace IDE

A professional non-linear video editor built as a plugin.
Powered by FFmpeg for all media operations.

Features:
- Import and organise video/audio/image clips
- Non-linear timeline with drag-and-drop editing
- Real-time preview with transport controls
- FFmpeg-powered export with format/quality options
- Frame-accurate trimming and splitting

Author: Workspace IDE
Version: 0.1.0
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt


class VideoEditorPlugin:
    """
    Video Editor Plugin — Non-linear video editing inside Workspace IDE.
    """

    # =========================================================================
    # Plugin Metadata
    # =========================================================================

    PLUGIN_NAME        = "Video Editor"
    PLUGIN_VERSION     = "0.1.0"
    PLUGIN_DESCRIPTION = "Professional non-linear video editor powered by FFmpeg"
    PLUGIN_RUN_ON_STARTUP = True
    PLUGIN_HAS_UI      = True
    PLUGIN_ICON        = "🎬"
    PLUGIN_DEPENDENCIES = ["ffmpeg-python", "opencv-python"]

    # =========================================================================
    # Lifecycle
    # =========================================================================

    def __init__(self, api):
        self.api         = api
        self.initialized = False
        self.widget      = None

        print(f"[{self.PLUGIN_NAME}] Instance created")

    def initialize(self):
        if self.initialized:
            return

        print(f"[{self.PLUGIN_NAME}] Initializing...")

        # Keyboard shortcuts
        self.api.register_keyboard_shortcut(
            'Ctrl+Shift+V',
            self._focus_plugin,
            'Video Editor: Show Panel'
        )

        self.initialized = True
        self.api.show_status_message("🎬 Video Editor ready", 2000)
        print(f"[{self.PLUGIN_NAME}] Initialized")

    def get_widget(self, parent=None):
        """Return the main UI widget."""
        # Import here to keep startup fast and avoid hard dep at load time
        from VideoEditorPlugin.VideoEditorWidget import VideoEditorWidget
        self.widget = VideoEditorWidget(self, parent)
        return self.widget

    def cleanup(self):
        print(f"[{self.PLUGIN_NAME}] Cleaning up...")
        if self.widget:
            self.widget.cleanup()
        if self.api:
            self.api.unregister_all_plugin_hooks('video_editor_plugin')
        self.initialized = False
        print(f"[{self.PLUGIN_NAME}] Cleaned up")

    # =========================================================================
    # Internal helpers
    # =========================================================================

    def _focus_plugin(self):
        self.api.show_status_message("🎬 Video Editor", 1500)
