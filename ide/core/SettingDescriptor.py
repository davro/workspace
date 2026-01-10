# ============================================================================
# SettingDescriptor.py - Base classes for declarative settings
# ============================================================================

from dataclasses import dataclass
from typing import Any, Literal, Optional, List, Tuple
from enum import Enum


class SettingType(Enum):
    """Types of settings that can be configured"""
    INTEGER = "integer"
    BOOLEAN = "boolean"
    CHOICE = "choice"
    STRING = "string"
    FLOAT = "float"


@dataclass
class SettingDescriptor:
    """Describes a single setting and how to render it in the UI"""
    
    key: str                                    # Internal key name
    label: str                                  # Display label
    setting_type: SettingType                   # Type of setting
    default: Any                                # Default value
    description: Optional[str] = None           # Tooltip/help text
    
    # For INTEGER/FLOAT types
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    suffix: Optional[str] = None                # e.g., " px", " seconds"
    
    # For CHOICE type
    choices: Optional[List[Tuple[str, Any]]] = None  # [(display, value), ...]
    
    # UI hints
    section: Optional[str] = None               # Group related settings
    
    def validate(self, value: Any) -> Any:
        """Validate and coerce value to correct type"""
        if self.setting_type == SettingType.INTEGER:
            val = int(value)
            if self.min_value is not None:
                val = max(val, int(self.min_value))
            if self.max_value is not None:
                val = min(val, int(self.max_value))
            return val
            
        elif self.setting_type == SettingType.FLOAT:
            val = float(value)
            if self.min_value is not None:
                val = max(val, self.min_value)
            if self.max_value is not None:
                val = min(val, self.max_value)
            return val
            
        elif self.setting_type == SettingType.BOOLEAN:
            return bool(value)
            
        elif self.setting_type == SettingType.CHOICE:
            # Ensure value is in choices
            valid_values = [v for _, v in self.choices]
            return value if value in valid_values else self.default
            
        elif self.setting_type == SettingType.STRING:
            return str(value)
            
        return value


class SettingsProvider:
    """Base class for components that provide settings"""
    
    # Each subclass should override this
    SETTINGS_DESCRIPTORS: List[SettingDescriptor] = []
    
    @classmethod
    def get_setting_descriptors(cls) -> List[SettingDescriptor]:
        """Return list of setting descriptors for this component"""
        return cls.SETTINGS_DESCRIPTORS
    
    @classmethod
    def get_default_settings(cls) -> dict:
        """Get default settings as a dict"""
        return {
            desc.key: desc.default 
            for desc in cls.SETTINGS_DESCRIPTORS
        }
    
    @classmethod
    def validate_settings(cls, settings: dict) -> dict:
        """Validate and return corrected settings"""
        validated = {}
        for desc in cls.SETTINGS_DESCRIPTORS:
            if desc.key in settings:
                validated[desc.key] = desc.validate(settings[desc.key])
            else:
                validated[desc.key] = desc.default
        return validated
