# ============================================================================
# managers/FileManager.py
# ============================================================================

from pathlib import Path
import os

from send2trash import send2trash

from PyQt6.QtWidgets import (
    QInputDialog,
    QMessageBox,
    QLineEdit,
)
from PyQt6.QtCore import QTimer

from ide.core.CodeEditor import CodeEditor


class FileManager:
    """Handles file system operations for Workspace IDE."""

    def __init__(self, workspace_path, parent):
        self.workspace_path = Path(workspace_path)
        self.parent = parent

    # ========================================================================
    # Create
    # ========================================================================

    def create_new_file(self, parent_dir):
        """Create a new file in the specified directory."""
        name, ok = QInputDialog.getText(
            self.parent,
            "New File",
            "Enter file name:",
            QLineEdit.EchoMode.Normal,
        )

        if not ok:
            return None

        name = name.strip()

        if not name or name in (".", "..") or Path(name).name != name:
            QMessageBox.warning(
                self.parent,
                "Invalid Name",
                "Enter a valid file name without directory components.",
            )
            return None

        file_path = Path(parent_dir) / name

        try:
            if file_path.exists() or file_path.is_symlink():
                QMessageBox.warning(
                    self.parent,
                    "Error",
                    f"'{name}' already exists.",
                )
                return None

            file_path.touch()

            self._show_status(f"Created file: {name}")
            return file_path

        except OSError as exc:
            QMessageBox.critical(
                self.parent,
                "Error",
                f"Could not create file:\n{exc}",
            )
            return None

    def create_new_folder(self, parent_dir):
        """Create a new folder in the specified directory."""
        name, ok = QInputDialog.getText(
            self.parent,
            "New Folder",
            "Enter folder name:",
            QLineEdit.EchoMode.Normal,
        )

        if not ok:
            return None

        name = name.strip()

        if not name or name in (".", "..") or Path(name).name != name:
            QMessageBox.warning(
                self.parent,
                "Invalid Name",
                "Enter a valid folder name without directory components.",
            )
            return None

        folder_path = Path(parent_dir) / name

        try:
            if folder_path.exists() or folder_path.is_symlink():
                QMessageBox.warning(
                    self.parent,
                    "Error",
                    f"'{name}' already exists.",
                )
                return None

            folder_path.mkdir()

            self._show_status(f"Created folder: {name}")
            return folder_path

        except OSError as exc:
            QMessageBox.critical(
                self.parent,
                "Error",
                f"Could not create folder:\n{exc}",
            )
            return None

    # ========================================================================
    # Rename
    # ========================================================================

    def rename_item(self, path, tab_manager):
        """Rename a file or folder."""
        path = Path(path)
        old_name = path.name

        new_name, ok = QInputDialog.getText(
            self.parent,
            "Rename",
            f"Rename '{old_name}' to:",
            QLineEdit.EchoMode.Normal,
            old_name,
        )

        if not ok:
            return False

        new_name = new_name.strip()

        if not new_name or new_name in (".", "..") or Path(new_name).name != new_name:
            QMessageBox.warning(
                self.parent,
                "Invalid Name",
                "Enter a valid name without directory components.",
            )
            return False

        if new_name == old_name:
            return False

        new_path = path.parent / new_name

        try:
            if new_path.exists() or new_path.is_symlink():
                QMessageBox.warning(
                    self.parent,
                    "Error",
                    f"'{new_name}' already exists.",
                )
                return False

            # Preserve the existing behaviour for file renames.
            if path.is_file() and not path.is_symlink():
                tab_manager.close_tab_by_path(str(path))

            path.rename(new_path)

            self._show_status(f"Renamed '{old_name}' to '{new_name}'")

            if new_path.is_file() and not new_path.is_symlink():
                tab_manager.open_file_by_path(new_path)

            return True

        except OSError as exc:
            QMessageBox.critical(
                self.parent,
                "Error",
                f"Could not rename:\n{exc}",
            )
            return False

    # ========================================================================
    # Delete to Trash
    # ========================================================================

    @staticmethod
    def _normalise_path(path):
        """Normalise a path without resolving symlinks."""
        return Path(os.path.abspath(os.fspath(path)))

    def _get_tab_widgets(self):
        """Return unique editor tab widgets, including split groups."""
        tab_widgets = []

        def add_widget(widget):
            if widget is not None and widget not in tab_widgets:
                tab_widgets.append(widget)

        if hasattr(self.parent, "tabs"):
            add_widget(self.parent.tabs)

        split_manager = getattr(self.parent, "split_manager", None)

        if split_manager is not None:
            for group in getattr(split_manager, "groups", []):
                add_widget(getattr(group, "tabs", None))

        return tab_widgets

    def _find_affected_tabs(self, path):
        """Find open editors referring to the selected file or directory."""
        target = self._normalise_path(path)
        is_directory = (
            target.is_dir()
            and not target.is_symlink()
        )

        affected = []

        for tab_widget in self._get_tab_widgets():
            for index in range(tab_widget.count()):
                editor = tab_widget.widget(index)

                if not isinstance(editor, CodeEditor):
                    continue

                file_path = getattr(editor, "file_path", None)

                if not file_path:
                    continue

                editor_path = self._normalise_path(file_path)

                try:
                    matches = (
                        editor_path == target
                        or (
                            is_directory
                            and target in editor_path.parents
                        )
                    )
                except (OSError, ValueError):
                    matches = False

                if matches:
                    affected.append((tab_widget, index, editor))

        return affected

    def _confirm_unsaved_changes(self, affected_tabs):
        """
        Ask what to do with each modified editor before moving files
        to Trash. Return False if the operation should be cancelled.
        """
        modified_editors = [
            (tab_widget, index, editor)
            for tab_widget, index, editor in affected_tabs
            if editor.document().isModified()
        ]

        for tab_widget, index, editor in modified_editors:
            title = tab_widget.tabText(index)
            file_path = getattr(editor, "file_path", None)

            if file_path:
                title = Path(file_path).name

            message_box = QMessageBox(self.parent)
            message_box.setWindowTitle("Unsaved Changes")
            message_box.setIcon(QMessageBox.Icon.Warning)
            message_box.setText(
                f"'{title}' has unsaved changes."
            )
            message_box.setInformativeText(
                "Save the changes before moving this item to Trash?"
            )

            save_button = message_box.addButton(
                "Save",
                QMessageBox.ButtonRole.AcceptRole,
            )
            discard_button = message_box.addButton(
                "Discard",
                QMessageBox.ButtonRole.DestructiveRole,
            )
            cancel_button = message_box.addButton(
                "Cancel",
                QMessageBox.ButtonRole.RejectRole,
            )

            message_box.setDefaultButton(save_button)
            message_box.exec()

            clicked = message_box.clickedButton()

            if clicked == cancel_button:
                return False

            if clicked == save_button:
                if not editor.save_file():
                    QMessageBox.warning(
                        self.parent,
                        "Save Failed",
                        f"Could not save '{title}'.\n\n"
                        "The item will not be moved to Trash.",
                    )
                    return False

                editor.document().setModified(False)

                if hasattr(self.parent, "on_editor_modified"):
                    self.parent.on_editor_modified(editor)

            elif clicked != discard_button:
                # Treat closing the dialog or any unexpected response
                # as cancellation.
                return False

        return True

    def _close_trashed_tabs(self, affected_tabs):
        """Close editors only after the Trash operation succeeds."""
        # Group affected tabs by widget, removing higher indexes first.
        grouped = {}

        for tab_widget, index, editor in affected_tabs:
            grouped.setdefault(tab_widget, []).append(
                (index, editor)
            )

        for tab_widget, entries in grouped.items():
            for index, editor in sorted(
                entries,
                key=lambda entry: entry[0],
                reverse=True,
            ):
                # The indexes may have shifted, so locate the editor again.
                current_index = tab_widget.indexOf(editor)

                if current_index < 0:
                    continue

                tab_widget.removeTab(current_index)

                # Keep tab-order tracking in sync where available.
                if (
                    tab_widget is getattr(self.parent, "tabs", None)
                    and hasattr(self.parent, "tab_order_manager")
                ):
                    self.parent.tab_order_manager.remove_tab(
                        current_index
                    )

                # Unwatch only when no remaining editor uses this path.
                file_path = getattr(editor, "file_path", None)

                if file_path and hasattr(self.parent, "file_monitor"):
                    normalised = self._normalise_path(file_path)
                    still_open = False

                    for other_widget in self._get_tab_widgets():
                        for other_index in range(other_widget.count()):
                            other_editor = other_widget.widget(other_index)

                            if (
                                isinstance(other_editor, CodeEditor)
                                and getattr(other_editor, "file_path", None)
                            ):
                                if (
                                    self._normalise_path(
                                        other_editor.file_path
                                    ) == normalised
                                ):
                                    still_open = True
                                    break

                        if still_open:
                            break

                    if not still_open:
                        self.parent.file_monitor.unwatch_file(
                            str(file_path)
                        )

        if hasattr(self.parent, "mark_session_dirty"):
            self.parent.mark_session_dirty()

    def delete_item(self, path, tab_manager):
        """
        Move a file or directory to the desktop Trash.

        Despite retaining the existing method name, this no longer
        permanently deletes files.
        """
        path = Path(path)

        if not path.exists() and not path.is_symlink():
            QMessageBox.warning(
                self.parent,
                "Item Not Found",
                f"This item no longer exists:\n{path}",
            )
            return False

        target = self._normalise_path(path)
        workspace_root = self._normalise_path(self.workspace_path)

        # Never allow the workspace root itself to be trashed.
        if target == workspace_root:
            QMessageBox.warning(
                self.parent,
                "Protected Folder",
                "The workspace root cannot be moved to Trash.",
            )
            return False

        is_directory = path.is_dir() and not path.is_symlink()
        item_type = "folder" if is_directory else "file"

        reply = QMessageBox.question(
            self.parent,
            "Move to Trash",
            f"Move this {item_type} to Trash?\n\n{path.name}\n\n"
            "You can restore it later from your desktop Trash.",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return False

        # Include editors for files contained within a selected folder.
        affected_tabs = self._find_affected_tabs(path)

        # Resolve all unsaved changes before touching the filesystem.
        if not self._confirm_unsaved_changes(affected_tabs):
            return False

        try:
            # Send2Trash handles files, directories and symlinks.
            # Do not close tabs unless this operation succeeds.
            send2trash(str(path))

        except Exception as exc:
            QMessageBox.critical(
                self.parent,
                "Trash Failed",
                f"Could not move '{path.name}' to Trash.\n\n"
                f"{exc}\n\n"
                "The item has not been intentionally removed by "
                "Workspace IDE.",
            )
            return False

        self._close_trashed_tabs(affected_tabs)

        self._show_status(f"Moved to Trash: {path.name}")
        return True

    # ========================================================================
    # Status
    # ========================================================================

    def _show_status(self, message, timeout=3000):
        """Display a temporary status-bar message."""
        if hasattr(self.parent, "show_status_message"):
            self.parent.show_status_message(message, timeout)
            return

        if hasattr(self.parent, "status_message"):
            self.parent.status_message.setText(message)
            QTimer.singleShot(
                timeout,
                lambda: self.parent.status_message.setText(""),
            )
