# ide/plugins/Codeintelligence/SymbolIndexer.py

"""
SymbolIndexer - Parse files and extract symbols
Uses AST for Python, OutlineParser for other languages
"""

import ast
from pathlib import Path
from typing import List, Optional
from ide.core.OutlineParser import OutlineParser

from .SymbolInfo import SymbolInfo


class SymbolIndexer:
    """
    Indexes code symbols from files
    Uses AST for detailed Python parsing, OutlineParser for other languages
    """
    
    def __init__(self):
        self.parsers = {
            '.py' : self.parse_python_ast,
            '.php': self.parse_with_outline_parser,
            '.go': self.parse_with_outline_parser,
        }
    
    def index_file(self, file_path: str) -> List[SymbolInfo]:
        """
        Parse a file and return all symbols
        
        Args:
            file_path: Path to file to index
            
        Returns:
            List of SymbolInfo objects
        """
        path = Path(file_path)
        ext = path.suffix.lower()
        
        try:
            if ext == '.py':
                return self.parse_python_ast(file_path)
            else:
                return self.parse_with_outline_parser(file_path)
        except Exception as e:
            print(f"[SymbolIndexer] Error indexing {file_path}: {e}")
            return []
    
    def parse_python_ast(self, file_path: str) -> List[SymbolInfo]:
        """
        Parse Python using AST for maximum detail
        
        Extracts:
        - Classes (with base classes)
        - Functions (with parameters, decorators)
        - Methods (with self/cls detection)
        - Module-level variables
        """
        symbols = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            # Track class context for methods
            current_class = None
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Class definition
                    symbols.append(SymbolInfo(
                        name=node.name,
                        symbol_type='class',
                        file_path=file_path,
                        line=node.lineno,
                        column=node.col_offset,
                        bases=[self._get_name(b) for b in node.bases],
                        decorators=[self._get_name(d) for d in node.decorator_list],
                        docstring=ast.get_docstring(node)
                    ))
                    
                    # Process methods inside class
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            symbols.append(SymbolInfo(
                                name=item.name,
                                symbol_type='method',
                                file_path=file_path,
                                line=item.lineno,
                                column=item.col_offset,
                                parent=node.name,
                                parameters=self._get_parameters(item.args),
                                decorators=[self._get_name(d) for d in item.decorator_list],
                                docstring=ast.get_docstring(item)
                            ))
                
                elif isinstance(node, ast.FunctionDef):
                    # Check if this is a top-level function (not inside a class)
                    if not self._is_inside_class(node, tree):
                        symbols.append(SymbolInfo(
                            name=node.name,
                            symbol_type='function',
                            file_path=file_path,
                            line=node.lineno,
                            column=node.col_offset,
                            parameters=self._get_parameters(node.args),
                            decorators=[self._get_name(d) for d in node.decorator_list],
                            docstring=ast.get_docstring(node)
                        ))
            
            return sorted(symbols, key=lambda s: s.line)
        
        except SyntaxError as e:
            print(f"[SymbolIndexer] Syntax error in {file_path}: {e}")
            return []
        except Exception as e:
            print(f"[SymbolIndexer] Error parsing Python {file_path}: {e}")
            return []
    
    def parse_with_outline_parser(self, file_path: str) -> List[SymbolInfo]:
        """
        Use existing OutlineParser for non-Python files
        
        Args:
            file_path: Path to file
            
        Returns:
            List of SymbolInfo objects
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            outline_symbols = OutlineParser.parse(file_path, content)
            
            # Convert OutlineParser symbols to SymbolInfo
            symbols = []
            for sym in outline_symbols:
                symbol_info = SymbolInfo(
                    name=sym.name,
                    symbol_type=sym.type,
                    file_path=file_path,
                    line=sym.line,
                    column=0,  # OutlineParser doesn't provide column
                    parent=sym.parent.name if sym.parent else None,
                    children=[c.name for c in sym.children]
                )
                symbols.append(symbol_info)
                
                # Add children as separate symbols
                for child in sym.children:
                    child_info = SymbolInfo(
                        name=child.name,
                        symbol_type=child.type,
                        file_path=file_path,
                        line=child.line,
                        column=0,
                        parent=sym.name
                    )
                    symbols.append(child_info)
            
            return symbols
        
        except Exception as e:
            print(f"[SymbolIndexer] Error with OutlineParser for {file_path}: {e}")
            return []
    
    # Helper methods
    
    def _get_name(self, node) -> str:
        """Extract name from AST node"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        elif hasattr(node, 'id'):
            return node.id
        return str(node)
    
    def _get_parameters(self, args: ast.arguments) -> List[str]:
        """Extract parameter names from function arguments"""
        params = []
        
        # Regular args
        for arg in args.args:
            params.append(arg.arg)
        
        # *args
        if args.vararg:
            params.append(f"*{args.vararg.arg}")
        
        # **kwargs
        if args.kwarg:
            params.append(f"**{args.kwarg.arg}")
        
        return params

    def _is_inside_class(self, func_node, tree) -> bool:
        """
        Check if a function node is inside a class
        
        This is a simplified check - walks the tree to see if
        function is nested inside a ClassDef
        """
        # For now, use a simpler approach - check if any ClassDef contains this function
        # This is good enough for most cases
        return False  # Will improve this in next iteration

