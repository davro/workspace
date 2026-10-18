import json
import urllib.error
import urllib.request

from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor

from .OllamaWorker import OllamaChatWorker, ollama_base_url

NO_MODEL_LABELS = ("No models found", "ollama not available")


class OllamaChatWidget(QWidget):
    """
    Chat panel for Ollama.

    Public surface used by the rest of the plugin (unchanged):
        model_box, refresh_models(), send_text_message(text)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_ide = parent
        # OllamaPluginWidget sets .plugin before building us; gives access to
        # the API (settings + MCP) without changing the plugin file.
        self.plugin = getattr(parent, "plugin", None)

        self.messages = []          # conversation history sent on every request
        self.worker = None
        self._always_allow = set()  # tools the user approved for this session
        self._assistant_open = False
        self._history_len_before = 0

        layout = QVBoxLayout(self)

        # ---- top bar -------------------------------------------------------
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Model:"))

        self.model_box = QComboBox()
        top_bar.addWidget(self.model_box)

        self.refresh_btn = QPushButton("Refresh Models")
        self.refresh_btn.clicked.connect(self.refresh_models)
        top_bar.addWidget(self.refresh_btn)

        self.ps_btn = QPushButton("Show Loaded Models")
        self.ps_btn.clicked.connect(self.show_ollama_ps)
        top_bar.addWidget(self.ps_btn)

        self.new_chat_btn = QPushButton("New Chat")
        self.new_chat_btn.setToolTip("Clear the conversation (Ollama forgets earlier messages)")
        self.new_chat_btn.clicked.connect(self.new_chat)
        top_bar.addWidget(self.new_chat_btn)

        top_bar.addStretch()

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #999;")
        top_bar.addWidget(self.status_label)
        layout.addLayout(top_bar)

        # ---- tools row -----------------------------------------------------
        tools_row = QHBoxLayout()
        self.tools_check = QCheckBox("🔧 Use MCP tools")
        self.tools_check.setChecked(True)
        self.tools_check.setToolTip("Let the model call tools from connected MCP servers "
                                    "(you approve every call). Needs a tool-capable model.")
        tools_row.addWidget(self.tools_check)
        tools_row.addStretch()
        layout.addLayout(tools_row)

        # ---- chat view -----------------------------------------------------
        self.chat = QTextEdit()
        self.chat.setReadOnly(True)
        self.chat.setStyleSheet("background:#1E1E1E;color:#CCC;")
        layout.addWidget(self.chat)

        # ---- input row -----------------------------------------------------
        bottom = QHBoxLayout()
        self.input = QLineEdit()
        self.input.returnPressed.connect(self.send_message)
        bottom.addWidget(self.input)
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.send_message)
        bottom.addWidget(self.send_btn)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop)
        bottom.addWidget(self.stop_btn)
        layout.addLayout(bottom)

        self.refresh_models()

        # MCP may load after us (plugin load order), so poll its tool count.
        self._tools_timer = QTimer(self)
        self._tools_timer.timeout.connect(self._refresh_tools_label)
        self._tools_timer.start(2000)
        self._refresh_tools_label()

        app = QApplication.instance()
        if app:
            app.aboutToQuit.connect(self.cleanup)

    # ===================================================================
    # Settings / MCP access
    # ===================================================================

    def get_timeout(self):
        plugin = self.plugin
        if plugin is not None and hasattr(plugin, "get_ollama_timeout"):
            try:
                return int(plugin.get_ollama_timeout())
            except Exception:
                pass
        return 240

    def _mcp(self):
        api = getattr(self.plugin, "api", None)
        return getattr(api, "mcp", None)

    def _refresh_tools_label(self):
        mcp = self._mcp()
        count = mcp.tool_count() if mcp else 0
        if mcp is None:
            self.tools_check.setText("🔧 Use MCP tools (MCP plugin not loaded)")
            self.tools_check.setEnabled(False)
        else:
            self.tools_check.setText(f"🔧 Use MCP tools ({count} available)")
            self.tools_check.setEnabled(count > 0)

    # ===================================================================
    # Models
    # ===================================================================

    def _get_json(self, path, timeout=3):
        with urllib.request.urlopen(ollama_base_url() + path, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def refresh_models(self):
        self.model_box.clear()
        try:
            data = self._get_json("/api/tags")
            for model in data.get("models", []):
                self.model_box.addItem(model.get("name", "?"))
            if self.model_box.count() == 0:
                self.model_box.addItem(NO_MODEL_LABELS[0])
        except Exception:
            self.model_box.addItem(NO_MODEL_LABELS[1])

    def show_ollama_ps(self):
        try:
            models = self._get_json("/api/ps").get("models", [])
        except Exception as e:
            self._write(f"\nError checking loaded models: {e}\n", color="#E74C3C")
            return
        if not models:
            self._write("\n=== No models currently loaded ===\n", color="#999999")
            return
        self._write("\n=== Currently Loaded Models ===\n", color="#999999")
        for m in models:
            size_gb = m.get("size", 0) / 1e9
            self._write(f"{m.get('name', '?')}  ({size_gb:.1f} GB)  until {m.get('expires_at', '?')}\n",
                        color="#999999")
        self._write("================================\n", color="#999999")

    # ===================================================================
    # Chat view helpers (plain text only - model output is never parsed as HTML)
    # ===================================================================

    def _write(self, text, color=None, bold=False, italic=False):
        fmt = QTextCharFormat()
        if color:
            fmt.setForeground(QColor(color))
        if bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        fmt.setFontItalic(italic)
        cursor = self.chat.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text, fmt)
        self.chat.setTextCursor(cursor)
        self.chat.ensureCursorVisible()

    def _open_assistant_block(self):
        if not self._assistant_open:
            self._write("Ollama: ", color="#4A9EFF", bold=True)
            self._assistant_open = True

    # ===================================================================
    # Sending
    # ===================================================================

    def new_chat(self):
        if self.worker is not None:
            return
        self.messages.clear()
        self._always_allow.clear()
        self.chat.clear()
        self.status_label.setText("")

    def send_message(self):
        text = self.input.text().strip()
        if not text:
            return
        if self._start_request(text):
            self.input.clear()

    def send_text_message(self, text):
        """Used by the plugin (send file/selection with context)."""
        if text.strip():
            self._start_request(text)

    def _start_request(self, text):
        if self.worker is not None:
            self.status_label.setText("⏳ Busy - wait or press Stop")
            return False

        model = self.model_box.currentText()
        if model in NO_MODEL_LABELS:
            self._write("Error: No valid Ollama model selected\n", color="#E74C3C")
            return False

        self._history_len_before = len(self.messages)
        self.messages.append({"role": "user", "content": text})
        self._write("You: ", color="#98C379", bold=True)
        self._write(text + "\n\n")

        mcp = self._mcp()
        tools = None
        if mcp is not None and self.tools_check.isChecked() and mcp.tool_count() > 0:
            tools = mcp.ollama_tools()

        self._assistant_open = False
        self.worker = OllamaChatWorker(
            model, self.messages, tools=tools, mcp=mcp,
            timeout=self.get_timeout(), parent=self,
        )
        self.worker.token.connect(self._on_token)
        self.worker.tool_call.connect(self._on_tool_call)
        self.worker.tool_result.connect(self._on_tool_result)
        self.worker.approval_needed.connect(self._on_approval_needed)
        self.worker.notice.connect(self._on_notice)
        self.worker.done.connect(self._on_done)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(self._on_thread_finished)

        self._set_busy(True)
        self.worker.start()
        return True

    def stop(self):
        if self.worker is not None:
            self.worker.cancel()
            self.status_label.setText("Stopping...")

    def _set_busy(self, busy):
        self.send_btn.setEnabled(not busy)
        self.stop_btn.setEnabled(busy)
        self.new_chat_btn.setEnabled(not busy)
        self.status_label.setText("⏳ Thinking..." if busy else "✓ Ready")

    # ===================================================================
    # Worker signals
    # ===================================================================

    def _on_token(self, piece):
        self._open_assistant_block()
        self._write(piece)

    def _on_tool_call(self, name, args_json):
        if self._assistant_open:
            self._write("\n")
        self._write(f"🔧 {name}({args_json})\n", color="#E5C07B", italic=True)
        self._assistant_open = False
        self.status_label.setText("🔧 Running tool...")

    def _on_tool_result(self, name, preview, is_error):
        color = "#E74C3C" if is_error else "#7F8C8D"
        prefix = "✗" if is_error else "↳"
        self._write(f"{prefix} {preview}\n\n", color=color, italic=True)
        self.status_label.setText("⏳ Thinking...")

    def _on_notice(self, text):
        self._write(f"ℹ {text}\n", color="#E5C07B", italic=True)

    def _on_approval_needed(self, name, args_json, holder):
        """Runs on the GUI thread; the worker thread waits on holder['event']."""
        if name in self._always_allow:
            holder["allow"] = True
            holder["event"].set()
            return

        shown = args_json if len(args_json) <= 600 else args_json[:600] + "\n..."
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Allow tool call?")
        box.setText(f"The model wants to run the MCP tool:\n\n    {name}")
        box.setInformativeText("Arguments:\n" + shown)
        allow = box.addButton("Allow once", QMessageBox.ButtonRole.AcceptRole)
        always = box.addButton("Always allow (this session)", QMessageBox.ButtonRole.AcceptRole)
        deny = box.addButton("Deny", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(deny)
        box.exec()

        clicked = box.clickedButton()
        if clicked is always:
            self._always_allow.add(name)
        holder["allow"] = clicked in (allow, always)
        holder["event"].set()

    def _on_done(self, new_messages):
        self.messages.extend(new_messages)
        self._write("\n\n")
        self._set_busy(False)

    def _on_failed(self, error):
        # Drop the user message that never got an answer so history stays valid.
        del self.messages[self._history_len_before:]
        self._write(f"\nError: {error}\n\n", color="#E74C3C")
        self._set_busy(False)
        self.status_label.setText("✗ Error")

    def _on_thread_finished(self):
        worker, self.worker = self.worker, None
        if worker is not None:
            worker.deleteLater()

    # ===================================================================
    # Shutdown
    # ===================================================================

    def cleanup(self):
        """Stop any running request so Qt never destroys a live QThread."""
        worker = self.worker
        if worker is not None:
            worker.cancel()
            worker.wait(3000)
