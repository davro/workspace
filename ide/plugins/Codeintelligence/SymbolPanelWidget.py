# ide/plugins/Codeintelligence/SymbolPanelWidget.py

"""
SymbolPanelWidget - Symbol tree panel for right sidebar
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QTreeWidget, QTreeWidgetItem
)
from PyQt6.QtCore import Qt

class SymbolPanelWidget(QWidget):
    """
    Symbol tree panel for right sidebar
    Shows symbols in current file in a tree structure
    """
    
    def __init__(self, database, navigation_manager, parent=None):
        super().__init__(parent)
        self.db = database
        self.nav_manager = navigation_manager
        self.current_file = None
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Header
        header_layout = QHBoxLayout()
        
        title = QLabel("Symbols")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_layout.addWidget(title)
        
        refresh_btn = QPushButton("🔄")
        refresh_btn.setFixedWidth(30)
        refresh_btn.setToolTip("Refresh symbols")
        refresh_btn.clicked.connect(self.refresh_symbols)
        header_layout.addWidget(refresh_btn)
        
        layout.addLayout(header_layout)
        
        # Symbol tree
        self.symbol_tree = QTreeWidget()
        self.symbol_tree.setHeaderHidden(True)
        self.symbol_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #2B2B2B;
                color: #CCC;
                border: none;
            }
            QTreeWidget::item {
                padding: 4px;
            }
            QTreeWidget::item:selected {
                background-color: #4A9EFF;
            }
            QTreeWidget::item:hover {
                background-color: #3C3F41;
            }
        """)
        self.symbol_tree.itemClicked.connect(self.on_symbol_clicked)
        layout.addWidget(self.symbol_tree)
        
        # Stats label
        self.stats_label = QLabel("No file selected")
        self.stats_label.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self.stats_label)
    
    def set_file(self, file_path: str):
        """
        Update to show symbols from a file
        
        Args:
            file_path: Path to file to display symbols for
        """
        self.current_file = file_path
        self.refresh_symbols()
    
    def refresh_symbols(self):
        """Refresh symbol tree from database"""
        self.symbol_tree.clear()
        
        if not self.current_file:
            self.stats_label.setText("No file selected")
            return
        
        symbols = self.db.get_file_symbols(self.current_file)
        
        if not symbols:
            self.stats_label.setText("No symbols found")
            return
        
        # Group by parent (for methods inside classes)
        top_level = [s for s in symbols if not s.parent]
        
        for symbol in top_level:
            # Create top-level item
            item_text = f"{symbol.get_icon()} {symbol.name}"
            if symbol.type in ('function', 'method') and symbol.parameters:
                params = ', '.join(symbol.parameters[:3])  # Show first 3 params
                if len(symbol.parameters) > 3:
                    params += ', ...'
                item_text += f"({params})"
            
            item = QTreeWidgetItem([item_text])
            item.setData(0, Qt.ItemDataRole.UserRole, symbol)
            self.symbol_tree.addTopLevelItem(item)
            
            # Add children (methods in class)
            children = [s for s in symbols if s.parent == symbol.name]
            for child in children:
                child_text = f"{child.get_icon()} {child.name}"
                if child.type in ('function', 'method') and child.parameters:
                    params = ', '.join(child.parameters[:3])
                    if len(child.parameters) > 3:
                        params += ', ...'
                    child_text += f"({params})"
                
                child_item = QTreeWidgetItem([child_text])
                child_item.setData(0, Qt.ItemDataRole.UserRole, child)
                item.addChild(child_item)
            
            # Expand classes to show methods
            if symbol.type == 'class' and children:
                item.setExpanded(True)
        
        # Update stats
        class_count = len([s for s in symbols if s.type == 'class'])
        func_count = len([s for s in symbols if s.type in ('function', 'method')])
        self.stats_label.setText(f"{len(symbols)} symbols ({class_count} classes, {func_count} functions)")
    
    def on_symbol_clicked(self, item, column):
        """
        Handle symbol click - jump to definition
        
        Args:
            item: QTreeWidgetItem that was clicked
            column: Column index (ignored)
        """
        symbol = item.data(0, Qt.ItemDataRole.UserRole)
        if symbol:
            self.nav_manager.jump_to_symbol(symbol)
    
    def clear(self):
        """Clear the symbol tree"""
        self.symbol_tree.clear()
        self.current_file = None
        self.stats_label.setText("No file selected")

