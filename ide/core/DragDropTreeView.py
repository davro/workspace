"""
File Explorer Drag and Drop Implementation

Features:
- Drag files and folders within the file tree
- Move files/folders to different directories
- Visual feedback during drag operation
- Confirmation before overwriting
- Handles edge cases (can't move into self, etc.)
- Updates tree view automatically
- Undo support (optional)
- Enter key to open files
"""

# ============================================================================
# DragDropTreeView.py in ide/core/ 
# ============================================================================

"""
Custom QTreeView with drag and drop support
"""

from PyQt6.QtWidgets import QTreeView, QMessageBox
from PyQt6.QtCore import Qt, QModelIndex, pyqtSignal
from PyQt6.QtGui import QDragMoveEvent, QDropEvent, QKeyEvent
from pathlib import Path
import shutil


class DragDropTreeView(QTreeView):
    """
    Enhanced QTreeView with drag and drop support for files and folders
    
    Features:
    - Drag files/folders to move them
    - Visual feedback during drag
    - Validation before drop
    - Auto-refresh after move
    - Enter key to open files
    """
    
    # Signal emitted when Enter is pressed on a file
    fileActivated = pyqtSignal(QModelIndex)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Enable drag and drop
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QTreeView.DragDropMode.InternalMove)
        
        # Track what's being dragged
        self.dragged_path = None
    
    def keyPressEvent(self, event: QKeyEvent):
        """Handle key press events - open files on Enter/Return"""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # Get currently selected index(es)
            selected_indexes = self.selectedIndexes()
            
            if not selected_indexes:
                super().keyPressEvent(event)
                return
            
            # Filter to only column 0 (file name column) to avoid duplicates
            selected_indexes = [idx for idx in selected_indexes if idx.column() == 0]
            
            model = self.model()
            opened_files = []
            
            for index in selected_indexes:
                if index.isValid():
                    file_path = Path(model.filePath(index))
                    
                    # Only open files, not directories
                    if file_path.is_file():
                        # Emit signal or trigger double-click behavior
                        self.doubleClicked.emit(index)
                        opened_files.append(file_path.name)
                    elif file_path.is_dir():
                        # For directories, toggle expansion
                        if self.isExpanded(index):
                            self.collapse(index)
                        else:
                            self.expand(index)
            
            # Show status message if files were opened
            if opened_files and hasattr(self.window(), 'status_message'):
                if len(opened_files) == 1:
                    msg = f"Opened: {opened_files[0]}"
                else:
                    msg = f"Opened {len(opened_files)} files"
                
                self.window().status_message.setText(msg)
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(3000, lambda: self.window().status_message.setText(""))
            
            event.accept()
            return
        
        # Let parent handle other keys
        super().keyPressEvent(event)
    
    def startDrag(self, supportedActions):
        """Start drag operation"""
        index = self.currentIndex()
        if not index.isValid():
            return
        
        # Get the file path being dragged
        model = self.model()
        self.dragged_path = Path(model.filePath(index))
        
        # Start the drag
        super().startDrag(supportedActions)
    
    def dragEnterEvent(self, event):
        """Accept drag enter"""
        if self.dragged_path:
            event.accept()
        else:
            event.ignore()
    
    def dragMoveEvent(self, event: QDragMoveEvent):
        """Handle drag move to show where item will be dropped"""
        if not self.dragged_path:
            event.ignore()
            return
        
        # Get the index where we're hovering
        index = self.indexAt(event.position().toPoint())
        
        if not index.isValid():
            event.ignore()
            return
        
        # Get the target path
        model = self.model()
        target_path = Path(model.filePath(index))
        
        # If target is a file, use its parent directory
        if target_path.is_file():
            target_path = target_path.parent
        
        # Validate the drop target
        if self.validate_drop_target(self.dragged_path, target_path):
            event.accept()
        else:
            event.ignore()
    
    def dropEvent(self, event: QDropEvent):
        """Handle drop - move the file/folder"""
        if not self.dragged_path:
            event.ignore()
            return
        
        # Get the drop target
        index = self.indexAt(event.position().toPoint())
        
        if not index.isValid():
            event.ignore()
            return
        
        model = self.model()
        target_path = Path(model.filePath(index))
        
        # If target is a file, use its parent directory
        if target_path.is_file():
            target_path = target_path.parent
        
        # Perform the move
        if self.move_item(self.dragged_path, target_path):
            event.accept()
            
            # Refresh the view
            self.model().layoutChanged.emit()
        else:
            event.ignore()
        
        # Clear dragged path
        self.dragged_path = None
    
    def validate_drop_target(self, source: Path, target: Path) -> bool:
        """
        Validate if source can be moved to target
        
        Args:
            source: Path being moved
            target: Destination directory
            
        Returns:
            True if move is valid
        """
        # Can't move to itself
        if source == target:
            return False
        
        # Can't move into itself (for directories)
        if source.is_dir() and target.is_relative_to(source):
            return False
        
        # Can't move to same parent (no-op)
        if source.parent == target:
            return False
        
        # Target must be a directory
        if not target.is_dir():
            return False
        
        return True
    
    def move_item(self, source: Path, target_dir: Path) -> bool:
        """
        Move file or folder to target directory
        
        Args:
            source: Path to move
            target_dir: Destination directory
            
        Returns:
            True if successful
        """
        try:
            destination = target_dir / source.name
            
            # Check if destination already exists
            if destination.exists():
                reply = QMessageBox.question(
                    self,
                    "Confirm Overwrite",
                    f"'{source.name}' already exists in the destination.\n\n"
                    "Do you want to replace it?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.No:
                    return False
                
                # Remove existing destination
                if destination.is_dir():
                    shutil.rmtree(destination)
                else:
                    destination.unlink()
            
            # Perform the move
            shutil.move(str(source), str(destination))
            
            # Show success message in parent's status bar
            if hasattr(self.parent(), 'status_message'):
                self.parent().status_message.setText(
                    f"Moved '{source.name}' to '{target_dir.name}'"
                )
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(3000, lambda: self.parent().status_message.setText(""))
            
            return True
            
        except PermissionError:
            QMessageBox.critical(
                self,
                "Permission Error",
                f"Cannot move '{source.name}':\nPermission denied"
            )
            return False
        
        except Exception as e:
            QMessageBox.critical(
                self,
                "Move Error",
                f"Cannot move '{source.name}':\n{str(e)}"
            )
            return False