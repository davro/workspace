# ============================================================================
# managers/tab_manager.py
# ============================================================================

from pathlib import Path
from PyQt6.QtWidgets import QMessageBox, QInputDialog, QLineEdit
from PyQt6.QtCore import QTimer
from ide.core.CodeEditor import CodeEditor


class TabManager:
    """Manages editor tabs and their operations"""

    def __init__(self, tabs_widget, parent):
        self.tabs = tabs_widget
        self.parent = parent


    def open_file_by_path(self, path, settings=None):
        """Open a file in a new tab or switch to existing tab"""
        # Check if already open
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if isinstance(widget, CodeEditor) and widget.file_path == str(path):
                self.tabs.setCurrentIndex(i)

                # Track in recent files when switching to existing tab
                if hasattr(self.parent, 'recent_files_manager'):
                    self.parent.recent_files_manager.add_file(str(path))

                return widget

        # Create new editor
        if settings is None:
            settings = {}

        editor = CodeEditor(
            font_size=settings.get('editor_font_size', 11),
            tab_width=settings.get('tab_width', 4),
            show_line_numbers=settings.get('show_line_numbers', True),
            gutter_width=settings.get('gutter_width', 10)
        )

        # *** NEW: Connect file monitor ***
        if hasattr(self.parent, 'file_monitor'):
            editor.set_file_monitor(self.parent.file_monitor)

        if editor.load_file(str(path)):
            tab_index = self.tabs.addTab(editor, path.name)
            self.tabs.setTabToolTip(tab_index, str(path))
            editor.textChanged.connect(lambda: self.parent.on_editor_modified(editor))
            self.tabs.setCurrentWidget(editor)

            # CRITICAL: Add focus handler for split view
            self._add_focus_handler_if_needed(editor)

            # Track in recent files when opening new file
            if hasattr(self.parent, 'recent_files_manager'):
                self.parent.recent_files_manager.add_file(str(path))

            return editor

        return None

    def _add_focus_handler_if_needed(self, editor):
        """Add focus handler to editor if in split view"""
        if not hasattr(self.parent, 'split_manager'):
            return

        if not self.parent.split_manager.is_split():
            return

        # Find which group this editor belongs to
        for group_id, group in enumerate(self.parent.split_manager.groups):
            if group.tabs == self.tabs:
                # Found the group - add focus handler
                self.parent.split_manager.add_focus_handler_to_editor(editor, group_id)
                break

    def close_tab(self, index):
        """Close a tab at the given index"""
        editor = self.tabs.widget(index)

        # *** NEW: Stop monitoring file ***
        if isinstance(editor, CodeEditor) and hasattr(editor, 'file_path') and editor.file_path:
            if hasattr(self.parent, 'file_monitor'):
                self.parent.file_monitor.unwatch_file(editor.file_path)

        if isinstance(editor, CodeEditor) and editor.document().isModified():
            reply = QMessageBox.question(
                self.parent,
                "Unsaved Changes",
                f"Save changes to {self.tabs.tabText(index)}?",
                QMessageBox.StandardButton.Yes |
                QMessageBox.StandardButton.No |
                QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Yes:
                editor.save_file()
            elif reply == QMessageBox.StandardButton.Cancel:
                return False

        # Update tab order tracking
        if hasattr(self.parent, 'tab_order_manager'):
            self.parent.tab_order_manager.remove_tab(index)

        self.tabs.removeTab(index)
        return True

    def close_tab_by_path(self, file_path):
        """Close tab with the given file path"""
        for i in range(self.tabs.count()):
            editor = self.tabs.widget(i)
            if isinstance(editor, CodeEditor) and editor.file_path == file_path:
                self.tabs.removeTab(i)
                return True
        return False

    def close_other_tabs(self, keep_index):
        """Close all tabs except the one at keep_index"""
        indices_to_close = [i for i in range(self.tabs.count()) if i != keep_index]

        for i in reversed(indices_to_close):
            if not self.close_tab(i):
                break

    def close_all_tabs(self):
        """Close all tabs"""
        while self.tabs.count() > 0:
            if not self.close_tab(0):
                break

    def save_tab(self, index):
        """Save the file in the tab at the given index"""
        editor = self.tabs.widget(index)
        if isinstance(editor, CodeEditor):
            if editor.save_file():
                editor.document().setModified(False)
                self.parent.on_editor_modified(editor)
                self.parent.status_message.setText("File saved")
                QTimer.singleShot(2000, lambda: self.parent.status_message.setText(""))
                return True
        return False

    def save_all_tabs(self):
        """Save all modified files"""
        saved_count = 0
        for i in range(self.tabs.count()):
            editor = self.tabs.widget(i)
            if isinstance(editor, CodeEditor) and editor.document().isModified():
                if editor.save_file():
                    editor.document().setModified(False)
                    self.parent.on_editor_modified(editor)
                    saved_count += 1

        if saved_count > 0:
            self.parent.status_message.setText(f"Saved {saved_count} file(s)")
            QTimer.singleShot(3000, lambda: self.parent.status_message.setText(""))
        else:
            self.parent.status_message.setText("No files to save")
            QTimer.singleShot(2000, lambda: self.parent.status_message.setText(""))

        return saved_count


    def get_current_editor(self):
        """Get the currently active editor"""
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, CodeEditor) else None
