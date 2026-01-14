# ============================================================================
# CodeFolding.py - Code folding infrastructure (FIXED VERSION)
# ============================================================================

"""
Code Folding System for CodeEditor

Provides:
- Automatic detection of foldable regions (functions, classes, blocks)
- Visual fold markers in the gutter
- Mouse interaction to toggle folds
- Keyboard shortcuts for folding operations
- Persistent fold state

FIXES:
- Added Markdown support (headers, code blocks, lists)
- Fixed line number painting to skip hidden blocks
"""

from dataclasses import dataclass
from typing import List, Tuple, Set, Optional
import re


@dataclass
class FoldRegion:
    """Represents a foldable region of code"""
    start_line: int      # Line number where region starts (0-based)
    end_line: int        # Line number where region ends (0-based)
    level: int           # Indentation level (0 = top level)
    type: str            # 'function', 'class', 'if', 'for', 'while', etc.
    is_folded: bool = False
    
    def contains_line(self, line: int) -> bool:
        """Check if this region contains a line number"""
        return self.start_line < line <= self.end_line


class CodeFoldingParser:
    """
    Parses code to detect foldable regions.
    
    Supports:
    - Python (functions, classes, if/for/while blocks)
    - JavaScript/TypeScript (functions, classes, blocks)
    - PHP (functions, classes, blocks)
    - C/C++/Java (functions, classes, blocks)
    - Markdown (headers, code blocks, lists)
    """
    
    def __init__(self, language: str = 'python'):
        self.language = language.lower()
    
    def parse(self, text: str) -> List[FoldRegion]:
        """
        Parse text and return list of foldable regions.
        
        Args:
            text: The source code text
            
        Returns:
            List of FoldRegion objects
        """
        if self.language == 'python':
            return self._parse_python(text)
        elif self.language in ['javascript', 'typescript', 'js', 'ts']:
            return self._parse_javascript(text)
        elif self.language == 'php':
            return self._parse_php(text)
        elif self.language in ['c', 'cpp', 'java', 'c++']:
            return self._parse_c_style(text)
        elif self.language in ['markdown', 'md']:
            return self._parse_markdown(text)
        else:
            # Generic brace-based folding
            return self._parse_braces(text)
    
    def _parse_python(self, text: str) -> List[FoldRegion]:
        """Parse Python code for foldable regions"""
        lines = text.split('\n')
        regions = []
        stack = []  # Stack of (line_num, indent_level, type)
        in_string = None  # Track if we're inside a multi-line string
        
        # Patterns for Python structures
        class_pattern = re.compile(r'^(\s*)class\s+\w+')
        func_pattern = re.compile(r'^(\s*)def\s+\w+')
        block_pattern = re.compile(r'^(\s*)(if|elif|else|for|while|try|except|finally|with)\s*[:(]')
        
        for i, line in enumerate(lines):
            # Handle multi-line strings (""" or ''')
            triple_double = line.count('"""')
            triple_single = line.count("'''")
            
            if in_string is None:
                if triple_double % 2 == 1:
                    in_string = '"""'
                    continue
                elif triple_single % 2 == 1:
                    in_string = "'''"
                    continue
            else:
                if in_string == '"""' and triple_double % 2 == 1:
                    in_string = None
                    continue
                elif in_string == "'''" and triple_single % 2 == 1:
                    in_string = None
                    continue
                else:
                    continue
            
            stripped = line.lstrip()
            
            if not stripped or stripped.startswith('#'):
                continue
            
            indent = len(line) - len(stripped)
            
            # Check for class definition
            class_match = class_pattern.match(line)
            if class_match:
                while stack and stack[-1][1] >= indent:
                    start_line, start_indent, block_type = stack.pop()
                    regions.append(FoldRegion(start_line, i - 1, start_indent, block_type))
                
                stack.append((i, indent, 'class'))
                continue
            
            # Check for function definition
            func_match = func_pattern.match(line)
            if func_match:
                while stack and stack[-1][1] >= indent:
                    start_line, start_indent, block_type = stack.pop()
                    regions.append(FoldRegion(start_line, i - 1, start_indent, block_type))
                
                stack.append((i, indent, 'function'))
                continue
            
            # Check for control flow blocks
            block_match = block_pattern.match(line)
            if block_match:
                block_indent = len(block_match.group(1))
                block_type = block_match.group(2)
                
                while stack and stack[-1][1] >= block_indent:
                    start_line, start_indent, prev_type = stack.pop()
                    regions.append(FoldRegion(start_line, i - 1, start_indent, prev_type))
                
                stack.append((i, block_indent, block_type))
                continue
            
            # Check if this line is less indented
            while stack and stack[-1][1] >= indent and not line.strip().startswith(('elif', 'else', 'except', 'finally')):
                start_line, start_indent, block_type = stack.pop()
                if i - start_line > 1:
                    regions.append(FoldRegion(start_line, i - 1, start_indent, block_type))
        
        # Close remaining regions
        last_line = len(lines) - 1
        while stack:
            start_line, start_indent, block_type = stack.pop()
            if last_line - start_line > 1:
                regions.append(FoldRegion(start_line, last_line, start_indent, block_type))
        
        return regions
    
    def _parse_markdown(self, text: str) -> List[FoldRegion]:
        """
        Parse Markdown for foldable regions.
        
        Supports:
        - Headers (# H1, ## H2, etc.) - fold until next header of same/higher level
        - Code blocks (```...```) - fold the entire block
        - Lists - fold nested list items
        """
        lines = text.split('\n')
        regions = []
        
        # Track header hierarchy
        header_stack = []  # Stack of (line_num, level)
        
        # Track code blocks
        in_code_block = False
        code_block_start = None
        
        for i, line in enumerate(lines):
            # Check for code block markers
            if line.strip().startswith('```'):
                if not in_code_block:
                    # Start of code block
                    in_code_block = True
                    code_block_start = i
                else:
                    # End of code block
                    in_code_block = False
                    if code_block_start is not None and i - code_block_start > 1:
                        regions.append(FoldRegion(code_block_start, i, 0, 'code_block'))
                    code_block_start = None
                continue
            
            # Skip lines inside code blocks
            if in_code_block:
                continue
            
            # Check for headers (# Header)
            header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if header_match:
                header_level = len(header_match.group(1))
                
                # Close all headers of same or lower level (higher number = lower level)
                while header_stack and header_stack[-1][1] >= header_level:
                    start_line, start_level = header_stack.pop()
                    if i - start_line > 1:  # Only fold if there's content
                        regions.append(FoldRegion(start_line, i - 1, start_level - 1, f'h{start_level}'))
                
                # Add this header to stack
                header_stack.append((i, header_level))
        
        # Close remaining headers at end of document
        last_line = len(lines) - 1
        while header_stack:
            start_line, start_level = header_stack.pop()
            if last_line - start_line > 1:
                regions.append(FoldRegion(start_line, last_line, start_level - 1, f'h{start_level}'))
        
        return regions
    
    def _parse_braces(self, text: str) -> List[FoldRegion]:
        """Generic brace-based folding for {}-style languages"""
        lines = text.split('\n')
        regions = []
        stack = []
        
        for i, line in enumerate(lines):
            open_braces = line.count('{')
            close_braces = line.count('}')
            
            for _ in range(open_braces):
                stack.append(i)
            
            for _ in range(close_braces):
                if stack:
                    start_line = stack.pop()
                    if i - start_line > 1:
                        regions.append(FoldRegion(start_line, i, 0, 'block'))
        
        return regions
    
    def _parse_javascript(self, text: str) -> List[FoldRegion]:
        """Parse JavaScript/TypeScript code"""
        return self._parse_braces(text)
    
    def _parse_php(self, text: str) -> List[FoldRegion]:
        """Parse PHP code"""
        return self._parse_braces(text)
    
    def _parse_c_style(self, text: str) -> List[FoldRegion]:
        """Parse C/C++/Java code"""
        return self._parse_braces(text)


