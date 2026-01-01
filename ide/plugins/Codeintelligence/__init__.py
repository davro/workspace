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
- SymbolPanelWidget: Sidebar panel UI
"""

from .SymbolInfo import SymbolInfo, Reference
from .SymbolDatabase import SymbolDatabase
from .SymbolIndexer import SymbolIndexer
from .NavigationManager import NavigationManager
from .ReferenceTracker import ReferenceTracker
from .SymbolSearchDialog import SymbolSearchDialog
from .SymbolPanelWidget import SymbolPanelWidget


# __all__ = [
    # 'SymbolInfo',
    # 'Reference',
    # 'SymbolDatabase',
    # 'SymbolIndexer',
    # 'NavigationManager',
    # 'ReferenceTracker',
    # 'SymbolSearchDialog',
    # 'SymbolPanelWidget',
# ]