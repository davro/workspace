"""
SQLite Browser Plugin for Workspace IDE
Save as: workspace/plugins/sqlite_browser.py
"""

import sqlite3
import json
import csv
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

PLUGIN_NAME = "SQLite Browser"
PLUGIN_VERSION = "1.0.0"

def get_widget(parent=None):
    return SQLiteBrowserWidget(parent)

class SQLiteBrowserWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_db = None
        self.current_table = None
        self.current_page = 0
        self.page_size = 50
        self.total_rows = 0
        self.load_active_projects()
        self.init_ui()
        self.scan_databases()
    
    def load_active_projects(self):
        config_file = Path.home() / "workspace" / ".workspace_ide_config.json"
        try:
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    self.active_projects = config.get('active_projects', [])
            else:
                self.active_projects = []
        except:
            self.active_projects = []
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Compact header
        header = QWidget()
        header.setStyleSheet("background: #2B2B2B; border-bottom: 2px solid #4A9EFF; padding: 5px;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(8, 5, 8, 5)
        title = QLabel("🗄️ SQLite Browser")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #4A9EFF;")
        h_layout.addWidget(title)
        h_layout.addStretch()
        refresh_btn = QPushButton("🔄 Scan")
        refresh_btn.clicked.connect(self.scan_databases)
        refresh_btn.setStyleSheet("background: #3498DB; color: white; border: none; padding: 4px 10px; border-radius: 3px; font-weight: bold;")
        h_layout.addWidget(refresh_btn)
        layout.addWidget(header)
        
        # Splitter - takes full available height
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Left: Tree
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(2)
        
        self.db_tree = QTreeWidget()
        self.db_tree.setHeaderLabel("Databases")
        self.db_tree.setStyleSheet("QTreeWidget { background: #1E1E1E; color: #CCC; border: 1px solid #555; } QTreeWidget::item:selected { background: #4A9EFF; color: white; }")
        self.db_tree.itemClicked.connect(self.on_tree_clicked)
        left_layout.addWidget(self.db_tree)
        
        self.db_info = QLabel("No database selected")
        self.db_info.setStyleSheet("color: #999; font-size: 9px; padding: 3px; background: #2B2B2B;")
        self.db_info.setWordWrap(True)
        self.db_info.setMaximumHeight(60)
        left_layout.addWidget(self.db_info)
        
        splitter.addWidget(left)
        
        # Right: Tabs - expand fully
        self.tabs = QTabWidget()
        self.tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.tabs.setStyleSheet("QTabWidget::pane { border: 1px solid #555; background: #2B2B2B; } QTabBar::tab { background: #3C3F41; color: #CCC; padding: 8px 16px; } QTabBar::tab:selected { background: #4A9EFF; color: white; }")
        
        # Data tab
        data_widget = QWidget()
        data_layout = QVBoxLayout(data_widget)
        
        controls = QHBoxLayout()
        self.table_combo = QComboBox()
        self.table_combo.currentTextChanged.connect(self.on_table_changed)
        self.table_combo.setStyleSheet("background: #1E1E1E; color: #CCC; border: 1px solid #555; padding: 5px;")
        controls.addWidget(QLabel("Table:"))
        controls.addWidget(self.table_combo)
        
        # Page size selector
        controls.addWidget(QLabel("  Rows:"))
        self.page_size_combo = QComboBox()
        self.page_size_combo.addItems(["25", "50", "75", "100", "250", "500"])
        self.page_size_combo.setCurrentText("50")
        self.page_size_combo.currentTextChanged.connect(self.on_page_size_changed)
        self.page_size_combo.setStyleSheet("background: #1E1E1E; color: #CCC; border: 1px solid #555; padding: 5px; min-width: 60px;")
        controls.addWidget(self.page_size_combo)
        
        controls.addStretch()
        
        for text, color, func in [("➕ Add", "#27AE60", self.add_row), ("✏️ Edit", "#3498DB", self.edit_row), ("🗑️ Delete", "#E74C3C", self.delete_row), ("🔄", "#9B59B6", self.refresh_data), ("💾 CSV", "#E67E22", self.export_csv)]:
            btn = QPushButton(text)
            btn.clicked.connect(func)
            btn.setStyleSheet(f"background: {color}; color: white; border: none; padding: 6px 12px; border-radius: 3px; font-weight: bold;")
            controls.addWidget(btn)
        
        data_layout.addLayout(controls)
        
        self.data_table = QTableWidget()
        self.data_table.setStyleSheet("QTableWidget { background: #1E1E1E; color: #CCC; gridline-color: #555; border: 1px solid #555; } QHeaderView::section { background: #3C3F41; color: #4A9EFF; padding: 5px; border: 1px solid #555; font-weight: bold; }")
        self.data_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.data_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        data_layout.addWidget(self.data_table)
        
        # Pagination controls
        pagination = QHBoxLayout()
        
        self.first_page_btn = QPushButton("⏮️ First")
        self.first_page_btn.clicked.connect(self.first_page)
        self.first_page_btn.setStyleSheet("background: #3C3F41; color: #CCC; border: none; padding: 4px 8px; border-radius: 3px;")
        pagination.addWidget(self.first_page_btn)
        
        self.prev_page_btn = QPushButton("◀️ Prev")
        self.prev_page_btn.clicked.connect(self.prev_page)
        self.prev_page_btn.setStyleSheet("background: #3C3F41; color: #CCC; border: none; padding: 4px 8px; border-radius: 3px;")
        pagination.addWidget(self.prev_page_btn)
        
        self.page_info_label = QLabel("Page 0 of 0")
        self.page_info_label.setStyleSheet("color: #4A9EFF; font-weight: bold; padding: 0 10px;")
        self.page_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pagination.addWidget(self.page_info_label)
        
        self.next_page_btn = QPushButton("Next ▶️")
        self.next_page_btn.clicked.connect(self.next_page)
        self.next_page_btn.setStyleSheet("background: #3C3F41; color: #CCC; border: none; padding: 4px 8px; border-radius: 3px;")
        pagination.addWidget(self.next_page_btn)
        
        self.last_page_btn = QPushButton("Last ⏭️")
        self.last_page_btn.clicked.connect(self.last_page)
        self.last_page_btn.setStyleSheet("background: #3C3F41; color: #CCC; border: none; padding: 4px 8px; border-radius: 3px;")
        pagination.addWidget(self.last_page_btn)
        
        pagination.addStretch()
        
        self.row_count = QLabel("0 rows")
        self.row_count.setStyleSheet("color: #999; font-size: 10px;")
        pagination.addWidget(self.row_count)
        
        data_layout.addLayout(pagination)
        
        self.tabs.addTab(data_widget, "📊 Data")
        
        # Query tab
        query_widget = QWidget()
        query_layout = QVBoxLayout(query_widget)
        
        self.query_input = QTextEdit()
        self.query_input.setPlaceholderText("Enter SQL query...\nSELECT * FROM table_name;")
        self.query_input.setStyleSheet("background: #1E1E1E; color: #CCC; border: 1px solid #555; font-family: monospace;")
        self.query_input.setMaximumHeight(120)
        query_layout.addWidget(self.query_input)
        
        q_controls = QHBoxLayout()
        exec_btn = QPushButton("▶️ Execute")
        exec_btn.clicked.connect(self.execute_query)
        exec_btn.setStyleSheet("background: #27AE60; color: white; border: none; padding: 6px 12px; border-radius: 3px; font-weight: bold;")
        q_controls.addWidget(exec_btn)
        
        clear_btn = QPushButton("🗑️ Clear")
        clear_btn.clicked.connect(self.query_input.clear)
        clear_btn.setStyleSheet("background: #E74C3C; color: white; border: none; padding: 6px 12px; border-radius: 3px; font-weight: bold;")
        q_controls.addWidget(clear_btn)
        q_controls.addStretch()
        query_layout.addLayout(q_controls)
        
        self.query_results = QTableWidget()
        self.query_results.setStyleSheet("QTableWidget { background: #1E1E1E; color: #CCC; gridline-color: #555; border: 1px solid #555; } QHeaderView::section { background: #3C3F41; color: #4A9EFF; padding: 5px; border: 1px solid #555; font-weight: bold; }")
        query_layout.addWidget(self.query_results)
        
        self.query_status = QLabel("")
        self.query_status.setStyleSheet("color: #999; font-size: 10px;")
        query_layout.addWidget(self.query_status)
        
        self.tabs.addTab(query_widget, "⚡ Query")
        
        # Structure tab
        struct_widget = QWidget()
        struct_layout = QVBoxLayout(struct_widget)
        self.structure_text = QTextEdit()
        self.structure_text.setReadOnly(True)
        self.structure_text.setStyleSheet("background: #1E1E1E; color: #CCC; border: 1px solid #555; font-family: monospace;")
        struct_layout.addWidget(self.structure_text)
        self.tabs.addTab(struct_widget, "🔧 Structure")
        
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        
        layout.addWidget(splitter, 1)  # stretch factor 1 = takes all available space
        
        # Compact status bar
        self.status = QLabel("Ready")
        self.status.setStyleSheet("color: #4A9EFF; padding: 3px; background: #1E1E1E; border-radius: 2px; font-size: 9px;")
        self.status.setMaximumHeight(22)
        layout.addWidget(self.status)
    
    def scan_databases(self):
        self.db_tree.clear()
        if not self.active_projects:
            self.update_status("No active projects")
            return
        
        db_count = 0
        for project_path in self.active_projects:
            project = Path(project_path)
            if not project.exists():
                continue
            
            project_item = QTreeWidgetItem(self.db_tree)
            project_item.setText(0, f"📁 {project.name}")
            project_item.setData(0, Qt.ItemDataRole.UserRole, {'type': 'project'})
            
            for ext in ['*.db', '*.sqlite', '*.sqlite3']:
                for db_file in project.rglob(ext):
                    if self.is_valid_sqlite(db_file):
                        db_item = QTreeWidgetItem(project_item)
                        db_item.setText(0, f"🗄️ {db_file.name}")
                        db_item.setData(0, Qt.ItemDataRole.UserRole, {'type': 'database', 'path': str(db_file)})
                        db_count += 1
        
        self.db_tree.expandAll()
        self.update_status(f"Found {db_count} database(s)")
    
    def is_valid_sqlite(self, path):
        try:
            with open(path, 'rb') as f:
                return f.read(16)[:16] == b'SQLite format 3\x00'
        except:
            return False
    
    def on_tree_clicked(self, item, column):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data and data['type'] == 'database':
            self.load_database(Path(data['path']))
    
    def load_database(self, db_path):
        try:
            if self.current_db:
                self.current_db.close()
            
            self.current_db = sqlite3.connect(str(db_path))
            self.current_db.row_factory = sqlite3.Row
            
            cursor = self.current_db.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]
            
            self.table_combo.clear()
            self.table_combo.addItems(tables)
            
            size = self.format_size(db_path.stat().st_size)
            modified = datetime.fromtimestamp(db_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
            
            self.db_info.setText(f"📊 {db_path.name}\n📏 {size}\n📅 {modified}\n📋 {len(tables)} tables")
            self.update_status(f"Loaded: {db_path.name}")
            
            if tables:
                self.current_page = 0
                self.load_table_data(tables[0])
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load:\n{e}")
    
    def on_table_changed(self, table_name):
        """Handle table selection change"""
        self.current_page = 0
        self.load_table_data(table_name)
    
    def on_page_size_changed(self, size_text):
        """Handle page size change"""
        self.page_size = int(size_text)
        self.current_page = 0
        if self.current_table:
            self.load_table_data(self.current_table)
    
    def refresh_data(self):
        """Refresh current table data"""
        if self.current_table:
            self.load_table_data(self.current_table)
    
    def first_page(self):
        """Go to first page"""
        self.current_page = 0
        if self.current_table:
            self.load_table_data(self.current_table)
    
    def prev_page(self):
        """Go to previous page"""
        if self.current_page > 0:
            self.current_page -= 1
            self.load_table_data(self.current_table)
    
    def next_page(self):
        """Go to next page"""
        total_pages = (self.total_rows + self.page_size - 1) // self.page_size
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.load_table_data(self.current_table)
    
    def last_page(self):
        """Go to last page"""
        total_pages = (self.total_rows + self.page_size - 1) // self.page_size
        self.current_page = max(0, total_pages - 1)
        if self.current_table:
            self.load_table_data(self.current_table)
    
    def update_pagination_buttons(self):
        """Update pagination button states"""
        total_pages = max(1, (self.total_rows + self.page_size - 1) // self.page_size)
        
        self.first_page_btn.setEnabled(self.current_page > 0)
        self.prev_page_btn.setEnabled(self.current_page > 0)
        self.next_page_btn.setEnabled(self.current_page < total_pages - 1)
        self.last_page_btn.setEnabled(self.current_page < total_pages - 1)
        
        self.page_info_label.setText(f"Page {self.current_page + 1} of {total_pages}")
    
    def load_table_data(self, table_name):
        """Load table data with pagination"""
        if not self.current_db or not table_name:
            return
        
        try:
            self.current_table = table_name
            cursor = self.current_db.cursor()
            
            # Get total row count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            self.total_rows = cursor.fetchone()[0]
            
            # Get paginated data
            offset = self.current_page * self.page_size
            cursor.execute(f"SELECT * FROM {table_name} LIMIT {self.page_size} OFFSET {offset}")
            rows = cursor.fetchall()
            
            if rows:
                columns = list(rows[0].keys())
                self.data_table.setColumnCount(len(columns))
                self.data_table.setHorizontalHeaderLabels(columns)
                self.data_table.setRowCount(len(rows))
                
                for r_idx, row in enumerate(rows):
                    for c_idx, col in enumerate(columns):
                        val = row[col]
                        item = QTableWidgetItem(str(val) if val is not None else "NULL")
                        if val is None:
                            item.setForeground(QColor("#999"))
                        self.data_table.setItem(r_idx, c_idx, item)
                
                self.data_table.resizeColumnsToContents()
                
                # Update row count display
                start_row = offset + 1
                end_row = min(offset + len(rows), self.total_rows)
                self.row_count.setText(f"Showing {start_row}-{end_row} of {self.total_rows} rows")
            else:
                self.data_table.setRowCount(0)
                self.data_table.setColumnCount(0)
                self.row_count.setText("0 rows")
            
            # Update pagination
            self.update_pagination_buttons()
            
            self.load_structure(table_name)
            self.update_status(f"Loaded: {table_name} (Page {self.current_page + 1})")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
    
    def load_structure(self, table):
        try:
            cursor = self.current_db.cursor()
            cursor.execute(f"PRAGMA table_info({table})")
            cols = cursor.fetchall()
            
            cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'")
            create_sql = cursor.fetchone()[0]
            
            info = ["=" * 70, f"TABLE: {table}", "=" * 70, "", "COLUMNS:", "-" * 70]
            for col in cols:
                cid, name, type_, notnull, default, pk = col
                info.append(f"  {name:<20} {type_:<15}{' PK' if pk else ''}{' NOT NULL' if notnull else ''}")
            
            info.extend(["", "CREATE:", "-" * 70, create_sql, "", "=" * 70])
            self.structure_text.setPlainText("\n".join(info))
        except:
            pass
    
    def add_row(self):
        if not self.current_db or not self.current_table:
            QMessageBox.warning(self, "No Table", "Select a table first")
            return
        
        dialog = RowDialog(self.current_db, self.current_table, None, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # After adding, go to last page to see the new row
            cursor = self.current_db.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {self.current_table}")
            self.total_rows = cursor.fetchone()[0]
            self.last_page()
    
    def edit_row(self):
        if not self.current_table or not self.data_table.selectedItems():
            QMessageBox.warning(self, "No Selection", "Select a row to edit")
            return
        
        row = self.data_table.currentRow()
        data = {}
        for col in range(self.data_table.columnCount()):
            name = self.data_table.horizontalHeaderItem(col).text()
            val = self.data_table.item(row, col).text()
            data[name] = val if val != "NULL" else None
        
        dialog = RowDialog(self.current_db, self.current_table, data, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_table_data(self.current_table)
    
    def delete_row(self):
        if not self.current_table or not self.data_table.selectedItems():
            QMessageBox.warning(self, "No Selection", "Select a row to delete")
            return
        
        if QMessageBox.question(self, "Confirm", "Delete this row?") != QMessageBox.StandardButton.Yes:
            return
        
        try:
            row = self.data_table.currentRow()
            where_parts = []
            values = []
            
            for col in range(self.data_table.columnCount()):
                name = self.data_table.horizontalHeaderItem(col).text()
                val = self.data_table.item(row, col).text()
                if val == "NULL":
                    where_parts.append(f"{name} IS NULL")
                else:
                    where_parts.append(f"{name} = ?")
                    values.append(val)
            
            cursor = self.current_db.cursor()
            cursor.execute(f"DELETE FROM {self.current_table} WHERE {' AND '.join(where_parts)}", values)
            self.current_db.commit()
            
            # Reload current page (or previous if this was the last item on the page)
            cursor.execute(f"SELECT COUNT(*) FROM {self.current_table}")
            self.total_rows = cursor.fetchone()[0]
            
            total_pages = max(1, (self.total_rows + self.page_size - 1) // self.page_size)
            if self.current_page >= total_pages:
                self.current_page = max(0, total_pages - 1)
            
            self.load_table_data(self.current_table)
            self.update_status("Row deleted")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            self.current_db.rollback()
    
    def execute_query(self):
        if not self.current_db:
            QMessageBox.warning(self, "No Database", "Select a database first")
            return
        
        query = self.query_input.toPlainText().strip()
        if not query:
            return
        
        try:
            cursor = self.current_db.cursor()
            cursor.execute(query)
            
            if query.upper().startswith('SELECT'):
                rows = cursor.fetchall()
                if rows:
                    cols = list(rows[0].keys())
                    self.query_results.setColumnCount(len(cols))
                    self.query_results.setHorizontalHeaderLabels(cols)
                    self.query_results.setRowCount(len(rows))
                    
                    for r, row in enumerate(rows):
                        for c, col in enumerate(cols):
                            self.query_results.setItem(r, c, QTableWidgetItem(str(row[col]) if row[col] is not None else "NULL"))
                    
                    self.query_results.resizeColumnsToContents()
                    self.query_status.setText(f"{len(rows)} row(s)")
                else:
                    self.query_results.setRowCount(0)
                    self.query_status.setText("No rows")
            else:
                self.current_db.commit()
                self.query_results.setRowCount(0)
                self.query_status.setText(f"Success ({cursor.rowcount} affected)")
                if self.current_table:
                    self.load_table_data(self.current_table)
            
            self.update_status("Query executed")
        except Exception as e:
            QMessageBox.critical(self, "Query Error", str(e))
            self.current_db.rollback()
    
    def export_csv(self):
        if not self.current_table:
            QMessageBox.warning(self, "No Table", "Select a table first")
            return
        
        path, _ = QFileDialog.getSaveFileName(self, "Export", f"{self.current_table}.csv", "CSV (*.csv)")
        if not path:
            return
        
        try:
            cursor = self.current_db.cursor()
            cursor.execute(f"SELECT * FROM {self.current_table}")
            rows = cursor.fetchall()
            
            with open(path, 'w', newline='', encoding='utf-8') as f:
                if rows:
                    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                    writer.writeheader()
                    for row in rows:
                        writer.writerow(dict(row))
            
            QMessageBox.information(self, "Success", f"Exported {len(rows)} rows")
            self.update_status(f"Exported {len(rows)} rows")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
    
    def format_size(self, size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
    
    def update_status(self, msg):
        self.status.setText(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


class RowDialog(QDialog):
    def __init__(self, db, table, data, parent=None):
        super().__init__(parent)
        self.db = db
        self.table = table
        self.data = data
        self.is_new = data is None
        self.setWindowTitle("Add Row" if self.is_new else "Edit Row")
        self.setMinimumWidth(500)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        cursor = self.db.cursor()
        cursor.execute(f"PRAGMA table_info({self.table})")
        cols = cursor.fetchall()
        
        form = QFormLayout()
        self.inputs = {}
        
        for col in cols:
            cid, name, type_, notnull, default, pk = col
            label = f"{name}{'(PK)' if pk else ''}{'*' if notnull else ''}"
            
            field = QLineEdit()
            field.setStyleSheet("background: #1E1E1E; color: #CCC; border: 1px solid #555; padding: 5px;")
            
            if self.data and name in self.data:
                field.setText(str(self.data[name]) if self.data[name] is not None else "")
            
            if pk and not self.is_new:
                field.setEnabled(False)
            
            form.addRow(label, field)
            self.inputs[name] = field
        
        layout.addLayout(form)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def save(self):
        try:
            values = {name: field.text().strip() or None for name, field in self.inputs.items()}
            cursor = self.db.cursor()
            
            if self.is_new:
                cols = ', '.join(values.keys())
                placeholders = ', '.join(['?'] * len(values))
                cursor.execute(f"INSERT INTO {self.table} ({cols}) VALUES ({placeholders})", list(values.values()))
            else:
                set_clause = ', '.join([f"{k} = ?" for k in values.keys()])
                where_parts = []
                where_vals = []
                for k, v in self.data.items():
                    if v is None:
                        where_parts.append(f"{k} IS NULL")
                    else:
                        where_parts.append(f"{k} = ?")
                        where_vals.append(v)
                
                cursor.execute(f"UPDATE {self.table} SET {set_clause} WHERE {' AND '.join(where_parts)}", list(values.values()) + where_vals)
            
            self.db.commit()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            self.db.rollback()


def cleanup():
    pass