class CodeFoldingManager:
    """
    Manages code folding state and operations for a CodeEditor.
    
    Responsibilities:
    - Track which regions are folded
    - Show/hide lines when folding/unfolding
    - Draw fold markers in the gutter
    - Handle mouse clicks on fold markers
    """
    
    def __init__(self, editor):
        self.editor = editor
        self.regions: List[FoldRegion] = []
        self.folded_regions: Set[Tuple[int, int]] = set()
        self.parser = None
        self.fold_marker_width = 14
    
    def update_regions(self):
        """
        Re-parse the document and update fold regions.
        Call this when the document changes significantly.
        """
        if self.editor.file_path:
            from pathlib import Path
            ext = Path(self.editor.file_path).suffix.lower()
            language_map = {
                '.py': 'python',
                '.js': 'javascript',
                '.ts': 'typescript',
                '.php': 'php',
                '.c': 'c',
                '.cpp': 'cpp',
                '.java': 'java',
                '.md': 'markdown',
                '.markdown': 'markdown',
            }
            language = language_map.get(ext, 'python')
        else:
            language = 'python'
        
        self.parser = CodeFoldingParser(language)
        text = self.editor.toPlainText()
        self.regions = self.parser.parse(text)
        
        self._restore_fold_state()
    
    def toggle_fold_at_line(self, line_number: int):
        """
        Toggle folding at a specific line number.
        
        Args:
            line_number: Line number (0-based)
        """
        region = self._find_region_at_line(line_number)
        
        if region:
            if region.is_folded:
                self.unfold_region(region)
            else:
                self.fold_region(region)
    
    def fold_region(self, region: FoldRegion):
        """Fold a region (hide its contents)"""
        if region.is_folded:
            return
        
        document = self.editor.document()
        
        # Hide lines in the region (but not the first line)
        for line_num in range(region.start_line + 1, region.end_line + 1):
            block = document.findBlockByNumber(line_num)
            if block.isValid():
                block.setVisible(False)
        
        region.is_folded = True
        self.folded_regions.add((region.start_line, region.end_line))
        
        # Update editor display - simple and effective
        self.editor.viewport().update()
        if self.editor.line_number_area:
            self.editor.line_number_area.update()
    
    def unfold_region(self, region: FoldRegion):
        """Unfold a region (show its contents)"""
        if not region.is_folded:
            return
        
        document = self.editor.document()
        
        # Show lines in the region
        for line_num in range(region.start_line + 1, region.end_line + 1):
            block = document.findBlockByNumber(line_num)
            if block.isValid():
                block.setVisible(True)
        
        region.is_folded = False
        self.folded_regions.discard((region.start_line, region.end_line))
        
        # Update editor display - simple and effective
        self.editor.viewport().update()
        if self.editor.line_number_area:
            self.editor.line_number_area.update()
    
    def fold_all(self):
        """Fold all regions"""
        for region in self.regions:
            if not region.is_folded:
                self.fold_region(region)
    
    def unfold_all(self):
        """Unfold all regions"""
        for region in self.regions:
            if region.is_folded:
                self.unfold_region(region)
    
    def fold_level(self, level: int):
        """Fold all regions at or above a certain level"""
        for region in self.regions:
            if region.level <= level and not region.is_folded:
                self.fold_region(region)
    
    def _find_region_at_line(self, line_number: int) -> Optional[FoldRegion]:
        """Find a region that starts at the given line"""
        for region in self.regions:
            if region.start_line == line_number:
                return region
        return None
    
    def _restore_fold_state(self):
        """Restore fold state after reparsing"""
        for region in self.regions:
            key = (region.start_line, region.end_line)
            if key in self.folded_regions:
                region.is_folded = True
    
    def get_fold_marker_rect(self, line_number: int, top: int, height: int) -> Optional[Tuple[int, int, int, int]]:
        """
        Get the rectangle for a fold marker at a line.
        
        Returns:
            Tuple of (x, y, width, height) or None if no marker at this line
        """
        region = self._find_region_at_line(line_number)
        if not region:
            return None
        
        x = 2
        y = top + (height - 12) // 2
        return (x, y, 12, 12)
    
    def draw_fold_marker(self, painter, line_number: int, top: int, height: int):
        """
        Draw a fold marker for a line.
        
        Args:
            painter: QPainter instance
            line_number: Line number (0-based)
            top: Y position of the line
            height: Height of the line
        """
        from PyQt6.QtGui import QColor, QPen
        from PyQt6.QtCore import QRect
        
        region = self._find_region_at_line(line_number)
        if not region:
            return
        
        rect_info = self.get_fold_marker_rect(line_number, top, height)
        if not rect_info:
            return
        
        x, y, w, h = rect_info
        
        # Draw fold marker box
        painter.setPen(QPen(QColor("#808080")))
        painter.drawRect(x, y, w, h)
        
        # Draw minus/plus sign
        mid_x = x + w // 2
        mid_y = y + h // 2
        
        # Horizontal line (always present)
        painter.drawLine(x + 3, mid_y, x + w - 3, mid_y)
        
        # Vertical line (only if folded - makes it a plus sign)
        if region.is_folded:
            painter.drawLine(mid_x, y + 3, mid_x, y + h - 3)