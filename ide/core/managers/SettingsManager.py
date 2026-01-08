# ============================================================================
# managers/settings_manager.py
# ============================================================================

import json
from pathlib import Path


class SettingsManager:
    """Manages application settings persistence"""

    DEFAULT_SETTINGS = {
        'explorer_width': 300,
        'terminal_height': 200,
        'editor_font_size': 11,
        'terminal_font_size': 10,
        'tab_width': 4,
        'restore_session': True,
        'show_line_numbers': True,
        'auto_save': False,
        'ollama_timeout': 180,
        'active_projects': [],
        'recent_files': [],
        'gutter_width': 10,					# CodeEditor gutter width
		'tab_switcher_mru': True,			# Enable MRU tab navigation

        'ollama_context_level': 'smart',	# Options: 'minimal', 'basic', 'smart'
        'ollama_show_context_dialog': True	# Show preview dialog before sending
    }

    def __init__(self, config_file):
        self.config_file = config_file
        self.settings = self.load()

    def load(self):
        """Load settings from file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    loaded = json.load(f)
                    # Merge with defaults to handle new settings
                    return {**self.DEFAULT_SETTINGS, **loaded}
            except Exception as e:
                print(f"Error loading settings: {e}")

        return self.DEFAULT_SETTINGS.copy()

    def save(self):
        """Save settings to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False

    def get(self, key, default=None):
        """Get a setting value"""
        return self.settings.get(key, default)

    def set(self, key, value):
        """Set a setting value"""
        self.settings[key] = value

    def update(self, new_settings):
        """Update multiple settings at once"""
        self.settings.update(new_settings)

