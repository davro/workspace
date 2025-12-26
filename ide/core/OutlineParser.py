# ============================================================================
# OutlineParser.py in ide/core/
# ============================================================================

"""
Multi-language code outline parser
Extracts symbols (classes, functions, methods) from source code
"""

import ast
import re
from pathlib import Path
from typing import List, Dict, Optional


class Symbol:
    """Represents a code symbol (class, function, method, etc.)"""
    
    def __init__(self, name: str, symbol_type: str, line: int, 
                 parent: Optional['Symbol'] = None, children: Optional[List['Symbol']] = None):
        self.name = name
        self.type = symbol_type  # 'class', 'function', 'method', etc.
        self.line = line
        self.parent = parent
        self.children = children or []
    
    def add_child(self, child: 'Symbol'):
        """Add a child symbol"""
        child.parent = self
        self.children.append(child)
    
    def get_icon(self) -> str:
        """Get emoji icon for symbol type"""
        icons = {
            'class': '📦',
            'function': '🔧',
            'method': '🔧',
            'variable': '🔢',
            'constant': '🔒',
            'interface': '📋',
            'struct': '📊',
            'enum': '📑',
            'trait': '🎯',
            'tag': '🏷️',
            'id': '#️⃣',
            'selector': '🎨',
            'property': '⚙️',
            'key': '🔑',
        }
        return icons.get(self.type, '📄')


class OutlineParser:
    """Factory class for creating language-specific parsers"""
    
    @staticmethod
    def parse(file_path: str, content: str) -> List[Symbol]:
        """
        Parse file and return list of symbols
        
        Args:
            file_path: Path to the file
            content: File content as string
            
        Returns:
            List of Symbol objects
        """
        ext = Path(file_path).suffix.lower()
        
        parsers = {
            '.py': PythonParser,
            '.php': PHPParser,
            '.go': GoParser,
            '.rs': RustParser,
            '.html': HTMLParser,
            '.htm': HTMLParser,
            '.css': CSSParser,
            '.scss': CSSParser,
            '.sass': CSSParser,
            '.json': JSONParser,
            '.js': JavaScriptParser,
            '.ts': JavaScriptParser,
            '.jsx': JavaScriptParser,
            '.tsx': JavaScriptParser,
            '.java': JavaParser,
            '.c': CParser,
            '.cpp': CppParser,
            '.h': CppParser,
            '.rb': RubyParser,
        }
        
        parser_class = parsers.get(ext)
        if parser_class:
            try:
                return parser_class.parse(content)
            except Exception as e:
                print(f"Error parsing {file_path}: {e}")
                return []
        
        return []


# ============================================================================
# Python Parser
# ============================================================================

class PythonParser:
    """Parse Python files using AST"""
    
    @staticmethod
    def parse(content: str) -> List[Symbol]:
        try:
            tree = ast.parse(content)
            symbols = []
            
            # First pass: collect all classes with their methods
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    class_symbol = Symbol(node.name, 'class', node.lineno)
                    
                    # Add methods that are direct children of this class
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            method_symbol = Symbol(item.name, 'method', item.lineno)
                            class_symbol.add_child(method_symbol)
                    
                    symbols.append(class_symbol)
                
                elif isinstance(node, ast.FunctionDef):
                    # Top-level function (not inside a class)
                    symbols.append(Symbol(node.name, 'function', node.lineno))
            
            return sorted(symbols, key=lambda s: s.line)
        
        except SyntaxError as e:
            print(f"Syntax error parsing Python: {e}")
            return []
        except Exception as e:
            print(f"Error parsing Python: {e}")
            return []


# ============================================================================
# PHP Parser
# ============================================================================

class PHPParser:
    """Parse PHP files using regex"""
    
    @staticmethod
    def parse(content: str) -> List[Symbol]:
        symbols = []
        
        # Parse classes
        class_pattern = r'class\s+(\w+)'
        for match in re.finditer(class_pattern, content, re.MULTILINE):
            line = content[:match.start()].count('\n') + 1
            symbols.append(Symbol(match.group(1), 'class', line))
        
        # Parse functions
        func_pattern = r'function\s+(\w+)\s*\('
        for match in re.finditer(func_pattern, content, re.MULTILINE):
            line = content[:match.start()].count('\n') + 1
            symbols.append(Symbol(match.group(1), 'function', line))
        
        return sorted(symbols, key=lambda s: s.line)


# ============================================================================
# Go Parser
# ============================================================================

