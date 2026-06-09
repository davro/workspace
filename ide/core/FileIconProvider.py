# ============================================================================
# FileIconProvider.py in ide/core/
# ============================================================================

"""
Provides unicode/emoji icons for files and folders based on file type
No image assets required - uses Unicode characters and emojis
"""

from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PyQt6.QtCore import Qt, QSize
from pathlib import Path


class FileIconProvider:
    """
    Provides unicode-based icons for files and folders
    Zero image dependencies - pure text icons
    """
    
    # Icon mappings by file extension
    ICON_MAP = {
        # Programming Languages
        '.py': '🐍',
        '.js': '📜',
        '.ts': '📘',
        '.jsx': '⚛️',
        '.tsx': '⚛️',
        '.java': '☕',
        '.cpp': '🔧',
        '.c': '🔧',
        '.h': '📋',
        '.cs': '#️⃣',
        '.go': '🐹',
        '.rs': '🦀',
        '.rb': '💎',
        '.php': '🐘',
        '.swift': '🦅',
        '.kt': '🎯',
        '.tl': '🔷',
        
        # Web
        '.html': '🌐',
        '.htm': '🌐',
        '.css': '🎨',
        '.scss': '🎨',
        '.sass': '🎨',
        '.less': '🎨',
        
        # Data/Config
        '.json': '📊',
        '.xml': '📄',
        '.yaml': '⚙️',
        '.yml': '⚙️',
        '.toml': '⚙️',
        '.ini': '⚙️',
        '.conf': '⚙️',
        '.cfg': '⚙️',
        '.env': '🔐',
        
        # Database
        '.sql': '🗄️',
        '.db': '💾',
        '.sqlite': '💾',
        '.sqlite3': '💾',
        
        # Documents
        '.md': '📝',
        '.txt': '📄',
        '.pdf': '📕',
        '.doc': '📘',
        '.docx': '📘',
        '.rtf': '📄',
        
        # Images
        '.png': '🖼️',
        '.jpg': '🖼️',
        '.jpeg': '🖼️',
        '.gif': '🖼️',
        '.svg': '🎨',
        '.ico': '🖼️',
        '.webp': '🖼️',
        
        # Archives
        '.zip': '📦',
        '.tar': '📦',
        '.gz': '📦',
        '.rar': '📦',
        '.7z': '📦',
        
        # Scripts
        '.sh': '🖥️',
        '.bash': '🖥️',
        '.zsh': '🖥️',
        '.bat': '🖥️',
        '.ps1': '🖥️',
        
        # Version Control
        '.git': '🌿',
        '.gitignore': '🚫',
        '.gitattributes': '🌿',
        
        # Build/Package
        'Makefile': '🔨',
        'Dockerfile': '🐳',
        'docker-compose.yml': '🐳',
        'package.json': '📦',
        'requirements.txt': '📦',
        'Gemfile': '💎',
        'Cargo.toml': '🦀',
        'pom.xml': '☕',
        
        # Other
        '.log': '📋',
        '.lock': '🔒',
    }
    
    # Special file names
    SPECIAL_FILES = {
        'README.md': '📖',
        'LICENSE': '⚖️',
        'CHANGELOG.md': '📜',
        '.env': '🔐',
        '.env.local': '🔐',
        '.env.example': '🔐',
    }
    
    # Folder icons
    FOLDER_CLOSED = '📁'
    FOLDER_OPEN = '📂'
    DEFAULT_FILE = '📄'
    
    @staticmethod
    def get_icon_text(file_path: Path, is_expanded: bool = False) -> str:
        """
        Get the icon text for a file or folder
        
        Args:
            file_path: Path to the file/folder
            is_expanded: Whether folder is expanded (for folders only)
            
        Returns:
            Unicode character/emoji for the icon
        """
        # Check if it's a directory
        if file_path.is_dir():
            return FileIconProvider.FOLDER_OPEN if is_expanded else FileIconProvider.FOLDER_CLOSED
        
        # Check special file names first
        if file_path.name in FileIconProvider.SPECIAL_FILES:
            return FileIconProvider.SPECIAL_FILES[file_path.name]
        
        # Check by extension
        extension = file_path.suffix.lower()
        if extension in FileIconProvider.ICON_MAP:
            return FileIconProvider.ICON_MAP[extension]
        
        # Check by full filename (for files like 'Makefile')
        if file_path.name in FileIconProvider.ICON_MAP:
            return FileIconProvider.ICON_MAP[file_path.name]
        
        # Default file icon
        return FileIconProvider.DEFAULT_FILE
    
    @staticmethod
    def create_icon(text: str, size: int = 16, color: str = None) -> QIcon:
        """
        Create a QIcon from unicode text
        
        Args:
            text: Unicode character/emoji
            size: Icon size in pixels
            color: Optional text color (hex string)
            
        Returns:
            QIcon with the rendered text
        """
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        
        # Set font
        font = QFont()
        font.setPixelSize(int(size * 0.8))  # Slightly smaller than icon size
        painter.setFont(font)
        
        # Set color if specified
        if color:
            painter.setPen(QColor(color))
        
        # Draw text centered
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        painter.end()
        
        return QIcon(pixmap)

