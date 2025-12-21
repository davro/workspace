from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QLabel
)
from PyQt6.QtCore import Qt, QEvent, QTimer
from PyQt6.QtGui import QKeyEvent
from pathlib import Path


class TabSwitcherDialog(QDialog):
    """
    Tab switcher popup dialog with recent order navigation

    Shows all open tabs in recently-used order, allows quick navigation
    """

    def __init__(self, parent, tab_widget, recent_order):
        super().__init__(parent)

        self.tab_widget = tab_widget
        self.recent_order = recent_order
        self.original_tab = tab_widget.currentIndex()
        self.selected_tab = None
        self.ctrl_held = True  # Assume Ctrl is held when dialog opens

        # Setup dialog
        self.setWindowFlags(
            Qt.WindowType.Popup |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )

        self.setup_ui()
        self.populate_tabs()

        # Install event filter to detect Ctrl release
        self.installEventFilter(self)

        # Position dialog at center of parent
        self.center_on_parent()

    def setup_ui(self):
        """Setup the UI layout"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        # Title label
        title = QLabel("Open Files (Recently Used)")
        title.setStyleSheet("""
            QLabel {
                color: #CCCCCC;
                font-weight: bold;
                font-size: 12px;
                padding: 5px;
            }
        """)
        layout.addWidget(title)

        # Tab list
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #2B2B2B;
                color: #A9B7C6;
                border: 2px solid #4A9EFF;
                border-radius: 5px;
                outline: none;
                font-size: 11px;
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
        self.list_widget.setMinimumWidth(500)
        self.list_widget.setMaximumHeight(400)

        # Connect signals
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        self.list_widget.itemActivated.connect(self.on_item_activated)

        layout.addWidget(self.list_widget)

        # Instructions label
        instructions = QLabel("Hold Ctrl+Tab to navigate  •  Release Ctrl to select  •  Esc: Cancel")
        instructions.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 10px;
                padding: 2px;
            }
        """)
        layout.addWidget(instructions)

    def populate_tabs(self):
        """Populate the list with tabs in recent order"""
        self.list_widget.clear()

        for idx in self.recent_order:
            if idx < 0 or idx >= self.tab_widget.count():
                continue

            editor = self.tab_widget.widget(idx)
            if not editor:
                continue

            # Get file info
            if hasattr(editor, 'file_path') and editor.file_path:
                file_path = Path(editor.file_path)
                file_name = file_path.name
                file_dir = str(file_path.parent)
            else:
                file_name = self.tab_widget.tabText(idx)
                file_dir = "Untitled"

            # Create list item
            item = QListWidgetItem()

            # Show filename on first line, path on second
            item_text = f"{file_name}\n  {file_dir}"
            item.setText(item_text)
            item.setData(Qt.ItemDataRole.UserRole, idx)  # Store tab index

            # Add modified indicator
            if hasattr(editor, 'document') and editor.document().isModified():
                item.setText(f"● {item_text}")

            self.list_widget.addItem(item)

        # Select second item (first is current, second is most recent)
        if self.list_widget.count() > 1:
            self.list_widget.setCurrentRow(1)
            self.preview_tab(1)
        elif self.list_widget.count() == 1:
            self.list_widget.setCurrentRow(0)

    def preview_tab(self, row):
        """Preview the tab at the given row without closing dialog"""
        item = self.list_widget.item(row)
        if item:
            tab_index = item.data(Qt.ItemDataRole.UserRole)
            if tab_index is not None:
                self.tab_widget.setCurrentIndex(tab_index)

    def on_item_clicked(self, item):
        """Handle mouse click on item"""
        tab_index = item.data(Qt.ItemDataRole.UserRole)
        if tab_index is not None:
            self.selected_tab = tab_index
            self.accept()

    def on_item_activated(self, item):
        """Handle Enter key or double-click"""
        self.on_item_clicked(item)

    def keyPressEvent(self, event: QKeyEvent):
        """Handle keyboard navigation"""
        key = event.key()
        modifiers = event.modifiers()

        # Mark that Ctrl is still being held
        if key == Qt.Key.Key_Control:
            self.ctrl_held = True

        if key == Qt.Key.Key_Escape:
            # Cancel - return to original tab
            self.tab_widget.setCurrentIndex(self.original_tab)
            self.reject()
            return

        elif key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            # Activate selected tab
            current_item = self.list_widget.currentItem()
            if current_item:
                self.on_item_activated(current_item)
            return

        elif key == Qt.Key.Key_Tab:
            # Ctrl+Tab or Ctrl+Shift+Tab
            event.accept()  # Prevent default tab behavior

            current_row = self.list_widget.currentRow()

            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                # Move up (backwards)
                new_row = current_row - 1
                if new_row < 0:
                    new_row = self.list_widget.count() - 1
            else:
                # Move down (forwards)
                new_row = current_row + 1
                if new_row >= self.list_widget.count():
                    new_row = 0

            self.list_widget.setCurrentRow(new_row)
            self.preview_tab(new_row)
            return

        elif key == Qt.Key.Key_Up:
            # Up arrow
            current_row = self.list_widget.currentRow()
            new_row = max(0, current_row - 1)
            self.list_widget.setCurrentRow(new_row)
            self.preview_tab(new_row)
            return

        elif key == Qt.Key.Key_Down:
            # Down arrow
            current_row = self.list_widget.currentRow()
            new_row = min(self.list_widget.count() - 1, current_row + 1)
            self.list_widget.setCurrentRow(new_row)
            self.preview_tab(new_row)
            return

        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        """Handle key release events"""
        if event.key() == Qt.Key.Key_Control:
            # Ctrl released - activate selected tab
            #print("[DEBUG] Ctrl released in keyReleaseEvent")
            self.ctrl_held = False
            current_item = self.list_widget.currentItem()
            if current_item:
                self.selected_tab = current_item.data(Qt.ItemDataRole.UserRole)
            self.accept()
            return

        super().keyReleaseEvent(event)

    def eventFilter(self, obj, event):
        """Filter events - kept for compatibility but keyReleaseEvent handles Ctrl"""
        return super().eventFilter(obj, event)

    def center_on_parent(self):
        """Center dialog on parent window"""
        if self.parent():
            parent_geo = self.parent().geometry()
            dialog_geo = self.geometry()

            x = parent_geo.x() + (parent_geo.width() - dialog_geo.width()) // 2
            y = parent_geo.y() + (parent_geo.height() - dialog_geo.height()) // 2

            self.move(x, y)




