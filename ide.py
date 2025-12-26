
import sys

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

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

    # Delay initial layout application
    QTimer.singleShot(50, ide.apply_initial_layout)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
