"""
MCP Plugin for Workspace IDE

Connects the IDE to MCP (Model Context Protocol) servers:
  * Servers are defined in  ~/.config/workspace-ide/plugins/mcp/servers.json
    (same format as Claude Desktop's "mcpServers").
  * A sidebar panel shows servers, status and the tools each one offers, and
    lets you test-call a tool by hand.
  * Exposes the manager as `api.mcp`, which the Ollama plugin uses to give
    local models tool access (every call needs your approval).

Requires:  pip install mcp
"""

import json
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTreeWidget,
    QTreeWidgetItem, QTextEdit, QDialog, QDialogButtonBox, QMessageBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor

from McpPlugin.McpClientManager import McpClientManager, McpError

STATUS_STYLE = {
    "connected":    ("●", "#98C379"),
    "connecting":   ("◌", "#E5C07B"),
    "error":        ("✗", "#E74C3C"),
    "disconnected": ("○", "#888888"),
}

BUTTON_CSS = """
    QPushButton { padding: 4px 8px; border: 1px solid #3C3F41; border-radius: 3px;
                  background-color: #2B2B2B; }
    QPushButton:hover { background-color: #3C3F41; border-color: #4A9EFF; }
    QPushButton:disabled { color: #666; }
"""


# ============================================================================
# Plugin
# ============================================================================

class McpPlugin:
    PLUGIN_NAME = "MCP"
    PLUGIN_VERSION = "1.0.0"
    PLUGIN_DESCRIPTION = "Connect to MCP servers and give AI models access to their tools"
    PLUGIN_RUN_ON_STARTUP = True
    PLUGIN_HAS_UI = True
    PLUGIN_ICON = "🔌"

    def __init__(self, api):
        self.api = api
        self.manager = None
        self.widget = None
        self.chat_panel = None
        self.initialized = False
        print(f"[{self.PLUGIN_NAME}] Instance created")

    def initialize(self):
        if self.initialized:
            return

        try:
            config_dir = self.api.app_dirs.plugin_dir("mcp")
        except Exception:
            config_dir = Path.home() / ".config" / "workspace-ide" / "plugins" / "mcp"
        config_path = Path(config_dir) / "servers.json"

        self.manager = McpClientManager(config_path)
        self.manager.start()
        self.api.mcp = self.manager        # other plugins look this up lazily

        self.widget = self.get_widget(self.api.ide)
        self.api.add_to_right_sidebar(self.widget, "MCP", "🔌")

        # Agent chat: optional, needs the Ollama plugin for its engine
        try:
            from McpPlugin.McpAgentChat import McpChatPanel
            self.chat_panel = McpChatPanel(self, self.api.ide)
            self.api.add_to_right_sidebar(self.chat_panel, "Agent", "💬")
        except ImportError as e:
            print(f"[{self.PLUGIN_NAME}] Agent chat disabled (needs the Ollama plugin): {e}")

        self.api.register_hook('on_workspace_closed', self.shutdown, plugin_id='mcp_plugin')

        error = self.manager.reload()      # connects every enabled server
        if error:
            print(f"[{self.PLUGIN_NAME}] Config problem: {error}")

        self.initialized = True
        print(f"[{self.PLUGIN_NAME}] Initialized (config: {config_path})")

    def get_widget(self, parent=None):
        return McpPanel(self, parent)

    def shutdown(self, *args, **kwargs):
        """Stop all servers (called when the IDE closes)."""
        if self.manager:
            self.manager.shutdown()

    def cleanup(self):
        print(f"[{self.PLUGIN_NAME}] Cleaning up...")
        if self.chat_panel:
            self.chat_panel.cleanup()
        self.shutdown()
        if self.api:
            self.api.unregister_all_plugin_hooks('mcp_plugin')
            if getattr(self.api, "mcp", None) is self.manager:
                self.api.mcp = None
        self.initialized = False


# ============================================================================
# Panel
# ============================================================================

