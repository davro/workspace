# ide/plugins/Codeintelligence/ReferenceTracker.py

"""
ReferenceTracker - Find all references to a symbol
"""

from typing import List, Dict, Optional
from pathlib import Path


from .SymbolInfo import SymbolInfo, Reference
from .SymbolDatabase import SymbolDatabase
from .SymbolIndexer import SymbolIndexer
from .NavigationManager import NavigationManager
from .SymbolSearchDialog import SymbolSearchDialog
from .SymbolPanelWidget import SymbolPanelWidget


class ReferenceTracker:
    """
    Tracks symbol references across codebase
    """
    
    def __init__(self, database):
        self.db = database
    
    def find_all_references(self, symbol_name: str, file_filter: List[str] = None) -> List[Reference]:
        """
        Find all references to a symbol
        
        Args:
            symbol_name: Name of symbol to find references for
            file_filter: Optional list of file paths to search (if None, search all)
            
        Returns:
            List of Reference objects (file, line, column, context)
        """
        references = []
        
        # Determine which files to search
        if file_filter:
            files_to_search = file_filter
        else:
            # Search all indexed files
            files_to_search = list(self.db.symbols_by_file.keys())
        
        # Search each file
        for file_path in files_to_search:
            file_refs = self._search_file_for_references(file_path, symbol_name)
            references.extend(file_refs)
        
        return references
    
    def _search_file_for_references(self, file_path: str, symbol_name: str) -> List[Reference]:
        """
        Search a single file for references to a symbol
        
        Args:
            file_path: Path to file to search
            symbol_name: Symbol name to find
            
        Returns:
            List of Reference objects found in this file
        """
        references = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for line_num, line in enumerate(lines, 1):
                # Find all occurrences of symbol_name in this line
                col = 0
                while True:
                    col = line.find(symbol_name, col)
                    if col == -1:
                        break
                    
                    # Verify it's a whole word (not part of another identifier)
                    if self._is_whole_word(line, col, symbol_name):
                        context = line.strip()
                        references.append(Reference(
                            file_path=file_path,
                            line=line_num,
                            column=col,
                            context=context
                        ))
                    
                    col += len(symbol_name)
        
        except Exception as e:
            print(f"[ReferenceTracker] Error searching {file_path}: {e}")
        
        return references
    
    def _is_whole_word(self, line: str, start: int, word: str) -> bool:
        """
        Check if word at position is a whole word (not part of another identifier)
        
        Args:
            line: Line of text
            start: Starting position of word
            word: Word to check
            
        Returns:
            True if word is standalone, False if part of larger identifier
        """
        # Check character before
        if start > 0:
            prev_char = line[start - 1]
            if prev_char.isalnum() or prev_char == '_':
                return False
        
        # Check character after
        end = start + len(word)
        if end < len(line):
            next_char = line[end]
            if next_char.isalnum() or next_char == '_':
                return False
        
        return True
    
    def count_references(self, symbol_name: str) -> int:
        """
        Count total references to a symbol (faster than finding all)
        
        Args:
            symbol_name: Symbol name
            
        Returns:
            Count of references
        """
        count = 0
        
        for file_path in self.db.symbols_by_file.keys():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Quick count using string methods
                col = 0
                while True:
                    col = content.find(symbol_name, col)
                    if col == -1:
                        break
                    
                    # Simple whole-word check
                    if col > 0 and (content[col-1].isalnum() or content[col-1] == '_'):
                        col += 1
                        continue
                    
                    end = col + len(symbol_name)
                    if end < len(content) and (content[end].isalnum() or content[end] == '_'):
                        col += 1
                        continue
                    
                    count += 1
                    col += len(symbol_name)
            
            except Exception as e:
                print(f"[ReferenceTracker] Error counting in {file_path}: {e}")
        
        return count