class GoParser:
    """Parse Go files using regex"""
    
    @staticmethod
    def parse(content: str) -> List[Symbol]:
        symbols = []
        
        # Parse structs
        struct_pattern = r'type\s+(\w+)\s+struct'
        for match in re.finditer(struct_pattern, content, re.MULTILINE):
            line = content[:match.start()].count('\n') + 1
            symbols.append(Symbol(match.group(1), 'struct', line))
        
        # Parse interfaces
        interface_pattern = r'type\s+(\w+)\s+interface'
        for match in re.finditer(interface_pattern, content, re.MULTILINE):
            line = content[:match.start()].count('\n') + 1
            symbols.append(Symbol(match.group(1), 'interface', line))
        
        # Parse functions
        func_pattern = r'func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\('
        for match in re.finditer(func_pattern, content, re.MULTILINE):
            line = content[:match.start()].count('\n') + 1
            symbols.append(Symbol(match.group(1), 'function', line))
        
        return sorted(symbols, key=lambda s: s.line)


# ============================================================================
# Rust Parser
# ============================================================================

class RustParser:
    """Parse Rust files using regex"""
    
    @staticmethod
    def parse(content: str) -> List[Symbol]:
        symbols = []
        
        # Parse structs
        struct_pattern = r'struct\s+(\w+)'
        for match in re.finditer(struct_pattern, content, re.MULTILINE):
            line = content[:match.start()].count('\n') + 1
            symbols.append(Symbol(match.group(1), 'struct', line))
        
        # Parse enums
        enum_pattern = r'enum\s+(\w+)'
        for match in re.finditer(enum_pattern, content, re.MULTILINE):
            line = content[:match.start()].count('\n') + 1
            symbols.append(Symbol(match.group(1), 'enum', line))
        
        # Parse traits
        trait_pattern = r'trait\s+(\w+)'
        for match in re.finditer(trait_pattern, content, re.MULTILINE):
            line = content[:match.start()].count('\n') + 1
            symbols.append(Symbol(match.group(1), 'trait', line))
        
        # Parse functions
        func_pattern = r'fn\s+(\w+)\s*(?:<[^>]*>)?\s*\('
        for match in re.finditer(func_pattern, content, re.MULTILINE):
            line = content[:match.start()].count('\n') + 1
            symbols.append(Symbol(match.group(1), 'function', line))
        
        return sorted(symbols, key=lambda s: s.line)


# ============================================================================
# HTML Parser
# ============================================================================

class HTMLParser:
    """Parse HTML files - extract tags with IDs"""
    
    @staticmethod
    def parse(content: str) -> List[Symbol]:
        symbols = []
        
        # Parse tags with IDs
        id_pattern = r'<(\w+)[^>]*\sid=["\']([^"\']+)["\']'
        for match in re.finditer(id_pattern, content, re.MULTILINE):
            line = content[:match.start()].count('\n') + 1
            tag_name = match.group(1)
            id_value = match.group(2)
            symbols.append(Symbol(f"#{id_value} ({tag_name})", 'id', line))
        
        return sorted(symbols, key=lambda s: s.line)


# ============================================================================
# CSS Parser
# ============================================================================

class CSSParser:
    """Parse CSS files - extract selectors"""
    
    @staticmethod
    def parse(content: str) -> List[Symbol]:
        symbols = []
        
        # Parse selectors (simplified)
        selector_pattern = r'^([.#]?[\w-]+(?:\s*[>+~]\s*[\w-]+)*)\s*\{'
        for match in re.finditer(selector_pattern, content, re.MULTILINE):
            line = content[:match.start()].count('\n') + 1
            selector = match.group(1).strip()
            symbols.append(Symbol(selector, 'selector', line))
        
        return sorted(symbols, key=lambda s: s.line)


# ============================================================================
# JSON Parser
# ============================================================================

class JSONParser:
    """Parse JSON files - extract top-level keys"""
    
    @staticmethod
    def parse(content: str) -> List[Symbol]:
        import json
        symbols = []
        
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                for key in data.keys():
                    # Find line number by searching for the key
                    pattern = rf'"{re.escape(key)}"'
                    match = re.search(pattern, content)
                    if match:
                        line = content[:match.start()].count('\n') + 1
                        symbols.append(Symbol(key, 'key', line))
        except json.JSONDecodeError:
            pass
        
        return symbols


# ============================================================================
# JavaScript/TypeScript Parser
# ============================================================================

class JavaScriptParser:
    """Parse JavaScript/TypeScript files using regex"""
    
    @staticmethod
    def parse(content: str) -> List[Symbol]:
        symbols = []
        
        # Parse classes
        class_pattern = r'class\s+(\w+)'
        for match in re.finditer(class_pattern, content, re.MULTILINE):
            line = content[:match.start()].count('\n') + 1
            symbols.append(Symbol(match.group(1), 'class', line))
        
        # Parse functions (including arrow functions)
        func_pattern = r'(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)'
        for match in re.finditer(func_pattern, content, re.MULTILINE):
            line = content[:match.start()].count('\n') + 1
            name = match.group(1) or match.group(2)
            if name:
                symbols.append(Symbol(name, 'function', line))
        
        return sorted(symbols, key=lambda s: s.line)


