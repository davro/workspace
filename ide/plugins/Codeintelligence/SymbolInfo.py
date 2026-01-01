# ide/plugins/Codeintelligene/SymbolInfo.py

"""
SymbolInfo - Complete information about a code symbol
"""

from typing import List, Optional, Dict, Tuple
from pathlib import Path

class SymbolInfo:
    """Complete information about a code symbol"""
    
    def __init__(self, name: str, symbol_type: str, file_path: str, 
                 line: int, column: int = 0, **kwargs):
        self.name = name
        self.type = symbol_type  # 'class', 'function', 'method', etc.
        self.file_path = file_path
        self.line = line
        self.column = column
        
        # Optional attributes
        self.parent = kwargs.get('parent')
        self.children = kwargs.get('children', [])
        self.parameters = kwargs.get('parameters', [])
        self.decorators = kwargs.get('decorators', [])
        self.docstring = kwargs.get('docstring')
        self.bases = kwargs.get('bases', [])
        
        # For reference tracking
        self.references: List[Tuple[str, int, int]] = []  # (file, line, col)
        
        # Computed properties
        self.qualified_name = self._compute_qualified_name()
    
    def _compute_qualified_name(self) -> str:
        """
        Compute fully qualified name
        Example: 'MyClass.my_method' or 'module.function'
        """
        if self.parent:
            return f"{self.parent}.{self.name}"
        return self.name
    
    def get_icon(self) -> str:
        """Get emoji icon for symbol type"""
        icons = {
            'class': '📦',
            'function': '🔧',
            'method': '⚙️',
            'variable': '📊',
            'constant': '🔒',
            'interface': '📋',
            'struct': '🏗️',
            'enum': '🔢',
            'trait': '🎯',
        }
        return icons.get(self.type, '📄')
    
    def get_signature(self) -> str:
        """Get function/method signature"""
        if self.type in ('function', 'method'):
            if self.parameters:
                params = ', '.join(self.parameters)
                return f"{self.name}({params})"
            return f"{self.name}()"
        return self.name
    
    def to_dict(self) -> Dict:
        """Serialize to dictionary for caching"""
        return {
            'name': self.name,
            'type': self.type,
            'file_path': self.file_path,
            'line': self.line,
            'column': self.column,
            'parent': self.parent,
            'children': self.children,
            'parameters': self.parameters,
            'decorators': self.decorators,
            'docstring': self.docstring,
            'bases': self.bases,
            'references': self.references,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SymbolInfo':
        """Deserialize from dictionary"""
        symbol = cls(
            name=data['name'],
            symbol_type=data['type'],
            file_path=data['file_path'],
            line=data['line'],
            column=data.get('column', 0),
            parent=data.get('parent'),
            children=data.get('children', []),
            parameters=data.get('parameters', []),
            decorators=data.get('decorators', []),
            docstring=data.get('docstring'),
            bases=data.get('bases', []),
        )
        symbol.references = data.get('references', [])
        return symbol
    
    def __repr__(self):
        return f"<Symbol {self.qualified_name} ({self.type}) at {Path(self.file_path).name}:{self.line}>"
    
    def __hash__(self):
        return hash((self.qualified_name, self.file_path, self.line))
    
    def __eq__(self, other):
        if not isinstance(other, SymbolInfo):
            return False
        return (self.qualified_name == other.qualified_name and 
                self.file_path == other.file_path and 
                self.line == other.line)


class Reference:
    """Represents a reference to a symbol"""
    
    def __init__(self, file_path: str, line: int, column: int, context: str):
        self.file_path = file_path
        self.line = line
        self.column = column
        self.context = context  # Line of code containing reference
    
    def __repr__(self):
        return f"<Reference {Path(self.file_path).name}:{self.line}:{self.column}>"
    
    def to_dict(self) -> Dict:
        """Serialize to dictionary"""
        return {
            'file_path': self.file_path,
            'line': self.line,
            'column': self.column,
            'context': self.context
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Reference':
        """Deserialize from dictionary"""
        return cls(
            file_path=data['file_path'],
            line=data['line'],
            column=data['column'],
            context=data['context']
        )
