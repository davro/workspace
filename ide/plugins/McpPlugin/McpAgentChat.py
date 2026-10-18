"""
McpAgentChat - a workspace-aware agent chat with bubble UI.

Engine: OllamaChatWorker (OllamaPlugin/OllamaWorker.py), which talks to Ollama's
/api/chat with *native* tool calling. The model is given the MCP tools through
the API's `tools` field, so there is no JSON-in-the-prompt protocol to parse,
no tool-name guessing, and it can chain several tool calls per question
(list a folder -> read a file -> answer).

Every tool call needs the user's approval.
"""

import json
import urllib.request
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

# Raises ImportError if the Ollama plugin isn't installed; McpPlugin handles that.
from OllamaPlugin.OllamaWorker import OllamaChatWorker, ollama_base_url

# PREFERRED_MODEL = "llama3.1:8b"
# TEMPERATURE = 0.2       # low = quotes tool output faithfully instead of embellishing it

PREFERRED_MODEL = "qwen3.8b"
TEMPERATURE = 0.2       # low = quotes tool output faithfully instead of embellishing it

PANEL_CSS = """
    QScrollArea { border: none; background-color: #1E1E1E; }
    QLineEdit { background-color: #2B2B2B; color: #FFF; border: 1px solid #3C3F41;
                padding: 6px; border-radius: 4px; }
    QPushButton { background-color: #3C3F41; color: #FFF; border: 1px solid #4E5254;
                  padding: 5px 10px; border-radius: 4px; }
    QPushButton:hover { background-color: #4E5254; border-color: #4A9EFF; }
    QPushButton:disabled { color: #777; }
    QComboBox { background-color: #2B2B2B; color: #FFF; border: 1px solid #3C3F41; padding: 3px; }
"""

# role -> (background, header colour, header text)
BUBBLE_STYLES = {
    "user":      ("#2D3748", "#98C379", "You"),
    "assistant": ("#23272E", "#4A9EFF", "Assistant"),
    "tool":      ("#2A2A2A", "#E5C07B", "Tool"),
    "notice":    ("#4A3728", "#E5C07B", "Notice"),
    "error":     ("#4A2828", "#E74C3C", "Error"),
}


