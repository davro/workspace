# ide/plugins/Codeintelligence/SymbolSearchDialog.py

"""
SymbolSearchDialog - Quick symbol search popup
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QLabel, 
    QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from pathlib import Path


class SymbolSearchDialog(QDialog):
    """
    Quick symbol search popup (Ctrl+T style)
    Like QuickOpen but for symbols
    """
    
    def __init__(self, database, navigation_manager, parent=None):
        super().__init__(parent)
        self.db = database
        self.nav_manager = navigation_manager
        self.selected_symbol = None
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        self.setWindowTitle("Go to Symbol")
        self.setModal(True)
        self.setMinimumSize(700, 500)
        
        # Styling (similar to QuickOpen)
        self.setStyleSheet("""
            QDialog {
                background-color: #2B2B2B;
            }
            QLineEdit {
                background-color: #3C3F41;
                color: #CCC;
                border: 2px solid #4A9EFF;
                padding: 8px;
                font-size: 14px;
                border-radius: 4px;
            }
            QListWidget {
                background-color: #313335;
                color: #CCC;
                border: 1px solid #555;
                font-size: 12px;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #3C3F41;
            }
            QListWidget::item:selected {
                background-color: #4A9EFF;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #3C3F41;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type symbol name... (fuzzy matching)")
        self.search_input.textChanged.connect(self.on_search_changed)
        self.search_input.returnPressed.connect(self.accept_selection)
        layout.addWidget(self.search_input)
        
        # Info label
        stats = self.db.get_statistics()
        self.info_label = QLabel(
            f"{stats['total_symbols']:,} symbols indexed "
            f"({stats['classes']} classes, {stats['functions']} functions)"
        )
        self.info_label.setStyleSheet("color: #999; font-size: 11px;")
        layout.addWidget(self.info_label)
        
        # Results list
        self.results_list = QListWidget()
        self.results_list.itemDoubleClicked.connect(self.accept_selection)
        layout.addWidget(self.results_list)
        
        # Instructions
        instructions = QLabel("↑↓ Navigate • Enter Jump • Esc Cancel")
        instructions.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(instructions)
        
        self.search_input.setFocus()
    
    def on_search_changed(self, text: str):
        """Update results based on search"""
        self.results_list.clear()
        
        if not text:
            # Show nothing or recent symbols
            self.info_label.setText("Type to search symbols...")
            return
        
        # Fuzzy search
        matches = self.db.fuzzy_search(text, limit=100)
        
        for symbol in matches:
            # Format: "icon SymbolName (type) - file.py:line"
            file_name = Path(symbol.file_path).name
            
            if symbol.parent:
                display_text = f"{symbol.get_icon()} {symbol.parent}.{symbol.name} ({symbol.type}) - {file_name}:{symbol.line}"
            else:
                display_text = f"{symbol.get_icon()} {symbol.name} ({symbol.type}) - {file_name}:{symbol.line}"
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, symbol)
            
            # Color code by type
            if symbol.type == 'class':
                item.setForeground(QColor("#FFC66D"))
            elif symbol.type in ('function', 'method'):
                item.setForeground(QColor("#4A9EFF"))
            
            self.results_list.addItem(item)
        
        if matches:
            self.info_label.setText(f"Found {len(matches):,} matches")
            self.results_list.setCurrentRow(0)
        else:
            self.info_label.setText("No matches found")
    
    def accept_selection(self):
        """Jump to selected symbol"""
        item = self.results_list.currentItem()
        if item:
            self.selected_symbol = item.data(Qt.ItemDataRole.UserRole)
            self.accept()
    
    def keyPressEvent(self, event):
        """Handle key presses"""
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        elif event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            self.results_list.keyPressEvent(event)
        elif event.key() == Qt.Key.Key_Return:
            self.accept_selection()
        else:
            # Pass other keys to search input
            self.search_input.keyPressEvent(event)
            self.search_input.setFocus()