# """
# This implements the tab switcher popup widget
# """

# from PyQt6.QtWidgets import (
    # QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QLabel
# )
# from PyQt6.QtCore import Qt, QEvent, QTimer
# from PyQt6.QtGui import QKeyEvent
# from pathlib import Path


# class TabSwitcherDialog(QDialog):
    # """
    # Tab switcher popup dialog with recent order navigation

    # Shows all open tabs in recently-used order, allows quick navigation
    # """

    # def __init__(self, parent, tab_widget, recent_order):
        # """
        # Initialize tab switcher

        # Args:
            # parent: Parent widget (WorkspaceIDE)
            # tab_widget: QTabWidget containing the tabs
            # recent_order: List of tab indices in recently-used order
        # """
        # super().__init__(parent)

        # self.tab_widget = tab_widget
        # self.recent_order = recent_order
        # self.original_tab = tab_widget.currentIndex()
        # self.selected_tab = None
        # self.ctrl_pressed = True  # Track Ctrl key state

        # # Setup dialog
        # self.setWindowFlags(
            # Qt.WindowType.Popup |
            # Qt.WindowType.FramelessWindowHint |
            # Qt.WindowType.WindowStaysOnTopHint
        # )
        # self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # self.setup_ui()
        # self.populate_tabs()

        # # Install event filter to detect Ctrl release
        # self.installEventFilter(self)

        # # Position dialog at center of parent
        # self.center_on_parent()

    # def setup_ui(self):
        # """Setup the UI layout"""
        # layout = QVBoxLayout(self)
        # layout.setContentsMargins(10, 10, 10, 10)
        # layout.setSpacing(5)

        # # Title label
        # title = QLabel("Open Files (Recently Used)")
        # title.setStyleSheet("""
            # QLabel {
                # color: #CCCCCC;
                # font-weight: bold;
                # font-size: 12px;
                # padding: 5px;
            # }
        # """)
        # layout.addWidget(title)

        # # Tab list
        # self.list_widget = QListWidget()
        # self.list_widget.setStyleSheet("""
            # QListWidget {
                # background-color: #2B2B2B;
                # color: #A9B7C6;
                # border: 2px solid #4A9EFF;
                # border-radius: 5px;
                # outline: none;
                # font-size: 11px;
            # }
            # QListWidget::item {
                # padding: 8px;
                # border-bottom: 1px solid #3C3F41;
            # }
            # QListWidget::item:selected {
                # background-color: #4A9EFF;
                # color: white;
            # }
            # QListWidget::item:hover {
                # background-color: #3C3F41;
            # }
        # """)
        # self.list_widget.setMinimumWidth(500)
        # self.list_widget.setMaximumHeight(400)

        # # Connect signals
        # self.list_widget.itemClicked.connect(self.on_item_clicked)
        # self.list_widget.itemActivated.connect(self.on_item_activated)

        # layout.addWidget(self.list_widget)

        # # Instructions label
        # instructions = QLabel("↑↓: Navigate  •  Enter: Select  •  Esc: Cancel")
        # instructions.setStyleSheet("""
            # QLabel {
                # color: #888888;
                # font-size: 10px;
                # padding: 2px;
            # }
        # """)
        # layout.addWidget(instructions)

    # def populate_tabs(self):
        # """Populate the list with tabs in recent order"""
        # self.list_widget.clear()

        # for idx in self.recent_order:
            # if idx < 0 or idx >= self.tab_widget.count():
                # continue

            # editor = self.tab_widget.widget(idx)
            # if not editor:
                # continue

            # # Get file info
            # if hasattr(editor, 'file_path') and editor.file_path:
                # file_path = Path(editor.file_path)
                # file_name = file_path.name
                # file_dir = str(file_path.parent)
            # else:
                # file_name = self.tab_widget.tabText(idx)
                # file_dir = "Untitled"

            # # Create list item
            # item = QListWidgetItem()

            # # Show filename on first line, path on second
            # item_text = f"{file_name}\n  {file_dir}"
            # item.setText(item_text)
            # item.setData(Qt.ItemDataRole.UserRole, idx)  # Store tab index

            # # Add modified indicator
            # if hasattr(editor, 'document') and editor.document().isModified():
                # item.setText(f"● {item_text}")

            # self.list_widget.addItem(item)

        # # Select second item (first is current, second is most recent)
        # if self.list_widget.count() > 1:
            # self.list_widget.setCurrentRow(1)
            # self.preview_tab(1)
        # elif self.list_widget.count() == 1:
            # self.list_widget.setCurrentRow(0)

    # def preview_tab(self, row):
        # """Preview the tab at the given row without closing dialog"""
        # item = self.list_widget.item(row)
        # if item:
            # tab_index = item.data(Qt.ItemDataRole.UserRole)
            # if tab_index is not None:
                # self.tab_widget.setCurrentIndex(tab_index)

    # def on_item_clicked(self, item):
        # """Handle mouse click on item"""
        # tab_index = item.data(Qt.ItemDataRole.UserRole)
        # if tab_index is not None:
            # self.selected_tab = tab_index
            # self.accept()

    # def on_item_activated(self, item):
        # """Handle Enter key or double-click"""
        # self.on_item_clicked(item)

    # def keyPressEvent(self, event: QKeyEvent):
        # """Handle keyboard navigation"""
        # key = event.key()
        # modifiers = event.modifiers()

        # if key == Qt.Key.Key_Escape:
            # # Cancel - return to original tab
            # self.tab_widget.setCurrentIndex(self.original_tab)
            # self.reject()
            # return

        # elif key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            # # Activate selected tab
            # current_item = self.list_widget.currentItem()
            # if current_item:
                # self.on_item_activated(current_item)
            # return

        # elif key == Qt.Key.Key_Tab:
            # # Ctrl+Tab or Ctrl+Shift+Tab
            # current_row = self.list_widget.currentRow()

            # if modifiers & Qt.KeyboardModifier.ShiftModifier:
                # # Move up (backwards)
                # new_row = current_row - 1
                # if new_row < 0:
                    # new_row = self.list_widget.count() - 1
            # else:
                # # Move down (forwards)
                # new_row = current_row + 1
                # if new_row >= self.list_widget.count():
                    # new_row = 0

            # self.list_widget.setCurrentRow(new_row)
            # self.preview_tab(new_row)
            # return

        # elif key == Qt.Key.Key_Up:
            # # Up arrow
            # current_row = self.list_widget.currentRow()
            # new_row = max(0, current_row - 1)
            # self.list_widget.setCurrentRow(new_row)
            # self.preview_tab(new_row)
            # return

        # elif key == Qt.Key.Key_Down:
            # # Down arrow
            # current_row = self.list_widget.currentRow()
            # new_row = min(self.list_widget.count() - 1, current_row + 1)
            # self.list_widget.setCurrentRow(new_row)
            # self.preview_tab(new_row)
            # return

        # super().keyPressEvent(event)

    # def eventFilter(self, obj, event):
        # """Filter events to detect Ctrl key release"""
        # if event.type() == QEvent.Type.KeyRelease:
            # if event.key() == Qt.Key.Key_Control:
                # # Ctrl released - activate selected tab
                # current_item = self.list_widget.currentItem()
                # if current_item:
                    # self.selected_tab = current_item.data(Qt.ItemDataRole.UserRole)
                # self.accept()
                # return True

        # return super().eventFilter(obj, event)

    # def center_on_parent(self):
        # """Center dialog on parent window"""
        # if self.parent():
            # parent_geo = self.parent().geometry()
            # dialog_geo = self.geometry()

            # x = parent_geo.x() + (parent_geo.width() - dialog_geo.width()) // 2
            # y = parent_geo.y() + (parent_geo.height() - dialog_geo.height()) // 2

            # self.move(x, y)