class Bubble(QFrame):
    """One chat message. Text is always shown literally (never parsed as HTML)."""

    def __init__(self, role, text="", model=None, parent=None):
        super().__init__(parent)
        background, header_color, header_text = BUBBLE_STYLES[role]
        if model:
            header_text = f"{header_text}({model})"      # e.g. Assistant(qwen3:8b)
        self.role = role
        self.model = model
        self.title = header_text
        self._text = ""

        self.setObjectName("bubble")
        self.setStyleSheet(f"QFrame#bubble {{ background-color: {background}; border-radius: 6px; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        header = QLabel(header_text)
        header.setTextFormat(Qt.TextFormat.PlainText)
        header.setStyleSheet(f"color: {header_color}; font-size: 9pt; font-weight: bold; background: transparent;")
        layout.addWidget(header)

        self.body = QLabel()
        self.body.setTextFormat(Qt.TextFormat.PlainText)
        self.body.setWordWrap(True)
        self.body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        mono = "font-family: 'Courier New', monospace; font-size: 9pt;" if role == "tool" else "font-size: 10pt;"
        self.body.setStyleSheet(f"color: #DCDCDC; background: transparent; {mono}")
        layout.addWidget(self.body)

        self.set_text(text)

    def set_text(self, text):
        self._text = text
        self.body.setText(text)

    def append(self, piece):
        self.set_text(self._text + piece)

    def render_markdown(self):
        """Called once an assistant answer is complete (Qt drops raw HTML in Markdown)."""
        self.body.setTextFormat(Qt.TextFormat.MarkdownText)
        self.body.setText(self._text)


class McpChatPanel(QWidget):
    changed = pyqtSignal()      # MCP state changed (emitted from the MCP thread)

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self.manager = plugin.manager

        self.history = []             # user / assistant / tool messages (no system prompt)
        self.worker = None
        self._pending_user = None
        self._assistant_bubble = None
        self._tool_bubble = None
        self._always_allow = set()
        self._request_model = ""     # model that is answering the current request

        self.setStyleSheet(PANEL_CSS)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # ---- header ---------------------------------------------------------
        top = QHBoxLayout()
        top.addWidget(QLabel("Model:"))
        self.model_box = QComboBox()
        self.model_box.setMinimumWidth(140)
        top.addWidget(self.model_box, 1)
        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setToolTip("Refresh model list")
        self.refresh_btn.setFixedWidth(32)
        self.refresh_btn.clicked.connect(self.refresh_models)
        top.addWidget(self.refresh_btn)
        self.copy_btn = QPushButton("📋")
        self.copy_btn.setToolTip("Copy the whole conversation (including tool calls) to the clipboard")
        self.copy_btn.setFixedWidth(36)
        self.copy_btn.clicked.connect(self.copy_chat)
        top.addWidget(self.copy_btn)
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setToolTip("Start a new conversation")
        self.clear_btn.clicked.connect(self.clear_chat)
        top.addWidget(self.clear_btn)
        layout.addLayout(top)

        options = QHBoxLayout()
        self.show_tools_check = QCheckBox("Show tool calls")
        self.show_tools_check.setChecked(True)
        self.show_tools_check.setToolTip("Hide the tool call / result bubbles. "
                                         "They are still included when you copy the chat.")
        self.show_tools_check.toggled.connect(self._apply_tool_visibility)
        options.addWidget(self.show_tools_check)
        options.addStretch()
        layout.addLayout(options)

        # ---- feed -----------------------------------------------------------
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.feed = QWidget()
        self.feed_layout = QVBoxLayout(self.feed)
        self.feed_layout.addStretch()
        self.scroll.setWidget(self.feed)
        layout.addWidget(self.scroll, 1)
        # Scroll after layout has grown (scrolling right after addWidget uses the old maximum)
        self.scroll.verticalScrollBar().rangeChanged.connect(self._stick_to_bottom)

        # ---- input ----------------------------------------------------------
        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask about your workspace...")
        self.input.returnPressed.connect(self.send_message)
        row.addWidget(self.input)
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.send_message)
        row.addWidget(self.send_btn)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop)
        row.addWidget(self.stop_btn)
        layout.addLayout(row)

        self.status = QLabel("")
        self.status.setStyleSheet("color: #888; font-size: 9pt;")
        layout.addWidget(self.status)

        # ---- wiring ---------------------------------------------------------
        self.changed.connect(self._update_status)
        self._listener = self.changed.emit
        self.manager.add_listener(self._listener)
        self.destroyed.connect(lambda *_: self.manager.remove_listener(self._listener))
        app = QApplication.instance()
        if app:
            app.aboutToQuit.connect(self.cleanup)

        self.refresh_models()
        self._update_status()

    # ------------------------------------------------------------------ helpers

    def _stick_to_bottom(self, _minimum, maximum):
        self.scroll.verticalScrollBar().setValue(maximum)

    def _add_bubble(self, role, text="", model=None):
        bubble = Bubble(role, text, model)
        if role == "tool":
            bubble.setVisible(self.show_tools_check.isChecked())
        self.feed_layout.insertWidget(self.feed_layout.count() - 1, bubble)
        return bubble

    def _bubbles(self):
        for i in range(self.feed_layout.count() - 1):
            widget = self.feed_layout.itemAt(i).widget()
            if isinstance(widget, Bubble):
                yield widget

    def _apply_tool_visibility(self, visible):
        for bubble in self._bubbles():
            if bubble.role == "tool":
                bubble.setVisible(visible)

    def copy_chat(self):
        """Copy the full thread as plain text - handy for sharing or bug reports."""
        bubbles = list(self._bubbles())
        if not bubbles:
            self.status.setText("Nothing to copy yet")
            return
        lines = [
            f"Model: {self.model_box.currentText()}",
            f"Workspace: {self._workspace_path()}",
            f"MCP tools: {self.manager.tool_count()}",
            "-" * 40,
        ]
        for bubble in bubbles:
            lines.append(f"{bubble.title}: {bubble._text}\n")
        QApplication.clipboard().setText("\n".join(lines).rstrip() + "\n")
        self.status.setText(f"✓ Copied {len(bubbles)} messages")
        QTimer.singleShot(2500, self._update_status)

    def _finish_assistant_bubble(self):
        if self._assistant_bubble is not None:
            self._assistant_bubble.render_markdown()
            self._assistant_bubble = None

    def _workspace_path(self):
        try:
            return str(Path(self.plugin.api.get_workspace_path()).resolve())
        except Exception:
            return str(Path.cwd())

    def _system_prompt(self):
        return (
            "You are a coding assistant built into Workspace IDE.\n"
            f"The workspace root is: {self._workspace_path()}\n"
            "Use the provided tools to inspect or change files, always with absolute paths "
            "inside the workspace root. Read before you write. "
            "Never guess a path: if you are unsure where a file or folder is, list or search the "
            "workspace first. Words like 'project' or 'the X folder' in the user's request are not "
            "necessarily literal path components. "
            "Call exactly ONE tool at a time through the tool-calling interface, wait for its "
            "result, then decide the next step. Never describe a plan or write tool calls as text. "
            "Leave optional arguments out unless you actually need them. "
            "If a tool call fails, read the error, fix the arguments and call it again. "
            "Report tool results faithfully: when showing a file, quote exactly what the tool "
            "returned inside a code block, and never add, complete or guess content that was not "
            "returned (a file may be one word or empty - say so). "
            "Otherwise answer concisely in Markdown."
        )

    def _update_status(self):
        count = self.manager.tool_count()
        self.status.setText(f"🔧 {count} MCP tool{'s' if count != 1 else ''} available"
                            if count else "No MCP tools connected - answering without tools")

    # ------------------------------------------------------------------ models

    def refresh_models(self):
        current = self.model_box.currentText()
        self.model_box.clear()
        try:
            with urllib.request.urlopen(ollama_base_url() + "/api/tags", timeout=3) as resp:
                names = [m.get("name", "?") for m in json.loads(resp.read().decode()).get("models", [])]
        except Exception:
            names = []
        if not names:
            self.model_box.addItem("(Ollama not reachable)")
            return
        self.model_box.addItems(names)
        for wanted in (current, PREFERRED_MODEL):
            index = self.model_box.findText(wanted)
            if index >= 0:
                self.model_box.setCurrentIndex(index)
                break

    # ------------------------------------------------------------------ sending

    def send_message(self):
        text = self.input.text().strip()
        if not text or self.worker is not None:
            return
        model = self.model_box.currentText()
        if model.startswith("("):
            self._add_bubble("error", "No Ollama model available. Is `ollama serve` running?")
            return

        self.input.clear()
        self._request_model = model
        self._add_bubble("user", text)
        self._pending_user = {"role": "user", "content": text}

        tools = self.manager.ollama_tools() or None
        messages = [{"role": "system", "content": self._system_prompt()}] + self.history + [self._pending_user]

        self._assistant_bubble = None
        self._tool_bubble = None
        self.worker = OllamaChatWorker(model, messages, tools=tools, mcp=self.manager,
                                       timeout=self._timeout(),
                                       options={"temperature": TEMPERATURE}, parent=self)
        self.worker.token.connect(self._on_token)
        self.worker.tool_call.connect(self._on_tool_call)
        self.worker.tool_result.connect(self._on_tool_result)
        self.worker.approval_needed.connect(self._on_approval_needed)
        self.worker.notice.connect(lambda t: self._add_bubble("notice", t))
        self.worker.discard_reply.connect(self._on_discard_reply)
        self.worker.done.connect(self._on_done)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(self._on_thread_finished)
        self._set_busy(True)
        self.worker.start()

    def _timeout(self):
        try:
            return int(self.plugin.api.get_settings().get("ollama_timeout", 240))
        except Exception:
            return 240

    def stop(self):
        if self.worker is not None:
            self.worker.cancel()
            self.status.setText("Stopping...")

    def clear_chat(self):
        if self.worker is not None:
            return
        self.history.clear()
        self._always_allow.clear()
        while self.feed_layout.count() > 1:
            item = self.feed_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _set_busy(self, busy):
        self.send_btn.setEnabled(not busy)
        self.stop_btn.setEnabled(busy)
        self.clear_btn.setEnabled(not busy)
        self.model_box.setEnabled(not busy)
        if busy:
            self.status.setText("⏳ Thinking...")
        else:
            self._update_status()

    # ------------------------------------------------------------------ worker signals

    def _on_token(self, piece):
        if self._assistant_bubble is None:
            self._assistant_bubble = self._add_bubble("assistant", model=self._request_model)
        self._assistant_bubble.append(piece)

    def _on_discard_reply(self):
        """The streamed text was a tool call / plan written as prose - remove it."""
        bubble, self._assistant_bubble = self._assistant_bubble, None
        if bubble is not None:
            self.feed_layout.removeWidget(bubble)
            bubble.deleteLater()

    def _on_tool_call(self, name, args_json):
        self._finish_assistant_bubble()
        shown = args_json if len(args_json) <= 400 else args_json[:400] + "..."
        self._tool_bubble = self._add_bubble("tool", f"{name}\n{shown}", model=self._request_model)
        self.status.setText("🔧 Running tool...")

    def _on_tool_result(self, name, preview, is_error):
        if self._tool_bubble is not None:
            self._tool_bubble.append(f"\n{'✗' if is_error else '↳'} {preview}")
        self.status.setText("⏳ Thinking...")

    def _on_approval_needed(self, name, args_json, holder):
        """GUI thread. The worker thread is waiting on holder['event']."""
        if name in self._always_allow:
            holder["allow"] = True
            holder["event"].set()
            return

        resolved = self.manager.resolve_tool(name)
        server, tool = resolved if resolved else ("?", name)
        shown = args_json if len(args_json) <= 600 else args_json[:600] + "\n..."

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Allow tool call?")
        box.setText(f"The assistant wants to run:\n\n    {tool}   (server: {server})")
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
        self._finish_assistant_bubble()
        if self._pending_user is not None:
            self.history.append(self._pending_user)
            self.history.extend(new_messages)
            self._pending_user = None
        self._set_busy(False)

    def _on_failed(self, error):
        self._finish_assistant_bubble()
        self._pending_user = None          # unanswered message is not kept in history
        self._add_bubble("error", error)
        self._set_busy(False)

    def _on_thread_finished(self):
        worker, self.worker = self.worker, None
        if worker is not None:
            worker.deleteLater()

    # ------------------------------------------------------------------ shutdown

    def cleanup(self):
        """Stop a running request so Qt never destroys a live QThread."""
        worker = self.worker
        if worker is not None:
            worker.cancel()
            worker.wait(3000)