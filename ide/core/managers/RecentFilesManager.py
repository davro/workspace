# ============================================================================
# RecentFilesManager.py in ide/core/managers/
# ============================================================================

"""
ide/core/managers/RecentFilesManager.py

Manages the recent files list with persistence and smart filtering
"""

from pathlib import Path
from typing import List
from PyQt6.QtWidgets import QMenu
from PyQt6.QtGui import QAction, QKeySequence


class RecentFilesManager:
    """
    Manages recently opened files

    Features:
    - Tracks up to MAX_RECENT files
    - Filters out non-existent files
    - Persists to settings
    - Creates dynamic menu with shortcuts
    """

    MAX_RECENT = 15  # Maximum number of recent files to track

    def __init__(self, settings_manager, parent):
        """
        Initialize recent files manager

        Args:
            settings_manager: SettingsManager instance
            parent: Parent WorkspaceIDE instance
        """
        self.settings_manager = settings_manager
        self.parent = parent
        self.recent_files = self._load_recent_files()

    def _load_recent_files(self) -> List[str]:
        """Load recent files from settings and filter out non-existent ones"""
        recent = self.settings_manager.get('recent_files', [])

        # Filter out files that no longer exist
        existing_files = []
        for file_path in recent:
            if Path(file_path).exists():
                existing_files.append(file_path)

        # Update settings if we filtered any files
        if len(existing_files) != len(recent):
            self.settings_manager.set('recent_files', existing_files)
            self.settings_manager.save()

        return existing_files

    def add_file(self, file_path: str):
        """
        Add a file to recent files list

        Args:
            file_path: Absolute path to the file
        """
        file_path = str(Path(file_path).resolve())

        # Remove if already exists (we'll add it to the front)
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)

        # Add to front of list
        self.recent_files.insert(0, file_path)

        # Trim to MAX_RECENT
        self.recent_files = self.recent_files[:self.MAX_RECENT]

        # Save to settings
        self.settings_manager.set('recent_files', self.recent_files)
        self.settings_manager.save()

    def get_recent_files(self) -> List[str]:
        """Get list of recent files (filtered for existing files)"""
        # Filter again in case files were deleted since last load
        existing = [f for f in self.recent_files if Path(f).exists()]

        if len(existing) != len(self.recent_files):
            self.recent_files = existing
            self.settings_manager.set('recent_files', self.recent_files)
            self.settings_manager.save()

        return self.recent_files

    def clear_recent_files(self):
        """Clear all recent files"""
        self.recent_files = []
        self.settings_manager.set('recent_files', [])
        self.settings_manager.save()

    def create_recent_files_menu(self, parent_menu: QMenu) -> QMenu:
        """
        Create Recent Files submenu with actions

        Args:
            parent_menu: Parent QMenu to add submenu to

        Returns:
            QMenu: The created recent files submenu
        """
        recent_menu = QMenu("Recent Files", self.parent)
        recent_menu.setToolTipsVisible(True)

        recent_files = self.get_recent_files()

        if not recent_files:
            # Show disabled "No recent files" action
            no_files_action = recent_menu.addAction("No recent files")
            no_files_action.setEnabled(False)
        else:
            # Add up to 9 recent files with keyboard shortcuts
            for i, file_path in enumerate(recent_files[:9]):
                path = Path(file_path)

                # Create action with file name
                action = QAction(f"📄 {path.name}", self.parent)

                # Set keyboard shortcut (Ctrl+1 through Ctrl+9)
                if i < 9:
                    action.setShortcut(QKeySequence(f"Ctrl+{i+1}"))

                # Set tooltip to show full path
                action.setToolTip(str(path))

                # Connect to open file handler
                action.triggered.connect(
                    lambda checked=False, p=file_path: self._open_recent_file(p)
                )

                recent_menu.addAction(action)

            # If there are more than 9 files, add them without shortcuts
            if len(recent_files) > 9:
                recent_menu.addSeparator()
                for file_path in recent_files[9:]:
                    path = Path(file_path)
                    action = QAction(f"📄 {path.name}", self.parent)
                    action.setToolTip(str(path))
                    action.triggered.connect(
                        lambda checked=False, p=file_path: self._open_recent_file(p)
                    )
                    recent_menu.addAction(action)

        # Add separator and clear option
        recent_menu.addSeparator()
        clear_action = recent_menu.addAction("Clear Recent Files")
        clear_action.triggered.connect(self._clear_and_update_menu)

        return recent_menu

    def _open_recent_file(self, file_path: str):
        """
        Open a recent file

        Args:
            file_path: Path to the file to open
        """
        path = Path(file_path)

        if not path.exists():
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self.parent,
                "File Not Found",
                f"The file no longer exists:\n\n{file_path}\n\n"
                "It will be removed from recent files."
            )
            # Remove from recent files
            if file_path in self.recent_files:
                self.recent_files.remove(file_path)
                self.settings_manager.set('recent_files', self.recent_files)
                self.settings_manager.save()
            return

        # Open the file using TabManager
        self.parent.tab_manager.open_file_by_path(
            path,
            self.parent.settings_manager.settings
        )

    def _clear_and_update_menu(self):
        """Clear recent files and refresh menu"""
        from PyQt6.QtWidgets import QMessageBox

        reply = QMessageBox.question(
            self.parent,
            "Clear Recent Files",
            "Are you sure you want to clear all recent files?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.clear_recent_files()
            # Menu will be recreated next time it's shown
