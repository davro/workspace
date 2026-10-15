# ide/plugins/Codeintelligence/SymbolDatabase.py

"""
SymbolDatabase - Storage and indexing for symbols
"""

import json
import os
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime


from .SymbolInfo import SymbolInfo, Reference


class SymbolDatabase:
    """
    Storage and indexing for symbols
    Optimized for fast lookups with multiple indexes
    """
    
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_file = cache_dir / "symbol_index.json"

        # Lock protecting all in-memory indexes.
        # IndexingThread mutates them from a background thread while the
        # main thread reads them via get_statistics / fuzzy_search.
        self._lock = threading.Lock()

        # In-memory indexes
        self.symbols_by_name: Dict[str, List[SymbolInfo]] = {}
        self.symbols_by_file: Dict[str, List[SymbolInfo]] = {}
        self.symbols_by_qualified_name: Dict[str, SymbolInfo] = {}
        
        # Fuzzy search index (pre-computed for speed)
        self.fuzzy_index: List[Tuple[str, SymbolInfo]] = []
        
        # Load from cache if exists
        self.load_from_cache()
    
    def add_symbols(self, symbols: List[SymbolInfo]):
        """
        Add symbols to database
        
        Args:
            symbols: List of SymbolInfo objects to add
        """
        with self._lock:
            for symbol in symbols:
                # Index by name
                if symbol.name not in self.symbols_by_name:
                    self.symbols_by_name[symbol.name] = []
                self.symbols_by_name[symbol.name].append(symbol)
                
                # Index by file
                if symbol.file_path not in self.symbols_by_file:
                    self.symbols_by_file[symbol.file_path] = []
                self.symbols_by_file[symbol.file_path].append(symbol)
                
                # Index by qualified name (unique)
                self.symbols_by_qualified_name[symbol.qualified_name] = symbol
                
                # Add to fuzzy index
                self.fuzzy_index.append((symbol.name.lower(), symbol))
    
    def remove_file(self, file_path: str):
        """
        Remove all symbols from a file (for re-indexing)
        
        Args:
            file_path: Path to file to remove symbols from
        """
        with self._lock:
            if file_path not in self.symbols_by_file:
                return
            
            for symbol in self.symbols_by_file[file_path]:
                # Remove from name index
                if symbol.name in self.symbols_by_name:
                    self.symbols_by_name[symbol.name] = [
                        s for s in self.symbols_by_name[symbol.name] if s != symbol
                    ]
                    # Remove empty lists
                    if not self.symbols_by_name[symbol.name]:
                        del self.symbols_by_name[symbol.name]
                
                # Remove from qualified name index
                if symbol.qualified_name in self.symbols_by_qualified_name:
                    del self.symbols_by_qualified_name[symbol.qualified_name]
            
            # Remove from file index
            del self.symbols_by_file[file_path]
            
            # Rebuild fuzzy index (still inside lock)
            self.fuzzy_index = [
                (s.name.lower(), s)
                for symbols in self.symbols_by_name.values()
                for s in symbols
            ]
    
    def find_symbol(self, name: str) -> List[SymbolInfo]:
        """
        Find symbols by exact name
        
        Args:
            name: Symbol name to find
            
        Returns:
            List of matching SymbolInfo objects
        """
        return self.symbols_by_name.get(name, [])
    
    def find_by_qualified_name(self, qualified_name: str) -> Optional[SymbolInfo]:
        """
        Find symbol by fully qualified name
        
        Args:
            qualified_name: Qualified name (e.g., "MyClass.my_method")
            
        Returns:
            SymbolInfo or None
        """
        return self.symbols_by_qualified_name.get(qualified_name)
    
    def get_file_symbols(self, file_path: str) -> List[SymbolInfo]:
        """
        Get all symbols in a file
        
        Args:
            file_path: Path to file
            
        Returns:
            List of SymbolInfo objects in that file
        """
        symbols = self.symbols_by_file.get(file_path)
        if symbols is not None:
            return symbols
        # Tolerate path-format differences (editor vs indexer): ./a/../b, slashes
        wanted = os.path.normpath(str(file_path))
        for key, value in list(self.symbols_by_file.items()):
            if os.path.normpath(key) == wanted:
                return value
        return []

    def has_file(self, file_path: str) -> bool:
        """True if the file has been indexed (even if it has no symbols)"""
        return bool(self.get_file_symbols(file_path))

    def prune_missing_files(self) -> int:
        """Drop cached symbols for files that no longer exist. Returns count removed."""
        missing = [f for f in list(self.symbols_by_file.keys()) if not os.path.exists(f)]
        for f in missing:
            self.remove_file(f)
        return len(missing)
    
    def fuzzy_search(self, pattern: str, limit: int = 50) -> List[SymbolInfo]:
        """
        Fuzzy search symbols
        Uses same algorithm as QuickOpen
        
        Args:
            pattern: Search pattern
            limit: Maximum results to return
            
        Returns:
            List of matching SymbolInfo objects, sorted by relevance
        """
        if not pattern:
            return []
        
        pattern_lower = pattern.lower()
        scored_matches = []
        
        snapshot = list(self.fuzzy_index)  # snapshot avoids holding lock during scoring
        for name_lower, symbol in snapshot:
            score = self._fuzzy_score(pattern_lower, name_lower)
            if score > 0:
                scored_matches.append((score, symbol))
        
        # Sort by score (highest first)
        scored_matches.sort(reverse=True, key=lambda x: x[0])
        
        return [symbol for score, symbol in scored_matches[:limit]]
    
    def _fuzzy_score(self, pattern: str, text: str) -> int:
        """
        Fuzzy matching score (same as QuickOpen)
        
        Args:
            pattern: Search pattern (lowercase)
            text: Text to match against (lowercase)
            
        Returns:
            Score (higher = better match), 0 if no match
        """
        # Exact substring match gets high score
        if pattern in text:
            return 1000 + (100 - text.index(pattern))
        
        # Character-by-character fuzzy match
        score = 0
        pattern_idx = 0
        last_match_idx = -1
        
        for i, char in enumerate(text):
            if pattern_idx < len(pattern) and char == pattern[pattern_idx]:
                score += 10
                # Bonus for consecutive characters
                if i == last_match_idx + 1:
                    score += 5
                # Bonus for matching at word boundaries
                if i == 0 or text[i-1] in '._':
                    score += 3
                last_match_idx = i
                pattern_idx += 1
        
        # Only return score if all pattern characters matched
        return score if pattern_idx == len(pattern) else 0
    
    def get_statistics(self) -> Dict:
        """
        Get index statistics
        
        Returns:
            Dictionary with statistics
        """
        total = classes = functions = methods = 0
        with self._lock:
            for symbols in self.symbols_by_name.values():
                for s in symbols:
                    total += 1
                    if s.type == 'class':
                        classes += 1
                    elif s.type == 'function':
                        functions += 1
                    elif s.type == 'method':
                        methods += 1
            files = len(self.symbols_by_file)
        return {
            'total_symbols': total,
            'files_indexed': files,
            'classes': classes,
            'functions': functions,
            'methods': methods,
        }
    
    def clear(self):
        """Clear all indexes"""
        with self._lock:
            self.symbols_by_name.clear()
            self.symbols_by_file.clear()
            self.symbols_by_qualified_name.clear()
            self.fuzzy_index.clear()
    
    def save_to_cache(self):
        """Persist index to disk"""
        try:
            snapshot = self._all_symbols()  # thread-safe snapshot
            data = {
                'symbols': [s.to_dict() for s in snapshot],
                'version': '1.0',
                'timestamp': datetime.now().isoformat()
            }
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            print(f"[SymbolDatabase] Saved {len(data['symbols'])} symbols to cache")
        
        except Exception as e:
            print(f"[SymbolDatabase] Error saving cache: {e}")
    
    def load_from_cache(self):
        """Load index from disk"""
        if not self.cache_file.exists():
            return
        
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            symbols = [SymbolInfo.from_dict(s) for s in data['symbols']]
            self.add_symbols(symbols)
            
            print(f"[SymbolDatabase] Loaded {len(symbols)} symbols from cache")
        
        except Exception as e:
            print(f"[SymbolDatabase] Error loading cache: {e}")
    
    def rebuild_fuzzy_index(self):
        """Rebuild fuzzy search index (acquires lock)."""
        with self._lock:
            self.fuzzy_index = [
                (symbol.name.lower(), symbol)
                for symbols in self.symbols_by_name.values()
                for symbol in symbols
            ]
    
    def _all_symbols(self) -> List[SymbolInfo]:
        """Get all symbols (flat list) — takes a snapshot under the lock."""
        with self._lock:
            return [s for symbols in self.symbols_by_name.values() for s in symbols]