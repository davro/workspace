
import sys

from PyQt6.QtWidgets import QApplication
from ide.core.Workspace import Workspace

# ============================================================================
# main.py (Entry Point)
# ============================================================================

def main():
    """Application entry point"""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    ide = Workspace()
    ide.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
