# ============================================================================
# managers/SettingsManager.py - Manages application settings persistence
# ============================================================================

import json
from pathlib import Path
from typing import List, Type
from ide.core.SettingDescriptor import SettingType, SettingsProvider, SettingDescriptor


class SettingsManager:
    """Manages application settings persistence with component registration"""

    def __init__(self, config_file):
        self.config_file = config_file
        self.providers: List[Type[SettingsProvider]] = []
        self.settings = {}
        
    def register_provider(self, provider_class: Type[SettingsProvider]):
        """Register a settings provider (Workspace, CodeEditor, etc.)"""
        print (f"Provider: {provider_class}")
        if provider_class not in self.providers:
            self.providers.append(provider_class)
    
    def get_all_descriptors(self):
        """Get all setting descriptors from all registered providers"""
        descriptors = []
        for provider in self.providers:
            descriptors.extend(provider.get_setting_descriptors())
        return descriptors
    
    def get_default_settings(self):
        """Build default settings from all registered providers"""
        defaults = {}
        for provider in self.providers:
            provider_get_default_settings = provider.get_default_settings()
            # print (f"Provider: {provider_get_default_settings}")
            defaults.update(provider_get_default_settings)
        return defaults
    
    def load(self):
        """Load settings from file"""
        defaults = self.get_default_settings()
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    loaded = json.load(f)
                    # Merge with defaults to handle new settings
                    self.settings = {**defaults, **loaded}
            except Exception as e:
                print(f"Error loading settings: {e}")
                self.settings = defaults.copy()
        else:
            self.settings = defaults.copy()
        
        # Validate all settings
        self.validate_all()
        return self.settings

    def validate_all(self):
        """Validate all settings using their descriptors"""
        for provider in self.providers:
            validated = provider.validate_settings(self.settings)
            self.settings.update(validated)

    def save(self):
        """Save settings to file"""
        try:
            # Validate before saving
            self.validate_all()
            
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
        self.validate_all()
    
    def get_settings_by_section(self):
        """Group settings by section for organized UI display"""
        sections = {}
        for desc in self.get_all_descriptors():
            section = desc.section or 'General'
            if section not in sections:
                sections[section] = []
            sections[section].append(desc)
        return sections
