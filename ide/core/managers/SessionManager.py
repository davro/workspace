# ============================================================================
# managers/session_manager.py
# ============================================================================

import json
from pathlib import Path
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QTextCursor


class SessionManager:
    """Handles session saving and restoration"""

    def __init__(self, session_file, parent):
        self.session_file = session_file
        self.parent = parent

    def save_session(self, tabs_widget, main_splitter):
        """Save the current session state"""
        open_files = []
        active_index = tabs_widget.currentIndex()

        # Collect open file information
        for i in range(tabs_widget.count()):
            editor = tabs_widget.widget(i)
            if hasattr(editor, 'file_path') and editor.file_path:
                cursor = editor.textCursor()
                scrollbar = editor.verticalScrollBar()

                file_info = {
                    'path': editor.file_path,
                    'cursor_line': cursor.blockNumber(),
                    'cursor_column': cursor.columnNumber(),
                    'scroll_position': scrollbar.value()
                }
                open_files.append(file_info)

        session_data = {
            'open_files': open_files,
            'active_index': active_index,
            'main_splitter_sizes': main_splitter.sizes(),
            'window_geometry': {
                'x': self.parent.x(),
                'y': self.parent.y(),
                'width': self.parent.width(),
                'height': self.parent.height(),
                'maximized': self.parent.isMaximized()
            }
        }

        try:
            with open(self.session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving session: {e}")
            return False

    def restore_session(self, tab_manager, settings):
        """Restore a previously saved session"""
        if not self.session_file.exists():
            return False

        try:
            with open(self.session_file, 'r') as f:
                session_data = json.load(f)

            # Restore window geometry
            geom = session_data.get('window_geometry', {})
            if geom:
                if not geom.get('maximized', False):
                    self.parent.setGeometry(
                        geom.get('x', 100),
                        geom.get('y', 100),
                        geom.get('width', 1400),
                        geom.get('height', 900)
                    )
                else:
                    self.parent.showMaximized()

            # Restore open files
            open_files = session_data.get('open_files', [])
            for file_info in open_files:
                if isinstance(file_info, str):
                    # Old format compatibility
                    file_path = file_info
                    cursor_line = cursor_column = scroll_position = 0
                else:
                    # New format with cursor position
                    file_path = file_info.get('path')
                    cursor_line = file_info.get('cursor_line', 0)
                    cursor_column = file_info.get('cursor_column', 0)
                    scroll_position = file_info.get('scroll_position', 0)

                file_path_obj = Path(file_path)
                if file_path_obj.exists():
                    editor = tab_manager.open_file_by_path(file_path_obj, settings)

                    if editor:
                        # Restore cursor position
                        cursor = editor.textCursor()
                        cursor.movePosition(QTextCursor.MoveOperation.Start)
                        cursor.movePosition(
                            QTextCursor.MoveOperation.Down,
                            QTextCursor.MoveMode.MoveAnchor,
                            cursor_line
                        )
                        cursor.movePosition(
                            QTextCursor.MoveOperation.Right,
                            QTextCursor.MoveMode.MoveAnchor,
                            cursor_column
                        )
                        editor.setTextCursor(cursor)

                        # Restore scroll position
                        def restore_scroll(ed=editor, pos=scroll_position):
                            scrollbar = ed.verticalScrollBar()
                            scrollbar.setValue(pos)
                        QTimer.singleShot(50, restore_scroll)

            # Restore active tab
            active_index = session_data.get('active_index', 0)
            if 0 <= active_index < tab_manager.tabs.count():
                tab_manager.tabs.setCurrentIndex(active_index)

            # Store splitter sizes for later application
            self.parent.saved_main_sizes = session_data.get('main_splitter_sizes', None)

            if tab_manager.tabs.count() > 0:
                self.parent.status_message.setText(
                    f"Restored {tab_manager.tabs.count()} file(s) with positions"
                )
                QTimer.singleShot(3000, lambda: self.parent.status_message.setText(""))

            return True

        except Exception as e:
            print(f"Error restoring session: {e}")
            return False
