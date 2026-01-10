# ============================================================================
# OutlineWidget.py in ide/core/
# ============================================================================

"""
Outline navigator widget - shows code structure
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, 
    QLineEdit, QLabel, QHBoxLayout
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from ide.core.OutlineParser import OutlineParser, Symbol
from ide.core.CodeEditor import CodeEditor


class OutlineWidget(QWidget):
    """
    Code outline/navigator widget
    Shows classes, functions, methods from current file
    """
    
    # Signal emitted when user clicks a symbol
    symbol_clicked = pyqtSignal(int)  # line number
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_editor = None
        self.symbols = []
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Header with refresh button (no label since tab already shows "Outline")
        header_layout = QHBoxLayout()
        
        # Refresh button
        from PyQt6.QtWidgets import QPushButton
        refresh_btn = QPushButton("🔄")
        refresh_btn.setFixedSize(24, 24)
        refresh_btn.setToolTip("Refresh outline")
        refresh_btn.clicked.connect(self.refresh_outline)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #3C3F41;
                color: #CCC;
                border: 1px solid #555;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #4A4A4A;
            }
        """)
        header_layout.addStretch()
        header_layout.addWidget(refresh_btn)
        
        layout.addLayout(header_layout)
        
        # Search box
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search symbols...")
        self.search_input.textChanged.connect(self.filter_symbols)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #3C3F41;
                color: #CCC;
                border: 1px solid #555;
                padding: 4px;
                border-radius: 3px;
            }
            QLineEdit:focus {
                border: 1px solid #4A9EFF;
            }
        """)
        layout.addWidget(self.search_input)
        
        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setIndentation(20)
        self.tree.itemClicked.connect(self.on_item_clicked)
        
        # Style the tree
        self.tree.setStyleSheet("""
            QTreeWidget {
                background-color: #2B2B2B;
                color: #CCCCCC;
                border: 1px solid #3C3F41;
                border-radius: 3px;
            }
            QTreeWidget::item {
                padding: 3px;
                border-radius: 2px;
            }
            QTreeWidget::item:hover {
                background-color: #3C3F41;
            }
            QTreeWidget::item:selected {
                background-color: #4A9EFF;
                color: white;
            }
            QTreeWidget::branch {
                background-color: #2B2B2B;
            }
            QTreeWidget::branch:has-children:!has-siblings:closed,
            QTreeWidget::branch:closed:has-children:has-siblings {
                image: url(none);
                border: none;
            }
            QTreeWidget::branch:open:has-children:!has-siblings,
            QTreeWidget::branch:open:has-children:has-siblings {
                image: url(none);
                border: none;
            }
        """)
        
        # Set font
        font = QFont("Monospace", 10)
        self.tree.setFont(font)
        
        layout.addWidget(self.tree)
        
        # Info label
        self.info_label = QLabel("No symbols")
        self.info_label.setStyleSheet("color: #999; padding: 5px;")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info_label)
    

    def set_editor(self, editor: CodeEditor):
        """
        Set the current editor and parse its symbols
        
        Args:
            editor: CodeEditor instance
        """
        # Stop any pending refresh
        if hasattr(self, '_refresh_timer'):
            self._refresh_timer.stop()
        
        # Disconnect from previous editor
        if self.current_editor:
            try:
                self.current_editor.textChanged.disconnect(self.on_text_changed)
            except:
                pass
        
        self.current_editor = editor
        
        # Connect to new editor's text changes
        if self.current_editor:
            self.current_editor.textChanged.connect(self.on_text_changed)
        
        self.refresh_outline()


    def on_text_changed(self):
        """Handle text changes in editor - debounced refresh"""
        # Use a timer to avoid refreshing on every keystroke
        if not hasattr(self, '_refresh_timer'):
            from PyQt6.QtCore import QTimer
            self._refresh_timer = QTimer()
            self._refresh_timer.setSingleShot(True)
            self._refresh_timer.timeout.connect(self.refresh_outline)
        
        # Refresh after 500ms of no typing
        self._refresh_timer.start(500)
    

    def refresh_outline(self):
        """Refresh the outline from current editor"""
        self.tree.clear()
        self.symbols = []
        
        if not self.current_editor or not self.current_editor.file_path:
            self.info_label.setText("No file open")
            return
        
        # Parse symbols
        content = self.current_editor.toPlainText()
        self.symbols = OutlineParser.parse(
            self.current_editor.file_path,
            content
        )
        
        if not self.symbols:
            self.info_label.setText("No symbols found")
            return
        
        # Populate tree
        self.populate_tree(self.symbols)
        self.info_label.setText(f"{len(self.symbols)} symbol(s)")


    def populate_tree(self, symbols):
        """
        Populate tree widget with symbols
        
        Args:
            symbols: List of Symbol objects
        """
        for symbol in symbols:
            self.add_symbol_to_tree(symbol, None)
        
        # Expand all top-level items
        for i in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(i).setExpanded(True)


    def add_symbol_to_tree(self, symbol: Symbol, parent_item: QTreeWidgetItem):
        """
        Add a symbol to the tree
        
        Args:
            symbol: Symbol object
            parent_item: Parent QTreeWidgetItem (None for top-level)
        """
        # Create item text with icon and line number
        item_text = f"{symbol.get_icon()} {symbol.name}  (line {symbol.line})"
        
        if parent_item:
            item = QTreeWidgetItem(parent_item, [item_text])
        else:
            item = QTreeWidgetItem(self.tree, [item_text])
        
        # Store line number in item data
        item.setData(0, Qt.ItemDataRole.UserRole, symbol.line)
        
        # Add children recursively
        for child in symbol.children:
            self.add_symbol_to_tree(child, item)


    def on_item_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle item click - jump to symbol"""
        line = item.data(0, Qt.ItemDataRole.UserRole)
        if line and self.current_editor:
            self.symbol_clicked.emit(line)
            self.jump_to_line(line)
 

    def jump_to_line(self, line: int):
        """
        Jump editor to specified line
        
        Args:
            line: Line number (1-indexed)
        """
        if not self.current_editor:
            return
        
        from PyQt6.QtGui import QTextCursor
        
        cursor = self.current_editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        cursor.movePosition(
            QTextCursor.MoveOperation.Down,
            QTextCursor.MoveMode.MoveAnchor,
            line - 1
        )
        self.current_editor.setTextCursor(cursor)
        # self.current_editor.ensureCursorVisible()
        self.current_editor.centerCursor()  # ← Changed from ensureCursorVisible() 
        self.current_editor.setFocus()

    def filter_symbols(self, text: str):
        """
        Filter displayed symbols by search text
        
        Args:
            text: Search text
        """
        if not text:
            # Show all items
            for i in range(self.tree.topLevelItemCount()):
                self.show_item_recursive(self.tree.topLevelItem(i), True)
            return
        
        text_lower = text.lower()
        
        # Hide/show items based on match
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            self.filter_item_recursive(item, text_lower)

    
    def filter_item_recursive(self, item: QTreeWidgetItem, search_text: str) -> bool:
        """
        Recursively filter item and children
        Returns True if item or any child matches
        """
        # Check if this item matches
        item_text = item.text(0).lower()
        matches = search_text in item_text
        
        # Check children
        child_matches = False
        for i in range(item.childCount()):
            child = item.child(i)
            if self.filter_item_recursive(child, search_text):
                child_matches = True
        
        # Show item if it or any child matches
        show = matches or child_matches
        item.setHidden(not show)
        
        # Expand if child matches
        if child_matches and not matches:
            item.setExpanded(True)
        
        return show

    
    def show_item_recursive(self, item: QTreeWidgetItem, show: bool):
        """Recursively show/hide item and children"""
        item.setHidden(not show)
        for i in range(item.childCount()):
            self.show_item_recursive(item.child(i), show)


    def cleanup(self):
        """Clean up connections when widget is destroyed"""
        if hasattr(self, '_refresh_timer'):
            self._refresh_timer.stop()
        
        if self.current_editor:
            try:
                self.current_editor.textChanged.disconnect(self.on_text_changed)
            except:
                pass
