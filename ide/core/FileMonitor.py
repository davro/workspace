"""
File Monitor for detecting external file changes
Watches files for modifications outside the IDE and notifies editors
"""
from pathlib import Path
from PyQt6.QtCore import QObject, QFileSystemWatcher, pyqtSignal, QTimer
from PyQt6.QtWidgets import QMessageBox
import hashlib


class FileMonitor(QObject):
    """
    Monitors files for external changes and emits signals when changes are detected.
    
    Handles:
    - File modifications outside the editor
    - File deletions
    - File moves/renames
    - Debouncing rapid changes
    """
    
    # Signal emitted when a file is modified externally
    file_modified = pyqtSignal(str)  # file_path
    
    # Signal emitted when a file is deleted
    file_deleted = pyqtSignal(str)  # file_path
    
    def __init__(self):
        super().__init__()
        
        # Qt's file system watcher
        self.watcher = QFileSystemWatcher()
        
        # Track file hashes to avoid false positives from saves
        self.file_hashes = {}
        
        # Track which files are currently being saved (to ignore our own writes)
        self.saving_files = set()
        
        # Debounce timer to avoid multiple notifications for single change
        self.change_timers = {}
        
        # Connect watcher signals
        self.watcher.fileChanged.connect(self._on_file_changed)
        self.watcher.directoryChanged.connect(self._on_directory_changed)
    
    def watch_file(self, file_path: str):
        """
        Start watching a file for external changes.
        
        Args:
            file_path: Path to the file to watch
        """
        if not file_path or file_path in self.watcher.files():
            return
        
        # Add file to watcher
        if Path(file_path).exists():
            self.watcher.addPath(file_path)
            
            # Store initial hash
            self.file_hashes[file_path] = self._calculate_file_hash(file_path)
    
    def unwatch_file(self, file_path: str):
        """
        Stop watching a file.
        
        Args:
            file_path: Path to the file to stop watching
        """
        if file_path in self.watcher.files():
            self.watcher.removePath(file_path)
        
        # Clean up tracking data
        if file_path in self.file_hashes:
            del self.file_hashes[file_path]
        
        if file_path in self.change_timers:
            self.change_timers[file_path].stop()
            del self.change_timers[file_path]
        
        self.saving_files.discard(file_path)
    
    def mark_file_saving(self, file_path: str):
        """
        Mark a file as currently being saved to ignore self-triggered changes.
        
        Args:
            file_path: Path to the file being saved
        """
        self.saving_files.add(file_path)
        
        # Update hash after save completes
        QTimer.singleShot(100, lambda: self._update_hash_after_save(file_path))
    
    def _update_hash_after_save(self, file_path: str):
        """Update file hash after save and remove from saving set"""
        if Path(file_path).exists():
            self.file_hashes[file_path] = self._calculate_file_hash(file_path)
        
        self.saving_files.discard(file_path)
    
    def _on_file_changed(self, file_path: str):
        """
        Handle file change notification from QFileSystemWatcher.
        
        Args:
            file_path: Path to the changed file
        """
        # Ignore if we're currently saving this file
        if file_path in self.saving_files:
            return
        
        # Check if file still exists
        if not Path(file_path).exists():
            self.file_deleted.emit(file_path)
            self.unwatch_file(file_path)
            return
        
        # Debounce - create timer if not exists
        if file_path not in self.change_timers:
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(lambda: self._process_file_change(file_path))
            self.change_timers[file_path] = timer
        
        # Start/restart timer (300ms debounce)
        self.change_timers[file_path].start(300)
    
    def _process_file_change(self, file_path: str):
        """
        Process a file change after debounce period.
        
        Args:
            file_path: Path to the changed file
        """
        # Calculate new hash
        new_hash = self._calculate_file_hash(file_path)
        old_hash = self.file_hashes.get(file_path)
        
        # Only emit signal if content actually changed
        if new_hash != old_hash:
            self.file_hashes[file_path] = new_hash
            self.file_modified.emit(file_path)
        
        # Re-add to watcher if needed (Qt sometimes removes it)
        if file_path not in self.watcher.files():
            self.watcher.addPath(file_path)
    
    def _on_directory_changed(self, dir_path: str):
        """
        Handle directory change notification.
        
        Args:
            dir_path: Path to the changed directory
        """
        # Check if any watched files in this directory were deleted
        for file_path in list(self.watcher.files()):
            if Path(file_path).parent == Path(dir_path):
                if not Path(file_path).exists():
                    self.file_deleted.emit(file_path)
                    self.unwatch_file(file_path)
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """
        Calculate MD5 hash of file content.
        
        Args:
            file_path: Path to the file
            
        Returns:
            MD5 hash as hex string
        """
        try:
            hasher = hashlib.md5()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return ""
    
    def get_watched_files(self):
        """
        Get list of currently watched files.
        
        Returns:
            List of file paths
        """
        return self.watcher.files()