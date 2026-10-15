# ide/plugins/Codeintelligence/__init__.py

"""
Code Intelligence Package

Components:
- SymbolInfo: Symbol data structure
- SymbolDatabase: Storage and indexing
- SymbolIndexer: File parsing
- NavigationManager: Jump-to-definition
- ReferenceTracker: Find all references
- SymbolSearchDialog: Quick search UI
- SymbolPanelWidget: Symbols tree (sidebar)
- ReferencesPanel: Find All References results (sidebar)
"""

from .SymbolInfo import SymbolInfo, Reference
from .SymbolDatabase import SymbolDatabase
from .SymbolIndexer import SymbolIndexer
from .NavigationManager import NavigationManager
from .ReferenceTracker import ReferenceTracker
from .SymbolSearchDialog import SymbolSearchDialog
from .SymbolPanelWidget import SymbolPanelWidget
from .ReferencesPanel import ReferencesPanel


__all__ = [
    'SymbolInfo', 'Reference', 'SymbolDatabase', 'SymbolIndexer',
    'NavigationManager', 'ReferenceTracker', 'SymbolSearchDialog',
    'SymbolPanelWidget', 'ReferencesPanel',
]