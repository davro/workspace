from PyQt6.QtWidgets import QTabBar, QTabWidget
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtCore import Qt

 
class StyledTabBar(QTabBar):
    """Custom tab bar with active/inactive styling and modified indicators"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDrawBase(False)
        self.setExpanding(False)
        self.modified_tabs = set()  # Track which tabs are modified

        # Apply comprehensive stylesheet
        self.setStyleSheet("""
            QTabBar::tab {
                background-color: #2B2B2B;
                color: #999999;
                border: none;
                border-bottom: 2px solid transparent;
                padding: 8px 24px 8px 16px;
                margin-right: 2px;
                min-width: 80px;
            }

            QTabBar::tab:selected {
                background-color: #2B2B2B;
                color: #4A9EFF;
                font-weight: bold;
                border-bottom: 2px solid #4A9EFF;
            }

            QTabBar::tab:!selected:hover {
                background-color: #3C3F41;
                color: #CCCCCC;
            }

            QTabBar::tab:selected:hover {
                background-color: #2B2B2B;
                color: #4A9EFF;
            }

            QTabBar::close-button {
                subcontrol-position: right;
                margin: 2px;
                width: 14px;
                height: 14px;
                border-radius: 3px;
                background-color: #555555;
            }

            QTabBar::close-button:hover {
                background-color: #E74C3C;
            }
        """)

    def set_tab_modified(self, index, modified):
        """Mark a tab as modified or unmodified"""
        if modified:
            self.modified_tabs.add(index)
        else:
            self.modified_tabs.discard(index)
        self.update()  # Trigger repaint

    def tabRemoved(self, index):
        """Clean up modified tabs tracking when tab is removed"""
        # Shift indices down for tabs after the removed one
        new_modified = set()
        for i in self.modified_tabs:
            if i < index:
                new_modified.add(i)
            elif i > index:
                new_modified.add(i - 1)
        self.modified_tabs = new_modified
        super().tabRemoved(index)

    def paintEvent(self, event):
        """Custom paint to show modified indicator"""
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw modified indicators
        for index in range(self.count()):
            if index in self.modified_tabs:
                rect = self.tabRect(index)

                # Draw a filled circle (dot) on the left side of the tab
                center_x = rect.left() + 10
                center_y = rect.center().y()
                radius = 4

                # Choose color based on whether tab is selected
                if index == self.currentIndex():
                    painter.setBrush(QColor("#4A9EFF"))  # Blue for active modified tab
                    painter.setPen(QColor("#4A9EFF"))
                else:
                    painter.setBrush(QColor("#FF6B6B"))  # Red for inactive modified tab
                    painter.setPen(QColor("#FF6B6B"))

                painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)

        painter.end()

    def tabMoved(self, from_index, to_index):
        if from_index in self.modified_tabs:
            self.modified_tabs.remove(from_index)
            # Adjust for insertion point
            new_index = to_index
            if to_index > from_index:
                new_index -= 1
            self.modified_tabs.add(new_index)
            self.update()
    
        super().tabMoved(from_index, to_index)


class StyledTabWidget(QTabWidget):
    """Custom tab widget with styled tab bar"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Replace default tab bar with custom one
        self.custom_tab_bar = StyledTabBar(self)
        self.setTabBar(self.custom_tab_bar)

        # Style the tab widget itself
        self.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #2B2B2B;
            }

            QTabWidget::tab-bar {
                alignment: left;
            }
        """)

        # Enable tooltips
        self.setMouseTracking(True)
        self.tabBar().setMouseTracking(True)

    def set_tab_modified(self, index, modified):
        """Mark a tab as modified"""
        self.custom_tab_bar.set_tab_modified(index, modified)



