# ============================================================================
# SplitEditorManager.py in ide/core/managers/
# ============================================================================

"""
Manages split editor panes (horizontal/vertical splits)
Allows side-by-side editing with independent tab groups
"""

from PyQt6.QtWidgets import QSplitter, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt
from ide.core.TabBar import StyledTabWidget
from ide.core.CodeEditor import CodeEditor


class EditorGroup(QWidget):
    """
    A single editor group with its own tab widget
    Represents one pane in a split view
    """
    
    def __init__(self, parent_manager, group_id):
        super().__init__()
        self.parent_manager = parent_manager
        self.group_id = group_id
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Create tab widget for this group
        self.tabs = StyledTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        
        # Connect handlers for ALL groups (not just non-primary)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        # Context menu for tabs
        self.tabs.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.tabBar().customContextMenuRequested.connect(self.show_tab_context_menu)
        
        layout.addWidget(self.tabs)
        
    def close_tab(self, index):
        """Close tab in this group"""
        self.parent_manager.close_tab_in_group(self.group_id, index)
    
    def on_tab_changed(self, index):
        """Handle tab change in this group"""
        if index >= 0:  # Only process valid indices
            self.parent_manager.on_group_tab_changed(self.group_id, index)
    
    def show_tab_context_menu(self, position):
        """Show tab context menu"""
        self.parent_manager.show_tab_context_menu(self.group_id, position)
    
    def add_editor(self, editor, title, tooltip):
        """Add an editor to this group"""
        index = self.tabs.addTab(editor, title)
        self.tabs.setTabToolTip(index, tooltip)
        return index
    
    def get_editor_at(self, index):
        """Get editor at index"""
        return self.tabs.widget(index)
    
    def get_current_editor(self):
        """Get currently active editor in this group"""
        return self.tabs.currentWidget()
    
    def set_current_index(self, index):
        """Set current tab index"""
        self.tabs.setCurrentIndex(index)