class McpPanel(QWidget):
    changed = pyqtSignal()     # emitted from the MCP thread, handled on the GUI thread

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self.manager = plugin.manager

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        header = QLabel(f"{plugin.PLUGIN_ICON} MCP Servers")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #4A9EFF; padding: 5px;")
        layout.addWidget(header)

        bar = QHBoxLayout()
        self.reload_btn = QPushButton("⟳ Reload")
        self.reload_btn.setToolTip("Re-read servers.json and (re)connect servers")
        self.edit_btn = QPushButton("✎ Edit config")
        self.edit_btn.setToolTip("Open servers.json in the editor")
        self.example_btn = QPushButton("＋ Example")
        self.example_btn.setToolTip("Add an example filesystem server (needs Node.js / npx)")
        for b in (self.reload_btn, self.edit_btn, self.example_btn):
            b.setStyleSheet(BUTTON_CSS)
            bar.addWidget(b)
        bar.addStretch()
        layout.addLayout(bar)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setStyleSheet("QTreeWidget { background:#1E1E1E; color:#CCC; border:1px solid #3C3F41; }")
        layout.addWidget(self.tree, 3)

        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setStyleSheet("background:#1E1E1E; color:#A9B7C6; border:1px solid #3C3F41;"
                                   "font-family:'Courier New',monospace; font-size:10pt;")
        layout.addWidget(self.details, 2)

        actions = QHBoxLayout()
        self.toggle_btn = QPushButton("Connect")
        self.test_btn = QPushButton("▶ Test tool…")
        for b in (self.toggle_btn, self.test_btn):
            b.setStyleSheet(BUTTON_CSS)
            actions.addWidget(b)
        actions.addStretch()
        layout.addLayout(actions)

        self.status = QLabel("")
        self.status.setStyleSheet("color:#888; font-size:9pt;")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.reload_btn.clicked.connect(self.on_reload)
        self.edit_btn.clicked.connect(self.on_edit)
        self.example_btn.clicked.connect(self.on_example)
        self.toggle_btn.clicked.connect(self.on_toggle)
        self.test_btn.clicked.connect(self.on_test)
        self.tree.currentItemChanged.connect(self.on_selection)
        self.changed.connect(self.refresh)

        self._listener = self.changed.emit
        self.manager.add_listener(self._listener)
        self.destroyed.connect(lambda *_: self.manager.remove_listener(self._listener))

        self.refresh()

    # ------------------------------------------------------------------ tree

    def refresh(self):
        selected = self._selected_key()
        self.tree.blockSignals(True)
        self.tree.clear()
        servers = self.manager.servers()

        for srv in servers:
            icon, color = STATUS_STYLE.get(srv["status"], STATUS_STYLE["disconnected"])
            count = len(srv["tools"])
            hidden = f", {srv['hidden']} hidden" if srv.get("hidden") else ""
            suffix = f" — {count} tool{'s' if count != 1 else ''}{hidden}" if srv["status"] == "connected" else \
                     f" — {srv['status']}"
            item = QTreeWidgetItem([f"{icon} {srv['name']}{suffix}"])
            item.setForeground(0, QColor(color))
            item.setData(0, Qt.ItemDataRole.UserRole, ("server", srv["name"]))
            self.tree.addTopLevelItem(item)
            for tool in srv["tools"]:
                child = QTreeWidgetItem([tool["name"]])
                child.setData(0, Qt.ItemDataRole.UserRole, ("tool", srv["name"], tool["name"]))
                item.addChild(child)
            item.setExpanded(srv["status"] == "connected")

        self.tree.blockSignals(False)
        self._reselect(selected)

        if not servers:
            self.details.setPlainText(
                "No MCP servers configured.\n\n"
                "Click “＋ Example” to add a filesystem server, or “✎ Edit config” to add your own:\n\n"
                '{\n  "mcpServers": {\n    "name": {\n      "command": "npx",\n'
                '      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/some/dir"]\n'
                "    }\n  }\n}")
        self.on_selection()

    def _selected_key(self):
        item = self.tree.currentItem()
        return item.data(0, Qt.ItemDataRole.UserRole) if item else None

    def _reselect(self, key):
        if not key:
            return
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            if top.data(0, Qt.ItemDataRole.UserRole) == key:
                self.tree.setCurrentItem(top)
                return
            for j in range(top.childCount()):
                if top.child(j).data(0, Qt.ItemDataRole.UserRole) == key:
                    self.tree.setCurrentItem(top.child(j))
                    return

    def _find_server(self, name):
        return next((s for s in self.manager.servers() if s["name"] == name), None)

    def on_selection(self, *_):
        key = self._selected_key()
        self.test_btn.setEnabled(bool(key and key[0] == "tool"))
        self.toggle_btn.setEnabled(bool(key))
        if not key:
            self.toggle_btn.setText("Connect")
            return

        srv = self._find_server(key[1])
        if not srv:
            return
        active = srv["status"] in ("connected", "connecting")
        self.toggle_btn.setText("Disconnect" if active else "Connect")

        if key[0] == "server":
            lines = [f"Server:  {srv['name']}", f"Status:  {srv['status']}", f"Command: {srv['command']}"]
            if srv["error"]:
                lines += ["", srv["error"]]
            self.details.setPlainText("\n".join(lines))
        else:
            tool = next((t for t in srv["tools"] if t["name"] == key[2]), None)
            if tool:
                self.details.setPlainText(
                    f"{tool['name']}\n\n{tool['description'] or '(no description)'}\n\n"
                    f"Input schema:\n{json.dumps(tool['schema'], indent=2)}")

    # ------------------------------------------------------------------ actions

    def on_reload(self):
        error = self.manager.reload()
        self.status.setText(f"⚠ {error}" if error else "Reloaded config")
        self.status.setStyleSheet(f"color:{'#E74C3C' if error else '#888'}; font-size:9pt;")

    def on_edit(self):
        self.manager.ensure_config_file()
        self.plugin.api.open_file(str(self.manager.config_path))
        self.status.setText("Edit the file, save it, then click Reload.")

    def on_example(self):
        try:
            workspace = str(Path(self.plugin.api.get_workspace_path()).resolve())
            self.manager.add_server_to_config("filesystem", {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", workspace],
            })
        except McpError as e:
            QMessageBox.warning(self, "MCP", str(e))
            return
        self.on_reload()

    def on_toggle(self):
        key = self._selected_key()
        if not key:
            return
        srv = self._find_server(key[1])
        if not srv:
            return
        if srv["status"] in ("connected", "connecting"):
            self.manager.disconnect(key[1])
        else:
            self.manager.connect(key[1])

    def on_test(self):
        key = self._selected_key()
        if not key or key[0] != "tool":
            return
        srv = self._find_server(key[1])
        tool = next((t for t in srv["tools"] if t["name"] == key[2]), None) if srv else None
        if tool:
            ToolTestDialog(self.manager, tool, self).exec()


