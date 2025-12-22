"""
Create new file: ide/core/OllamaContext.py
This builds intelligent context from code editors
"""

import ast
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from PyQt6.QtGui import QTextCursor


class OllamaContextBuilder:
    """
    Build intelligent context for Ollama requests
    
    Analyzes code to provide relevant context about:
    - File information (path, language)
    - Selection details (line numbers, size)
    - Function/class context (for Python)
    - Imports and dependencies
    """
    
    # Language detection by file extension
    LANGUAGE_MAP = {
        '.py': 'Python',
        '.js': 'JavaScript',
        '.ts': 'TypeScript',
        '.jsx': 'React/JSX',
        '.tsx': 'TypeScript React',
        '.html': 'HTML',
        '.css': 'CSS',
        '.scss': 'SCSS',
        '.json': 'JSON',
        '.xml': 'XML',
        '.md': 'Markdown',
        '.txt': 'Plain Text',
        '.sh': 'Shell Script',
        '.bash': 'Bash',
        '.php': 'PHP',
        '.java': 'Java',
        '.c': 'C',
        '.cpp': 'C++',
        '.h': 'C/C++ Header',
        '.rs': 'Rust',
        '.go': 'Go',
        '.rb': 'Ruby',
        '.sql': 'SQL',
        '.yaml': 'YAML',
        '.yml': 'YAML',
    }
    
    def __init__(self):
        self.context_levels = ['minimal', 'basic', 'smart']
    
    def build_context(self, editor, level='smart') -> Dict:
        """
        Build context dictionary from editor
        
        Args:
            editor: CodeEditor instance
            level: Context level ('minimal', 'basic', 'smart')
            
        Returns:
            Dictionary with context information
        """
        context = {}
        
        # Always include file info
        context['file_path'] = editor.file_path if editor.file_path else 'Untitled'
        context['language'] = self.detect_language(editor)
        
        # Get selection info
        cursor = editor.textCursor()
        if cursor.hasSelection():
            context['selection'] = self.get_selection_info(editor, cursor)
        else:
            context['selection'] = None
        
        # Add smart context for Python files
        if level == 'smart' and context['language'] == 'Python':
            context['python_context'] = self.get_python_context(editor, cursor)
        
        return context
    
    def detect_language(self, editor) -> str:
        """Detect programming language from file extension"""
        if not editor.file_path:
            return 'Plain Text'
        
        ext = Path(editor.file_path).suffix.lower()
        return self.LANGUAGE_MAP.get(ext, 'Plain Text')
    
    def get_selection_info(self, editor, cursor: QTextCursor) -> Dict:
        """Get information about the current selection"""
        selection_start = cursor.selectionStart()
        selection_end = cursor.selectionEnd()
        
        # Get line numbers
        cursor_copy = QTextCursor(cursor)
        cursor_copy.setPosition(selection_start)
        start_line = cursor_copy.blockNumber() + 1
        
        cursor_copy.setPosition(selection_end)
        end_line = cursor_copy.blockNumber() + 1
        
        selected_text = cursor.selectedText().replace('\u2029', '\n')
        
        return {
            'start_line': start_line,
            'end_line': end_line,
            'line_count': end_line - start_line + 1,
            'char_count': len(selected_text),
            'text': selected_text
        }
    
    def get_python_context(self, editor, cursor: QTextCursor) -> Dict:
        """
        Get Python-specific context using AST parsing
        
        Returns:
            Dictionary with Python context (function, class, imports, etc.)
        """
        context = {
            'imports': [],
            'current_function': None,
            'current_class': None,
            'file_structure': {}
        }
        
        try:
            source_code = editor.toPlainText()
            tree = ast.parse(source_code)
            
            # Get imports
            context['imports'] = self.extract_imports(tree)
            
            # Get file structure
            context['file_structure'] = self.extract_structure(tree)
            
            # Get current context (function/class at cursor position)
            if cursor.hasSelection():
                line_number = cursor.blockNumber() + 1
                context['current_function'] = self.find_function_at_line(tree, line_number)
                context['current_class'] = self.find_class_at_line(tree, line_number)
            
        except SyntaxError:
            # File has syntax errors, skip AST parsing
            context['parse_error'] = True
        except Exception as e:
            # Other parsing errors
            context['parse_error'] = True
        
        return context
    
    def extract_imports(self, tree: ast.AST) -> List[str]:
        """Extract import statements from AST"""
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}" if module else alias.name)
        
        return imports
    
    def extract_structure(self, tree: ast.AST) -> Dict:
        """Extract file structure (classes and functions)"""
        structure = {
            'classes': [],
            'functions': [],
        }
        
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                methods = [m.name for m in node.body if isinstance(m, ast.FunctionDef)]
                structure['classes'].append({
                    'name': node.name,
                    'line': node.lineno,
                    'methods': methods
                })
            elif isinstance(node, ast.FunctionDef):
                structure['functions'].append({
                    'name': node.name,
                    'line': node.lineno
                })
        
        return structure
    
    def find_function_at_line(self, tree: ast.AST, line: int) -> Optional[str]:
        """Find function name at specific line"""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
                    if node.lineno <= line <= node.end_lineno:
                        return node.name
        return None
    
    def find_class_at_line(self, tree: ast.AST, line: int) -> Optional[str]:
        """Find class name at specific line"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
                    if node.lineno <= line <= node.end_lineno:
                        return node.name
        return None
    
    def format_context(self, context: Dict, include_code: bool = True) -> str:
        """
        Format context dictionary into readable text
        
        Args:
            context: Context dictionary
            include_code: Whether to include the actual code
            
        Returns:
            Formatted context string
        """
        lines = []
        
        # File information
        file_path = context.get('file_path', 'Unknown')
        language = context.get('language', 'Unknown')
        
        lines.append(f"File: {file_path}")
        lines.append(f"Language: {language}")
        
        # Selection information
        selection = context.get('selection')
        if selection:
            start = selection['start_line']
            end = selection['end_line']
            count = selection['line_count']
            chars = selection['char_count']
            
            if start == end:
                lines.append(f"Line: {start}")
            else:
                lines.append(f"Lines: {start}-{end} ({count} lines)")
            lines.append(f"Characters: {chars}")
        
        # Python-specific context
        python_ctx = context.get('python_context')
        if python_ctx and not python_ctx.get('parse_error'):
            
            # Current function/class
            func = python_ctx.get('current_function')
            cls = python_ctx.get('current_class')
            
            if cls:
                lines.append(f"Class: {cls}")
            if func:
                lines.append(f"Function: {func}()")
            
            # Imports (show first 5)
            imports = python_ctx.get('imports', [])
            if imports:
                lines.append(f"Imports: {', '.join(imports[:5])}")
                if len(imports) > 5:
                    lines.append(f"  ... and {len(imports) - 5} more")
            
            # File structure summary
            structure = python_ctx.get('file_structure', {})
            classes = structure.get('classes', [])
            functions = structure.get('functions', [])
            
            if classes:
                lines.append(f"Classes in file: {len(classes)}")
            if functions:
                lines.append(f"Functions in file: {len(functions)}")
        
        lines.append("")  # Blank line before code
        
        # Add the actual code
        if include_code and selection:
            lines.append("```" + language.lower())
            lines.append(selection['text'])
            lines.append("```")
        
        return '\n'.join(lines)

