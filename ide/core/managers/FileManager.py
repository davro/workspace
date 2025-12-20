# ============================================================================
# managers/file_manager.py
# ============================================================================

from pathlib import Path
from PyQt6.QtWidgets import QInputDialog, QMessageBox, QLineEdit
from PyQt6.QtCore import QTimer


class FileManager:
    """Handles all file system operations"""

    def __init__(self, workspace_path, parent):
        self.workspace_path = workspace_path
        self.parent = parent

    def create_new_file(self, parent_dir):
        """Create a new file in the specified directory"""
        name, ok = QInputDialog.getText(
            self.parent,
            "New File",
            "Enter file name:",
            QLineEdit.EchoMode.Normal
        )

        if ok and name:
            if not name.strip():
                QMessageBox.warning(self.parent, "Invalid Name", "File name cannot be empty")
                return None

            file_path = parent_dir / name
            try:
                if file_path.exists():
                    QMessageBox.warning(self.parent, "Error", f"'{name}' already exists")
                    return None

                file_path.touch()
                self.parent.status_message.setText(f"Created file: {name}")
                QTimer.singleShot(3000, lambda: self.parent.status_message.setText(""))
                return file_path

            except Exception as e:
                QMessageBox.critical(self.parent, "Error", f"Could not create file: {e}")
                return None

    def create_new_folder(self, parent_dir):
        """Create a new folder in the specified directory"""
        name, ok = QInputDialog.getText(
            self.parent,
            "New Folder",
            "Enter folder name:",
            QLineEdit.EchoMode.Normal
        )

        if ok and name:
            if not name.strip():
                QMessageBox.warning(self.parent, "Invalid Name", "Folder name cannot be empty")
                return None

            folder_path = parent_dir / name
            try:
                if folder_path.exists():
                    QMessageBox.warning(self.parent, "Error", f"'{name}' already exists")
                    return None

                folder_path.mkdir()
                self.parent.status_message.setText(f"Created folder: {name}")
                QTimer.singleShot(3000, lambda: self.parent.status_message.setText(""))
                return folder_path

            except Exception as e:
                QMessageBox.critical(self.parent, "Error", f"Could not create folder: {e}")
                return None

    def rename_item(self, path, tab_manager):
        """Rename a file or folder"""
        old_name = path.name
        new_name, ok = QInputDialog.getText(
            self.parent,
            "Rename",
            f"Rename '{old_name}' to:",
            QLineEdit.EchoMode.Normal,
            old_name
        )

        if ok and new_name:
            if not new_name.strip():
                QMessageBox.warning(self.parent, "Invalid Name", "Name cannot be empty")
                return False

            if new_name == old_name:
                return False

            new_path = path.parent / new_name
            try:
                if new_path.exists():
                    QMessageBox.warning(self.parent, "Error", f"'{new_name}' already exists")
                    return False

                # Close tab if it's a file being renamed
                if path.is_file():
                    tab_manager.close_tab_by_path(str(path))

                path.rename(new_path)
                self.parent.status_message.setText(f"Renamed '{old_name}' to '{new_name}'")
                QTimer.singleShot(3000, lambda: self.parent.status_message.setText(""))

                # Reopen if it was a file
                if new_path.is_file():
                    tab_manager.open_file_by_path(new_path)

                return True

            except Exception as e:
                QMessageBox.critical(self.parent, "Error", f"Could not rename: {e}")
                return False

    def delete_item(self, path, tab_manager):
        """Delete a file or folder"""
        item_type = "folder" if path.is_dir() else "file"

        reply = QMessageBox.question(
            self.parent,
            "Confirm Delete",
            f"Are you sure you want to delete this {item_type}?\n\n{path.name}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Close tab if it's a file
                if path.is_file():
                    tab_manager.close_tab_by_path(str(path))

                if path.is_dir():
                    import shutil
                    shutil.rmtree(path)
                else:
                    path.unlink()

                self.parent.status_message.setText(f"Deleted: {path.name}")
                QTimer.singleShot(3000, lambda: self.parent.status_message.setText(""))
                return True

            except Exception as e:
                QMessageBox.critical(self.parent, "Error", f"Could not delete: {e}")
                return False

        return False


