
# ============================================================================
# ide/core/managers/SessionManager.py
# ============================================================================
import json
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QTextCursor


class SessionManager:
    """Handles session saving and restoration."""

    def __init__(self, session_file, parent):
        self.session_file = Path(session_file)
        self.parent = parent

    def _collect_expanded_directories(
        self, tree, file_model, workspace_root
    ):
        """Return expanded directory paths relative to the workspace root."""
        expanded = []
        root = Path(workspace_root).resolve()
        root_index = tree.rootIndex()

        def visit(parent_index):
            for row in range(file_model.rowCount(parent_index)):
                index = file_model.index(row, 0, parent_index)

                if not file_model.isDir(index):
                    continue

                if not tree.isExpanded(index):
                    continue

                directory = Path(file_model.filePath(index)).resolve()

                try:
                    relative = directory.relative_to(root)
                except ValueError:
                    continue

                expanded.append(relative.as_posix())
                visit(index)

        visit(root_index)
        return sorted(set(expanded), key=lambda path: (path.count("/"), path))

    def _restore_expanded_directories(
        self, tree, file_model, workspace_root, directories
    ):
        """Restore previously expanded directories, parents first."""
        root = Path(workspace_root).resolve()

        ordered = sorted(
            set(directories),
            key=lambda path: (str(path).count("/"), str(path))
        )

        for relative_path in ordered:
            try:
                relative = Path(relative_path)

                # Reject absolute paths and paths escaping the workspace.
                if relative.is_absolute() or ".." in relative.parts:
                    continue

                directory = (root / relative).resolve()
                directory.relative_to(root)

                if not directory.is_dir():
                    continue

                index = file_model.index(str(directory))

                if index.isValid() and file_model.isDir(index):
                    tree.expand(index)

            except (OSError, ValueError, RuntimeError):
                continue

    def save_session(
        self,
        tabs_widget,
        main_splitter,
        tree=None,
        file_model=None,
        workspace_root=None
    ):
        """Save editor state, window state and explorer tree state."""
        open_files = []
        active_index = tabs_widget.currentIndex()

        for i in range(tabs_widget.count()):
            editor = tabs_widget.widget(i)

            if not getattr(editor, "file_path", None):
                continue

            cursor = editor.textCursor()
            scrollbar = editor.verticalScrollBar()

            open_files.append({
                "path": editor.file_path,
                "cursor_line": cursor.blockNumber(),
                "cursor_column": cursor.columnNumber(),
                "scroll_position": scrollbar.value()
            })

        session_data = {
            "open_files": open_files,
            "active_index": active_index,
            "main_splitter_sizes": main_splitter.sizes(),
            "window_geometry": {
                "x": self.parent.x(),
                "y": self.parent.y(),
                "width": self.parent.width(),
                "height": self.parent.height(),
                "maximized": self.parent.isMaximized()
            }
        }

        # Preserve expanded folders in the existing session file.
        if tree is not None and file_model is not None and workspace_root:
            session_data["expanded_directories"] = (
                self._collect_expanded_directories(
                    tree, file_model, workspace_root
                )
            )

        try:
            self.session_file.parent.mkdir(parents=True, exist_ok=True)

            with self.session_file.open("w", encoding="utf-8") as handle:
                json.dump(session_data, handle, indent=2)

            return True

        except Exception as exc:
            print(f"Error saving session: {exc}")
            return False

    def restore_session(
        self,
        tab_manager,
        settings,
        tree=None,
        file_model=None,
        workspace_root=None
    ):
        """Restore editor state and the explorer tree from the last session."""
        if not self.session_file.exists():
            return False

        try:
            with self.session_file.open("r", encoding="utf-8") as handle:
                session_data = json.load(handle)

            # Restore window geometry.
            geometry = session_data.get("window_geometry", {})

            if geometry:
                if geometry.get("maximized", False):
                    self.parent.showMaximized()
                else:
                    self.parent.setGeometry(
                        geometry.get("x", 100),
                        geometry.get("y", 100),
                        geometry.get("width", 1400),
                        geometry.get("height", 900)
                    )

            # Restore expanded directories after the file model has loaded.
            expanded_directories = session_data.get(
                "expanded_directories", []
            )

            if (
                tree is not None
                and file_model is not None
                and workspace_root
                and isinstance(expanded_directories, list)
            ):
                QTimer.singleShot(
                    500,
                    lambda t=tree, m=file_model, r=workspace_root,
                    d=expanded_directories:
                        self._restore_expanded_directories(t, m, r, d)
                )

            # Restore open files. Supports the original string-only format.
            open_files = session_data.get("open_files", [])

            for file_info in open_files:
                if isinstance(file_info, str):
                    file_path = file_info
                    cursor_line = 0
                    cursor_column = 0
                    scroll_position = 0
                else:
                    file_path = file_info.get("path")
                    cursor_line = file_info.get("cursor_line", 0)
                    cursor_column = file_info.get("cursor_column", 0)
                    scroll_position = file_info.get("scroll_position", 0)

                if not file_path:
                    continue

                file_path_obj = Path(file_path)

                if not file_path_obj.exists():
                    continue

                editor = tab_manager.open_file_by_path(
                    file_path_obj, settings
                )

                if not editor:
                    continue

                cursor = editor.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.Start)
                cursor.movePosition(
                    QTextCursor.MoveOperation.Down,
                    QTextCursor.MoveMode.MoveAnchor,
                    max(0, cursor_line)
                )
                cursor.movePosition(
                    QTextCursor.MoveOperation.Right,
                    QTextCursor.MoveMode.MoveAnchor,
                    max(0, cursor_column)
                )

                editor.setTextCursor(cursor)

                QTimer.singleShot(
                    50,
                    lambda ed=editor, pos=scroll_position:
                        ed.verticalScrollBar().setValue(pos)
                )

            # Restore active tab.
            active_index = session_data.get("active_index", 0)

            if 0 <= active_index < tab_manager.tabs.count():
                tab_manager.tabs.setCurrentIndex(active_index)

            self.parent.saved_main_sizes = session_data.get(
                "main_splitter_sizes"
            )

            if tab_manager.tabs.count() > 0:
                self.parent.status_message.setText(
                    f"Restored {tab_manager.tabs.count()} file(s) "
                    "with positions"
                )
                QTimer.singleShot(
                    3000,
                    lambda: self.parent.status_message.setText("")
                )

            return True

        except Exception as exc:
            print(f"Error restoring session: {exc}")
            return False