class SplitEditorManager:
    """
    Manages split editor functionality
    Handles creation, removal, and coordination of editor groups
    """
    
    def __init__(self, parent):
        self.parent = parent
        self.splitter = None
        self.groups = []  # List of EditorGroup instances
        self.active_group_id = 0
        self.split_orientation = None  # None, Qt.Orientation.Horizontal, or Qt.Orientation.Vertical
        
    def initialize(self, container_layout):
        """
        Initialize the split editor system
        
        Args:
            container_layout: The layout where the editor will be placed
        """
        # Create initial single group
        group = EditorGroup(self, 0)
        self.groups.append(group)
        container_layout.addWidget(group)
        
        return group.tabs  # Return the tabs widget for backward compatibility
    
    def split_horizontal(self):
        """Split the editor area horizontally (top/bottom)"""
        self._create_split(Qt.Orientation.Vertical)  # Vertical splitter = horizontal split
    
    def split_vertical(self):
        """Split the editor area vertically (left/right)"""
        self._create_split(Qt.Orientation.Horizontal)  # Horizontal splitter = vertical split
    
    def _create_split(self, orientation):
        """
        Create a split with the given orientation
        
        Args:
            orientation: Qt.Orientation.Horizontal or Qt.Orientation.Vertical
        """
        if self.splitter is not None:
            # Already split, show message
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self.parent,
                "Already Split",
                "Editor is already split. Close the split first to create a new one."
            )
            return
        
        # Get the current group
        current_group = self.groups[self.active_group_id]
        parent_layout = current_group.parent().layout()
        
        # Remove current group from layout
        parent_layout.removeWidget(current_group)
        
        # Create splitter
        self.splitter = QSplitter(orientation)
        self.splitter.setHandleWidth(3)
        self.splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #3C3F41;
            }
            QSplitter::handle:hover {
                background-color: #4A9EFF;
            }
        """)
        
        # Add current group to splitter
        self.splitter.addWidget(current_group)
        
        # CRITICAL: Add focus handlers to ALL existing editors in current group
        # This ensures clicking in group 0 updates active_group_id correctly
        for i in range(current_group.tabs.count()):
            editor = current_group.tabs.widget(i)
            if isinstance(editor, CodeEditor):
                # Store original focusInEvent
                original_focus = editor.focusInEvent
                # Create new handler that updates active group
                def make_focus_handler(ed, gid, orig):
                    def handler(event):
                        self.active_group_id = gid
                        #print(f"[FOCUS] Editor clicked in group {gid}, file: {ed.file_path}")  # DEBUG
                        orig(event)
                    return handler
                editor.focusInEvent = make_focus_handler(editor, self.active_group_id, original_focus)
        
        # Create new group
        new_group = EditorGroup(self, len(self.groups))
        self.groups.append(new_group)
        self.splitter.addWidget(new_group)
        
        # Add splitter to layout
        parent_layout.addWidget(self.splitter)
        
        # Set equal sizes
        total_size = self.splitter.width() if orientation == Qt.Orientation.Horizontal else self.splitter.height()
        self.splitter.setSizes([total_size // 2, total_size // 2])
        
        self.split_orientation = orientation
        
        # Show status message
        direction = "vertically" if orientation == Qt.Orientation.Horizontal else "horizontally"
        self.parent.status_message.setText(f"Editor split {direction}")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self.parent.status_message.setText(""))
    
    def close_split(self):
        """Close the split and merge back to single editor"""
        if self.splitter is None:
            return
        
        # Get the layout
        parent_layout = self.splitter.parent().layout()
        
        # Remove splitter
        parent_layout.removeWidget(self.splitter)
        
        # Keep only the active group (with safety check)
        if self.active_group_id >= len(self.groups):
            self.active_group_id = 0
        
        active_group = self.groups[self.active_group_id]
        
        # Move all tabs from non-active groups to active group (AVOID DUPLICATES)
        for i, group in enumerate(self.groups):
            if i != self.active_group_id:
                # Move all tabs to active group
                while group.tabs.count() > 0:
                    editor = group.tabs.widget(0)
                    title = group.tabs.tabText(0)
                    tooltip = group.tabs.tabToolTip(0)
                    
                    # Check if this file is already open in active group
                    file_path = editor.file_path if isinstance(editor, CodeEditor) else None
                    already_open = False
                    
                    if file_path:
                        for j in range(active_group.tabs.count()):
                            existing_editor = active_group.tabs.widget(j)
                            if isinstance(existing_editor, CodeEditor) and existing_editor.file_path == file_path:
                                already_open = True
                                break
                    
                    # Remove from source group
                    group.tabs.removeTab(0)
                    
                    # Only add if not already open in active group
                    if not already_open:
                        active_group.add_editor(editor, title, tooltip)
                    else:
                        # Close the duplicate editor
                        editor.deleteLater()
        
        # Clear groups and keep only active
        self.groups = [active_group]
        self.active_group_id = 0
        
        # Add active group back to layout
        parent_layout.addWidget(active_group)
        
        # CRITICAL: Update parent's self.tabs reference
        if hasattr(self.parent, 'tabs'):
            self.parent.tabs = active_group.tabs
        
        # CRITICAL: Update TabManager's reference
        if hasattr(self.parent, 'tab_manager'):
            self.parent.tab_manager.tabs = active_group.tabs
        
        # CRITICAL: Reconnect event handlers to the new tab widget
        if hasattr(self.parent, 'tab_manager'):
            active_group.tabs.tabCloseRequested.disconnect()
            active_group.tabs.currentChanged.disconnect()
            
            active_group.tabs.tabCloseRequested.connect(
                lambda idx: self.parent.tab_manager.close_tab(idx)
            )
            active_group.tabs.currentChanged.connect(
                self.parent.on_editor_tab_changed
            )
            
            # Reconnect context menu
            if active_group.tabs.tabBar():
                active_group.tabs.tabBar().customContextMenuRequested.disconnect()
                active_group.tabs.tabBar().customContextMenuRequested.connect(
                    self.parent.show_tab_context_menu
                )
        
        # Clean up splitter
        self.splitter.deleteLater()
        self.splitter = None
        self.split_orientation = None
        
        # Show status message
        self.parent.status_message.setText("Split closed")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self.parent.status_message.setText(""))
    
    def move_tab_to_other_group(self):
        """Move current tab to the other editor group"""
        if self.splitter is None or len(self.groups) < 2:
            return
        
        current_group = self.groups[self.active_group_id]
        other_group_id = 1 if self.active_group_id == 0 else 0
        other_group = self.groups[other_group_id]
        
        # Get current tab
        current_index = current_group.tabs.currentIndex()
        if current_index < 0:
            return
        
        editor = current_group.tabs.widget(current_index)
        title = current_group.tabs.tabText(current_index)
        tooltip = current_group.tabs.tabToolTip(current_index)
        
        # Move to other group
        current_group.tabs.removeTab(current_index)
        new_index = other_group.add_editor(editor, title, tooltip)
        other_group.set_current_index(new_index)
        
        # Switch focus to other group AND the editor
        self.active_group_id = other_group_id
        editor.setFocus()  # Focus the editor for immediate typing
        
        # Update parent's find/replace and status bar
        if hasattr(self.parent, 'find_replace'):
            self.parent.find_replace.set_editor(editor)
        if hasattr(self.parent, 'statusbar_manager'):
            self.parent.statusbar_manager.update_file_info(editor)
        
        # Show status message
        self.parent.status_message.setText(f"Moved tab to group {other_group_id + 1}")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self.parent.status_message.setText(""))
    
    def focus_other_group(self):
        """Switch focus to the other editor group"""
        if len(self.groups) < 2:
            return
        
        self.active_group_id = 1 if self.active_group_id == 0 else 0
        group = self.groups[self.active_group_id]
        
        # Focus the group's current editor
        editor = group.get_current_editor()
        if editor:
            editor.setFocus()
            
            # Update find/replace and status bar
            if hasattr(self.parent, 'find_replace'):
                self.parent.find_replace.set_editor(editor)
            if hasattr(self.parent, 'statusbar_manager'):
                self.parent.statusbar_manager.update_file_info(editor)
        
        # Show status message
        self.parent.status_message.setText(f"Switched to group {self.active_group_id + 1}")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1000, lambda: self.parent.status_message.setText(""))
    
    def open_file_in_split(self, file_path):
        """
        Open a file in the non-active group (creates split if needed)
        
        Args:
            file_path: Path to file to open
        """
        if self.splitter is None:
            # Create vertical split first
            self.split_vertical()
        
        # Open in the other group
        other_group_id = 1 if self.active_group_id == 0 else 0
        other_group = self.groups[other_group_id]
        
        # Use parent's TabManager to open the file
        editor = self._open_file_in_group(other_group_id, file_path)
        
        if editor:
            # Focus the other group AND the editor
            self.active_group_id = other_group_id
            editor.setFocus()  # Focus the editor for immediate typing
            
            # Update parent's find/replace and status bar
            if hasattr(self.parent, 'find_replace'):
                self.parent.find_replace.set_editor(editor)
            if hasattr(self.parent, 'statusbar_manager'):
                self.parent.statusbar_manager.update_file_info(editor)
    
    def _open_file_in_group(self, group_id, file_path):
        """Open a file in a specific group"""
        from pathlib import Path
        
        group = self.groups[group_id]
        path = Path(file_path)
        
        # Check if already open in this group
        for i in range(group.tabs.count()):
            editor = group.tabs.widget(i)
            if isinstance(editor, CodeEditor) and editor.file_path == str(path):
                group.tabs.setCurrentIndex(i)
                return editor
        
        # Create new editor
        settings = self.parent.settings_manager.settings if hasattr(self.parent, 'settings_manager') else {}
        
        editor = CodeEditor(
            font_size=settings.get('editor_font_size', 11),
            tab_width=settings.get('tab_width', 4),
            show_line_numbers=settings.get('show_line_numbers', True),
            gutter_width=settings.get('gutter_width', 10)
        )
        
        if editor.load_file(str(path)):
            tab_index = group.add_editor(editor, path.name, str(path))
            editor.textChanged.connect(lambda: self.parent.on_editor_modified(editor))
            
            # CRITICAL: Track which group is active when editor gets focus
            editor.focusInEvent = self._create_focus_handler(editor, group_id)
            
            group.set_current_index(tab_index)
            
            # Track in recent files
            if hasattr(self.parent, 'recent_files_manager'):
                self.parent.recent_files_manager.add_file(str(path))
            
            return editor
        
        return None
    
    def _create_focus_handler(self, editor, group_id):
        """Create a focus handler that tracks which group is active"""
        original_focus = editor.focusInEvent
        
        # Use default argument to capture group_id value
        def focus_handler(event, gid=group_id):
            # Update active group when editor gets focus
            # Safety check: only update if group still exists
            if gid < len(self.groups):
                self.active_group_id = gid
                #print(f"[FOCUS] Editor clicked in group {gid}, file: {editor.file_path}")  # DEBUG
            else:
                #print(f"[FOCUS] WARNING: Invalid group {gid}, resetting to 0")  # DEBUG
                self.active_group_id = 0
            # Call original handler
            original_focus(event)
        
        return focus_handler
    
    def add_focus_handler_to_editor(self, editor, group_id):
        """
        Add focus handler to an editor (public method for TabManager)
        
        Args:
            editor: CodeEditor instance
            group_id: Which group the editor belongs to
        """
        if not isinstance(editor, CodeEditor):
            return
        
        editor.focusInEvent = self._create_focus_handler(editor, group_id)
    
    def get_active_group(self):
        """Get the currently active editor group"""
        # Safety check: ensure active_group_id is valid
        if self.active_group_id >= len(self.groups):
            self.active_group_id = 0
        
        return self.groups[self.active_group_id]
    
    def get_all_editors(self):
        """Get all open editors across all groups"""
        editors = []
        for group in self.groups:
            for i in range(group.tabs.count()):
                editor = group.tabs.widget(i)
                if isinstance(editor, CodeEditor):
                    editors.append(editor)
        return editors
    
    def close_tab_in_group(self, group_id, index):
        """Close a tab in a specific group"""
        # Validate group_id
        if group_id >= len(self.groups):
            return False
        
        group = self.groups[group_id]
        
        # Validate index
        if index < 0 or index >= group.tabs.count():
            return False
        
        editor = group.tabs.widget(index)
        
        if isinstance(editor, CodeEditor) and editor.document().isModified():
            from PyQt6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self.parent,
                "Unsaved Changes",
                f"Save changes to {group.tabs.tabText(index)}?",
                QMessageBox.StandardButton.Yes |
                QMessageBox.StandardButton.No |
                QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Yes:
                editor.save_file()
            elif reply == QMessageBox.StandardButton.Cancel:
                return False
        
        group.tabs.removeTab(index)
        
        # If this group is now empty and we have a split, close the split
        if group.tabs.count() == 0 and self.splitter is not None:
            self.close_split()
        
        return True
    
    def on_group_tab_changed(self, group_id, index):
        """Handle tab change in a group"""
        # Validate group_id
        if group_id >= len(self.groups) or index < 0:
            return
        
        group = self.groups[group_id]
        
        # Validate that the tab still exists
        if index >= group.tabs.count():
            return
        
        editor = group.tabs.widget(index)
        
        if isinstance(editor, CodeEditor):
            # Update find/replace
            if hasattr(self.parent, 'find_replace'):
                self.parent.find_replace.set_editor(editor)
            
            # Update status bar
            if hasattr(self.parent, 'statusbar_manager'):
                self.parent.statusbar_manager.update_file_info(editor)
                editor.cursorPositionChanged.connect(
                    lambda: self.parent.statusbar_manager.update_cursor_position(editor)
                )
    
    def show_tab_context_menu(self, group_id, position):
        """Show context menu for tab"""
        # Delegate to parent's existing tab context menu handler
        group = self.groups[group_id]
        
        # Temporarily set the active group
        old_active = self.active_group_id
        self.active_group_id = group_id
        
        # Call parent's context menu (needs to be adapted)
        if hasattr(self.parent, '_show_tab_context_menu_for_group'):
            self.parent._show_tab_context_menu_for_group(group, position)
        
        self.active_group_id = old_active
    
    def is_split(self):
        """Check if editor is currently split"""
        return self.splitter is not None