# ============================================================================
# Manual tool test
# ============================================================================

class _CallThread(QThread):
    finished_ok = pyqtSignal(str, bool)
    failed = pyqtSignal(str)

    def __init__(self, manager, qualified, args, parent=None):
        super().__init__(parent)
        self.manager, self.qualified, self.args = manager, qualified, args

    def run(self):
        try:
            text, is_error = self.manager.call_tool(self.qualified, self.args, timeout=120)
            self.finished_ok.emit(text, is_error)
        except Exception as e:
            self.failed.emit(str(e))


class ToolTestDialog(QDialog):
    def __init__(self, manager, tool, parent=None):
        super().__init__(parent)
        self.manager, self.tool = manager, tool
        self.thread_ = None
        self.setWindowTitle(f"Test: {tool['name']}")
        self.setMinimumSize(520, 460)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>{tool['name']}</b> — {tool['description'][:200] or 'no description'}"))
        layout.addWidget(QLabel("Arguments (JSON):"))

        self.args_edit = QTextEdit()
        self.args_edit.setPlainText(json.dumps(self._skeleton(tool["schema"]), indent=2))
        self.args_edit.setMaximumHeight(140)
        layout.addWidget(self.args_edit)

        self.run_btn = QPushButton("▶ Run")
        self.run_btn.clicked.connect(self.run)
        layout.addWidget(self.run_btn)

        layout.addWidget(QLabel("Result:"))
        self.result = QTextEdit()
        self.result.setReadOnly(True)
        layout.addWidget(self.result)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _skeleton(schema):
        """Pre-fill required arguments so the user only edits values."""
        defaults = {"string": "", "integer": 0, "number": 0, "boolean": False,
                    "array": [], "object": {}}
        props = (schema or {}).get("properties", {}) or {}
        required = (schema or {}).get("required", []) or []
        out = {}
        for name in required:
            spec = props.get(name) or {}
            if "default" in spec:
                out[name] = spec["default"]
                continue
            kind = spec.get("type", "string")
            out[name] = defaults.get(kind if isinstance(kind, str) else "string", "")
        return out

    def run(self):
        try:
            args = json.loads(self.args_edit.toPlainText() or "{}")
            if not isinstance(args, dict):
                raise ValueError("arguments must be a JSON object")
        except ValueError as e:
            self.result.setPlainText(f"Invalid JSON: {e}")
            return

        qualified = self.tool.get("qualified")
        self.run_btn.setEnabled(False)
        self.result.setPlainText("Running…")
        self.thread_ = _CallThread(self.manager, qualified, args, self)
        self.thread_.finished_ok.connect(self._on_result)
        self.thread_.failed.connect(lambda msg: self._on_result(f"Error: {msg}", True))
        self.thread_.start()

    def _on_result(self, text, is_error):
        shown = text
        stripped = text.strip()
        if stripped[:1] in ("{", "["):
            try:
                shown = json.dumps(json.loads(stripped), indent=2)
            except ValueError:
                pass
        self.result.setPlainText(("✗ Tool reported an error\n\n" if is_error else "") + shown)
        self.run_btn.setEnabled(True)

    def done(self, code):
        if self.thread_ is not None and self.thread_.isRunning():
            self.thread_.wait(1000)
        super().done(code)