# ============================================================================
# Java Parser
# ============================================================================

class JavaParser:
    """Parse Java files using regex"""
    
    @staticmethod
    def parse(content: str) -> List[Symbol]:
        symbols = []
        
        # Parse classes
        class_pattern = r'(?:public\s+)?(?:abstract\s+)?class\s+(\w+)'
        for match in re.finditer(class_pattern, content, re.MULTILINE):
            line = content[:match.start()].count('\n') + 1
            symbols.append(Symbol(match.group(1), 'class', line))
        
        # Parse interfaces
        interface_pattern = r'(?:public\s+)?interface\s+(\w+)'
        for match in re.finditer(interface_pattern, content, re.MULTILINE):
            line = content[:match.start()].count('\n') + 1
            symbols.append(Symbol(match.group(1), 'interface', line))
        
        # Parse methods
        method_pattern = r'(?:public|private|protected)?\s+(?:static\s+)?(?:\w+(?:<[^>]+>)?)\s+(\w+)\s*\('
        for match in re.finditer(method_pattern, content, re.MULTILINE):
            line = content[:match.start()].count('\n') + 1
            symbols.append(Symbol(match.group(1), 'method', line))
        
        return sorted(symbols, key=lambda s: s.line)


# ============================================================================
# C Parser
# ============================================================================

class CParser:
    """Parse C files using regex"""
    
    @staticmethod
    def parse(content: str) -> List[Symbol]:
        symbols = []
        
        # Parse structs
        struct_pattern = r'(?:typedef\s+)?struct\s+(\w+)'
        for match in re.finditer(struct_pattern, content, re.MULTILINE):
            line = content[:match.start()].count('\n') + 1
            symbols.append(Symbol(match.group(1), 'struct', line))
        
        # Parse functions
        func_pattern = r'^(?:\w+\s+)+(\w+)\s*\([^)]*\)\s*\{'
        for match in re.finditer(func_pattern, content, re.MULTILINE):
            line = content[:match.start()].count('\n') + 1
            symbols.append(Symbol(match.group(1), 'function', line))
        
        return sorted(symbols, key=lambda s: s.line)


# ============================================================================
# C++ Parser
# ============================================================================

class CppParser:
    """Parse C++ files using regex"""
    
    @staticmethod
    def parse(content: str) -> List[Symbol]:
        symbols = []
        
        # Parse classes
        class_pattern = r'class\s+(\w+)'
        for match in re.finditer(class_pattern, content, re.MULTILINE):
            line = content[:match.start()].count('\n') + 1
            symbols.append(Symbol(match.group(1), 'class', line))
        
        # Parse structs
        struct_pattern = r'struct\s+(\w+)'
        for match in re.finditer(struct_pattern, content, re.MULTILINE):
            line = content[:match.start()].count('\n') + 1
            symbols.append(Symbol(match.group(1), 'struct', line))
        
        # Parse functions/methods
        func_pattern = r'(?:[\w:]+\s+)+(\w+)\s*\([^)]*\)\s*(?:const)?\s*\{'
        for match in re.finditer(func_pattern, content, re.MULTILINE):
            line = content[:match.start()].count('\n') + 1
            symbols.append(Symbol(match.group(1), 'function', line))
        
        return sorted(symbols, key=lambda s: s.line)


# ============================================================================
# Ruby Parser
# ============================================================================

class RubyParser:
    """Parse Ruby files using regex"""
    
    @staticmethod
    def parse(content: str) -> List[Symbol]:
        symbols = []
        
        # Parse classes
        class_pattern = r'class\s+(\w+)'
        for match in re.finditer(class_pattern, content, re.MULTILINE):
            line = content[:match.start()].count('\n') + 1
            symbols.append(Symbol(match.group(1), 'class', line))
        
        # Parse modules
        module_pattern = r'module\s+(\w+)'
        for match in re.finditer(module_pattern, content, re.MULTILINE):
            line = content[:match.start()].count('\n') + 1
            symbols.append(Symbol(match.group(1), 'class', line))  # Use 'class' icon
        
        # Parse methods
        def_pattern = r'def\s+(\w+)'
        for match in re.finditer(def_pattern, content, re.MULTILINE):
            line = content[:match.start()].count('\n') + 1
            symbols.append(Symbol(match.group(1), 'function', line))
        
        return sorted(symbols, key=lambda s: s.line)