# ============================================================================
# CombinedTreeDelegate.py in ide/core/
# ============================================================================

"""
Combined delegate that handles both file icons AND project highlighting
Merges FileIconDelegate and ProjectHighlightDelegate functionality
"""

from PyQt6.QtWidgets import QStyledItemDelegate, QStyle
from PyQt6.QtGui import QPainter, QFont, QColor
from PyQt6.QtCore import Qt, QRect
from pathlib import Path
from ide.core.FileIconProvider import FileIconProvider


class CombinedTreeDelegate(QStyledItemDelegate):
    """
    Delegate that handles:
    1. File/folder icons (unicode emojis)
    2. Project highlighting (for active projects)
    """
    
    def __init__(self, file_model, parent=None):
        super().__init__(parent)
        self.file_model = file_model
        self.icon_provider = FileIconProvider()
        self.active_projects = set()  # Paths of active projects
    
    def set_active_projects(self, projects):
        """Set the list of active project paths"""
        self.active_projects = set(str(p) for p in projects)
    
    def paint(self, painter, option, index):
        """Paint the item with icon and project highlighting"""
        if index.column() != 0:  # Only customize the first column
            super().paint(painter, option, index)
            return
        
        # Get file path
        file_path = Path(self.file_model.filePath(index))
        
        # Check if this path IS an active project (exact match only, not children)
        is_active_project = str(file_path) in self.active_projects
        
        # Check if folder is expanded
        tree_view = self.parent()
        is_expanded = tree_view.isExpanded(index) if file_path.is_dir() else False
        
        # Get icon text
        icon_text = self.icon_provider.get_icon_text(file_path, is_expanded)
        
        # Setup painter
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        
        # Draw background with project highlighting
        if option.state & QStyle.StateFlag.State_Selected:
            # Selected item
            painter.fillRect(option.rect, option.palette.highlight())
            text_color = option.palette.highlightedText().color()
        elif is_active_project:
            # Active project folder only - subtle highlight
            highlight_color = QColor("#2d4a2e")  # Subtle green tint
            painter.fillRect(option.rect, highlight_color)
            text_color = QColor("#a8d5a8")  # Light green text
        else:
            # Normal item
            text_color = option.palette.text().color()
        
        painter.setPen(text_color)
        
        # Draw icon
        icon_rect = QRect(option.rect.left() + 4, option.rect.top(), 20, option.rect.height())
        icon_font = QFont()
        icon_font.setPixelSize(14)
        painter.setFont(icon_font)
        painter.drawText(icon_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, icon_text)
        
        # Draw file name
        text_rect = QRect(option.rect.left() + 24, option.rect.top(), 
                         option.rect.width() - 24, option.rect.height())
        text_font = QFont()
        text_font.setPixelSize(14)
        
        # Make active project items bold
        if is_active_project:
            text_font.setBold(True)
        
        painter.setFont(text_font)
        
        # Get display text
        display_text = self.file_model.fileName(index)
        
        # Draw text with elision if needed
        elided_text = painter.fontMetrics().elidedText(
            display_text, Qt.TextElideMode.ElideRight, text_rect.width()
        )
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_text)
        
        painter.restore()
    
    def sizeHint(self, option, index):
        """Return the size hint for the item"""
        size = super().sizeHint(option, index)
        size.setHeight(max(size.height(), 22))  # Minimum height for icons
        return size

