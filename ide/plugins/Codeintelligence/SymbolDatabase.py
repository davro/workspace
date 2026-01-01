# ide/plugins/Codeintelligence/SymbolDatabase.py

"""
SymbolDatabase - Storage and indexing for symbols
"""

import json
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
        
        # Rebuild fuzzy index
        self.rebuild_fuzzy_index()
    
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
        return self.symbols_by_file.get(file_path, [])
    
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
        
        for name_lower, symbol in self.fuzzy_index:
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
        all_symbols = self._all_symbols()
        return {
            'total_symbols': len(all_symbols),
            'files_indexed': len(self.symbols_by_file),
            'classes': sum(1 for s in all_symbols if s.type == 'class'),
            'functions': sum(1 for s in all_symbols if s.type == 'function'),
            'methods': sum(1 for s in all_symbols if s.type == 'method'),
        }
    
    def clear(self):
        """Clear all indexes"""
        self.symbols_by_name.clear()
        self.symbols_by_file.clear()
        self.symbols_by_qualified_name.clear()
        self.fuzzy_index.clear()
    
    def save_to_cache(self):
        """Persist index to disk"""
        try:
            data = {
                'symbols': [s.to_dict() for s in self._all_symbols()],
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
        """Rebuild fuzzy search index"""
        self.fuzzy_index = [
            (symbol.name.lower(), symbol)
            for symbols in self.symbols_by_name.values()
            for symbol in symbols
        ]
    
    def _all_symbols(self) -> List[SymbolInfo]:
        """Get all symbols (flat list)"""
        return [s for symbols in self.symbols_by_name.values() for s in symbols]
