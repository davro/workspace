# ide/plugins/Codeintelligence/ReferencesPanel.py

"""
ReferencesPanel - "Find All References" results, grouped by file (right sidebar)
"""

from collections import OrderedDict

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QTreeWidget, QTreeWidgetItem
)

KIND_ICONS = {'definition': '📍', 'reference': '➡️', 'comment': '💬', 'string': '🔤'}


class ReferencesPanel(QWidget):
    """Shows references for the last symbol searched; click a row to jump to it."""

    def __init__(self, nav_manager, parent=None):
        super().__init__(parent)
        self.nav_manager = nav_manager
        self.symbol_name = None
        self.references = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        header = QHBoxLayout()
        self.title = QLabel("References")
        self.title.setStyleSheet("font-weight: bold; font-size: 14px;")
        header.addWidget(self.title, 1)
        clear_btn = QPushButton("✖")
        clear_btn.setFixedWidth(30)
        clear_btn.setToolTip("Clear results")
        clear_btn.clicked.connect(self.clear)
        header.addWidget(clear_btn)
        layout.addLayout(header)

        self.include_noise = QCheckBox("Include comments && strings")
        self.include_noise.setChecked(True)
        self.include_noise.stateChanged.connect(lambda _: self._populate())
        layout.addWidget(self.include_noise)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setStyleSheet("""
            QTreeWidget { background-color: #2B2B2B; color: #CCC; border: none; }
            QTreeWidget::item { padding: 3px; }
            QTreeWidget::item:selected { background-color: #4A9EFF; }
            QTreeWidget::item:hover { background-color: #3C3F41; }
        """)
        self.tree.itemClicked.connect(self.on_item_clicked)
        layout.addWidget(self.tree)

        self.status = QLabel("Place the cursor on a symbol and press Ctrl+Shift+R")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self.status)

    def show_results(self, symbol_name: str, references: list):
        self.symbol_name = symbol_name
        self.references = list(references)
        self._populate()

    def _populate(self):
        self.tree.clear()
        if self.symbol_name is None:
            return
        show_noise = self.include_noise.isChecked()
        visible = [r for r in self.references
                   if show_noise or r.kind not in ('comment', 'string')]

        by_file = OrderedDict()
        for ref in visible:
            by_file.setdefault(ref.file_path, []).append(ref)

        for file_path, refs in by_file.items():
            file_item = QTreeWidgetItem([f"📄 {self.nav_manager.display_path(file_path)}  ({len(refs)})"])
            self.tree.addTopLevelItem(file_item)
            for ref in refs:
                icon = KIND_ICONS.get(ref.kind, '➡️')
                context = ref.context if len(ref.context) <= 110 else ref.context[:107] + '...'
                child = QTreeWidgetItem([f"{ref.line}:{ref.column + 1}  {icon} {context}"])
                child.setData(0, Qt.ItemDataRole.UserRole, ref)
                child.setToolTip(0, ref.context)
                file_item.addChild(child)
            file_item.setExpanded(True)

        self.title.setText(f"References: {self.symbol_name}")
        if visible:
            self.status.setText(f"{len(visible)} references in {len(by_file)} files "
                                f"({len(self.references) - len(visible)} hidden)")
        else:
            self.status.setText(f"No references found for '{self.symbol_name}'")

    def on_item_clicked(self, item, column):
        ref = item.data(0, Qt.ItemDataRole.UserRole)
        if ref is not None:
            self.nav_manager.jump_to_location(ref.file_path, ref.line, ref.column,
                                              length=len(self.symbol_name or ''))
        else:
            item.setExpanded(not item.isExpanded())

    def clear(self):
        self.symbol_name = None
        self.references = []
        self.tree.clear()
        self.title.setText("References")
        self.status.setText("Place the cursor on a symbol and press Ctrl+Shift+R")