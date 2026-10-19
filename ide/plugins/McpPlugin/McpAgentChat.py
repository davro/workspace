"""
McpAgentChat - a workspace-aware agent chat with bubble UI.

Engine: OllamaChatWorker (OllamaPlugin/OllamaWorker.py), which talks to Ollama's
/api/chat with *native* tool calling. The model is given the MCP tools through
the API's `tools` field, so there is no JSON-in-the-prompt protocol to parse,
no tool-name guessing, and it can chain several tool calls per question
(list a folder -> read a file -> answer).

Every tool call needs the user's approval.
"""

import copy
import json
import os
import re
import time
import urllib.request
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QCompleter, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMenu, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)
from PyQt6.QtCore import QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QStandardItem, QStandardItemModel

# Raises ImportError if the Ollama plugin isn't installed; McpPlugin handles that.
from OllamaPlugin.OllamaWorker import OllamaChatWorker, ollama_base_url
from McpPlugin.skills import replace_token, resolve_filenames
from McpPlugin.SkillStepWorker import SkillStepWorker

# PREFERRED_MODEL = "llama3.1:8b"
# TEMPERATURE = 0.2       # low = quotes tool output faithfully instead of embellishing it

PREFERRED_MODEL = "qwen3:8b"
TEMPERATURE = 0.2       # low = quotes tool output faithfully instead of embellishing it
NUM_CTX = 16384         # Ollama's default context is small: a skill + tool list would be truncated

# Skills (served by McpPlugin/skills_server.py, registered in servers.json as "skills")
SKILLS_SERVER = "skills"
# api.get_current_editor() returns the active editor; its file path lives in one of these attributes
# (or zero-argument methods). Add yours here if the editor names it differently.
EDITOR_PATH_ATTRS = ("file_path", "filepath", "current_file", "path", "filename", "get_file_path")
SKILL_TOOLS = {"list_skills", "load_skill"}     # read-only: no approval prompt needed

# Optional arguments that small models misuse (e.g. head=20 -> explains a file it never read).
# They are removed from the tool schema sent to Ollama. Keys are tool names without the server prefix.
HIDE_TOOL_ARGS = {"read_text_file": {"head", "tail"}, "read_file": {"head", "tail"}}

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


def _fmt_s(sec):
    sec = max(0.0, sec)
    return f"{sec:.1f}s" if sec < 60 else f"{int(sec // 60)}m {int(sec % 60):02d}s"


def _fmt_stats(wall, first_token=None, stats=None, label="", think=None):
    """'⏱ 12.3s · 412 tok @ 34.1 tok/s · prompt 5,210 tok in 3.9s · first token 4.1s'"""
    parts = [f"⏱ {label}{_fmt_s(wall)}"]
    if stats:                                   # Ollama's own numbers (nanoseconds), if the worker passes them
        n, d = stats.get("eval_count"), stats.get("eval_duration")
        if n and d:
            parts.append(f"{n} tok @ {n / (d / 1e9):.1f} tok/s")
        pn, pd = stats.get("prompt_eval_count"), stats.get("prompt_eval_duration")
        if pn:
            parts.append(f"prompt {pn:,} tok" + (f" in {_fmt_s(pd / 1e9)}" if pd else ""))
        load = stats.get("load_duration")
        if load and load > 1e9:
            parts.append(f"model load {_fmt_s(load / 1e9)}")
    if first_token is not None:
        parts.append(f"first token {_fmt_s(first_token)}")
    if think is not None:
        parts.append("think " + ("off" if think is False else "on" if think is True else str(think)))
    return " · ".join(parts)


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

        self._footer_text = ""
        self.footer = QLabel()
        self.footer.setTextFormat(Qt.TextFormat.PlainText)
        self.footer.setStyleSheet("color: #8A9BA8; font-size: 8pt; background: transparent;")
        self.footer.setVisible(False)
        layout.addWidget(self.footer)

        self.set_text(text)

    def set_footer(self, text):
        self._footer_text = text
        self.footer.setText(text)
        self.footer.setVisible(bool(text))

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
        self._active_skill = None     # set by "/skill-name"; stays on until "/skill off" or Clear
        self._run_skill = None        # skill named in the message being sent (runs step by step)
        self._stepwise = True         # "/steps off" = one single turn instead
        # timing (wall clock, monotonic)
        self._t_run = self._t_call = self._t_first = self._t_tool = None
        self._call_open = False       # a model call started and has not yet been attributed to a bubble
        self._calls = 0               # model calls beyond the first (tool rounds / steps)
        self._call_stats = None       # Ollama's stats for the latest model call (optional)
        self._caps_cache = {}         # model -> Ollama capabilities list (from /api/show)
        self._think_used = None       # the `think` value sent for the current run (None = not sent)
        self._tool_model_info = ""
        self._approval_total = 0.0    # seconds spent waiting in approval dialogs this run
        self._approval_at_tool = self._approval_at_step = 0.0
        self._step_notice = None
        self._step_label = ""
        self._step_t0 = None

        self.setStyleSheet(PANEL_CSS)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # ---- header ---------------------------------------------------------
        top = QHBoxLayout()
        top.addWidget(QLabel("Model:"))
        self.model_box = QComboBox()
        self.model_box.setMinimumWidth(140)
        top.addWidget(self.model_box, 1)
        self.think_box = QComboBox()
        self.think_box.addItem("Think: auto", "auto")
        self.think_box.addItem("Think: on", "on")
        self.think_box.addItem("Think: off", "off")
        self.think_box.setToolTip(
            "Reasoning ('thinking') models such as qwen3 deliberate before answering.\n"
            "auto: off for skill steps, the model's default for normal chat\n"
            "on / off: force it. Only sent to models that support it (also: /think auto|on|off)")
        top.addWidget(self.think_box)
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
        self.input.setPlaceholderText("Ask about your workspace...  (type / for skills and commands)")
        self.input.returnPressed.connect(self._on_return_pressed)
        self._setup_command_popup()
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
            f"Think: {self.think_box.currentData()}",
            f"Workspace: {self._workspace_path()}",
            f"MCP tools: {self.manager.tool_count()}",
            "-" * 40,
        ]
        for bubble in bubbles:
            footer = f"\n{bubble._footer_text}" if bubble._footer_text else ""
            lines.append(f"{bubble.title}: {bubble._text}{footer}\n")
        QApplication.clipboard().setText("\n".join(lines).rstrip() + "\n")
        self.status.setText(f"✓ Copied {len(bubbles)} messages")
        QTimer.singleShot(2500, self._update_status)

    def _finish_assistant_bubble(self):
        if self._assistant_bubble is not None:
            self._assistant_bubble.render_markdown()
            if self._t_call is not None:
                self._assistant_bubble.set_footer(
                    _fmt_stats(time.monotonic() - self._t_call, self._t_first, self._call_stats, think=self._think_used))
            self._call_stats, self._call_open = None, False
            self._assistant_bubble = None

    def _workspace_path(self):
        try:
            return str(Path(self.plugin.api.get_workspace_path()).resolve())
        except Exception:
            return str(Path.cwd())

    def _system_prompt(self, include_active=True):
        return (
            "You are a coding assistant built into Workspace IDE.\n"
            f"The workspace root is: {self._workspace_path()}\n"
            "Use the provided tools to inspect or change files, always with absolute paths "
            "inside the workspace root. Read before you write. "
            "When asked to explain or review a file, read the WHOLE file first and never describe "
            "code you have not actually read; if a result looks cut off, say so. "
            "If the user's message already contains an absolute path, use it directly with the "
            "read/list tools and do NOT search for it. "
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
        ) + self._skills_prompt(include_active)

    def _tools_for_model(self):
        """MCP tools in Ollama format, minus the optional arguments listed in HIDE_TOOL_ARGS."""
        tools = copy.deepcopy(self.manager.ollama_tools())
        for tool in tools:
            fn = tool["function"]
            hide = HIDE_TOOL_ARGS.get(fn["name"].split("__", 1)[-1])
            if not hide:
                continue
            params = fn.get("parameters") or {}
            for arg in hide:
                params.get("properties", {}).pop(arg, None)
            if "required" in params:
                params["required"] = [r for r in params["required"] if r not in hide]
        return tools or None

    # ------------------------------------------------------------------ "/" command popup

    # (command, description, takes an argument?)
    BUILTIN_COMMANDS = [
        ("/skills", "list the available skills", False),
        ("/skill off", "deactivate the active skill", False),
        ("/steps on", "run skills step by step, then verify", False),
        ("/steps off", "run skills in a single turn", False),
        ("/think auto", "off for skill steps, model default otherwise", False),
        ("/think on", "force thinking on", False),
        ("/think off", "force thinking off", False),
    ]

    def _setup_command_popup(self):
        """Typing '/' in the input pops up the skills and commands; pick one with arrows+Enter or the mouse."""
        self._cmd_args = set()                     # commands that expect text after them (the skills)
        self._cmd_chosen_at = 0.0                  # when a popup item was last picked (see send_message)
        self._cmd_model = QStandardItemModel(self)
        completer = QCompleter(self._cmd_model, self)
        completer.setCompletionRole(Qt.ItemDataRole.UserRole)     # match / insert the bare command,
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)   # but display "command - description"
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setMaxVisibleItems(10)
        completer.popup().setStyleSheet(
            "QListView { background-color: #2B2B2B; color: #FFFFFF; border: 1px solid #3C3F41; font-size: 10pt; }"
            "QListView::item { padding: 3px 6px; }"
            "QListView::item:selected { background-color: #4B6EAF; }")
        completer.activated[str].connect(self._on_command_chosen)
        self.input.setCompleter(completer)
        self._cmd_completer = completer
        self._refresh_commands()

    def _refresh_commands(self):
        """Rebuild the popup entries (skills are re-read from disk, so new SKILL.md files show up)."""
        self._cmd_model.clear()
        self._cmd_args = set()
        skills = self._skills()
        entries = []
        if skills:
            for name, skill in skills.scan().items():
                entries.append((f"/{name}", skill["description"], True))
        entries += self.BUILTIN_COMMANDS
        for command, description, takes_arg in entries:
            short = description if len(description) <= 80 else description[:77] + "..."
            item = QStandardItem(f"{command}  -  {short}")
            item.setData(command, Qt.ItemDataRole.UserRole)
            item.setToolTip(description)
            item.setEditable(False)
            self._cmd_model.appendRow(item)
            if takes_arg:
                self._cmd_args.add(command)

    def _on_return_pressed(self):
        """Enter in the input. If it is choosing a popup item (popup open with an item highlighted, or the
        item was chosen a moment ago) it must not also send: the same key press reaches both."""
        popup = self._cmd_completer.popup()
        choosing = popup.isVisible() and popup.currentIndex().isValid()
        if choosing or time.monotonic() - self._cmd_chosen_at < 0.4:
            return
        self.send_message()

    def _on_command_chosen(self, command):
        """Skills need a target, so choosing one only fills in '/skill ' and waits for you to type or press
        Enter. Commands without arguments (/skills, /steps off, /think on ...) have nothing more to type: run them."""
        self._cmd_chosen_at = time.monotonic()

        def apply():                      # runs after QLineEdit has put the completion text in itself
            if command in self._cmd_args:
                self.input.setText(command + " ")
                self.input.setFocus()
            else:
                self.input.setText(command)
                self.send_message()
        QTimer.singleShot(0, apply)

    def _current_file(self):
        """Absolute path of the file open in the editor, or None."""
        try:
            editor = self.plugin.api.get_current_editor()
        except Exception:
            return None
        if editor is None:
            return None
        for attr in EDITOR_PATH_ATTRS:
            value = getattr(editor, attr, None)
            if callable(value):
                try:
                    value = value()
                except Exception:
                    value = None
            if isinstance(value, (str, Path)) and str(value).strip():
                return os.path.abspath(str(value))
        return None

    def _pick_candidate(self, token, candidates):
        """Ask which file was meant when a name matches several. Returns the chosen path or None."""
        root = self._workspace_path()
        menu = QMenu(self)
        header = menu.addAction(f"'{token}' matches several files - pick one:")
        header.setEnabled(False)
        menu.addSeparator()
        for path in candidates:
            label = os.path.relpath(path, root) if path.startswith(root) else path
            menu.addAction(label).setData(path)
        action = menu.exec(self.input.mapToGlobal(QPoint(0, 0)))
        return action.data() if action is not None and action.data() else None

    def _capabilities(self, model):
        """Ollama's capability list for a model ('completion', 'tools', 'thinking', ...) or None if unknown
        (old Ollama without the field, or server not reachable). Cached once known."""
        if model in self._caps_cache:
            return self._caps_cache[model]
        caps = None
        try:
            req = urllib.request.Request(ollama_base_url() + "/api/show",
                                         data=json.dumps({"model": model}).encode("utf-8"),
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                found = json.loads(resp.read().decode("utf-8")).get("capabilities")
            caps = [str(c) for c in found] if isinstance(found, list) else None
        except Exception:
            caps = None
        if caps is not None:
            self._caps_cache[model] = caps
        return caps

    def _think_for(self, model, stepwise):
        """Value for Ollama's `think` option, or None to leave it out of the request."""
        mode = self.think_box.currentData() or "auto"
        want = {"auto": False if stepwise else None, "on": True, "off": False}[mode]
        if want is None:
            return None
        caps = self._capabilities(model)
        if mode == "auto" and caps is None:
            return None                       # can't tell: don't risk it unless the user forced a mode
        if caps is not None and "thinking" not in caps:
            return None                       # model has no thinking mode (or no switch for it)
        if model.lower().startswith("gpt-oss"):
            return "medium" if want else "low"      # gpt-oss takes levels, not a boolean
        return want

    def _skills(self):
        return getattr(self.plugin.api, "skills", None)

    def _skills_prompt(self, include_active=True):
        skills = self._skills()
        if not skills:
            return ""
        # Only tell the model it can load skills if the skills server is actually connected
        can_load = self.manager.resolve_tool(f"{SKILLS_SERVER}__load_skill") is not None
        text = skills.index_prompt(f"{SKILLS_SERVER}__load_skill" if can_load else None)
        out = ("\n\n" + text) if text else ""
        if self._active_skill and include_active:
            out += (f"\n\nACTIVE SKILL \"{self._active_skill}\" - follow these instructions "
                    f"for every answer:\n\n" + skills.load(self._active_skill, compact_mode=True))
        return out

    def _handle_slash(self, text):
        """Returns the text to send to the model, or None if the command was handled locally."""
        if not text.startswith("/"):
            return text
        skills = self._skills()
        known = skills.scan() if skills else {}
        cmd, _, rest = text[1:].partition(" ")
        rest = rest.strip()
        if cmd == "skills":
            lines = [f"/{n}  -  {s['description'][:90]}" for n, s in known.items()]
            self._add_bubble("notice", "\n".join(lines) + "\n\n/skill off  -  deactivate    /steps on|off  -  step-by-step mode    /think auto|on|off"
                             if lines else "No skills found.")
            return None
        if cmd == "think" and rest in ("auto", "on", "off"):
            self.think_box.setCurrentIndex(self.think_box.findData(rest))
            self._add_bubble("notice", "Think: " + rest + (" (off for skill steps, model default for normal chat)"
                                                           if rest == "auto" else ""))
            return None
        if cmd == "steps" and rest in ("on", "off"):
            self._stepwise = rest == "on"
            self._add_bubble("notice", "Skills now run " + ("step by step, then a verification pass."
                                                           if self._stepwise else "in a single turn."))
            return None
        if cmd == "skill" and rest == "off":
            self._active_skill = None
            self._add_bubble("notice", "Skill deactivated.")
            self._update_status()
            return None
        if cmd in known:
            self._active_skill = cmd
            self._update_status()
            current = self._current_file()
            if current:                      # "/skill" alone, or "/skill this file": use the open file
                rest = current if not rest else re.sub(
                    r"\b(?:this|the current|the open|current) file\b", lambda _m: current, rest, flags=re.I)
            if not rest:
                self._add_bubble("notice", f"Skill \"{cmd}\" is active. Now tell me what to apply "
                                           f"it to (a file path, a function name, a question).")
                return None
            self._run_skill = cmd
            self._add_bubble("notice", f"🎓 Skill: {cmd}")
            return rest
        return text                  # not a skill command: send as normal text

    def _update_status(self):
        count = self.manager.tool_count()
        skill = f"  |  🎓 skill: {self._active_skill}" if self._active_skill else ""
        self.status.setText((f"🔧 {count} MCP tool{'s' if count != 1 else ''} available"
                             if count else "No MCP tools connected - answering without tools") + skill)

    # ------------------------------------------------------------------ models

    def refresh_models(self):
        self._refresh_commands()          # the ↻ button also re-reads the skills
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
        self._refresh_commands()
        run_skill = None
        if text.startswith("/"):
            self.input.clear()
            text = self._handle_slash(text)
            run_skill, self._run_skill = self._run_skill, None
            if text is None:
                return
        model = self.model_box.currentText()
        if model.startswith("("):
            self._add_bubble("error", "No Ollama model available. Is `ollama serve` running?")
            self.input.setText(f"/{run_skill} {text}" if run_skill else text)
            return

        self.input.clear()
        self._request_model = model
        # "McpClientManager.py" -> absolute path, so the model reads it instead of searching
        original = text
        text, notes, ambiguous = resolve_filenames(text, self._workspace_path(),
                                                   current_file=self._current_file())
        for token, candidates in ambiguous.items():          # never guess between real files: ask
            chosen = self._pick_candidate(token, candidates)
            if chosen is None:
                self.input.setText(f"/{run_skill} {original}" if run_skill else original)
                self._add_bubble("notice", f"'{token}' matches several files, so nothing was sent. Pick one, "
                                           f"or type a longer path (for example project/dir/File.py).")
                return
            text = replace_token(text, token, chosen)
        if notes:
            self._add_bubble("notice", "\n".join(notes))
        self._add_bubble("user", text)
        self._pending_user = {"role": "user", "content": text}

        tools = self._tools_for_model()

        # A skill invoked with /skill-name <target> runs step by step if it has '### Step N' sections
        steps, checklist = [], []
        skills = self._skills()
        if run_skill and self._stepwise and skills:
            steps, checklist = skills.plan(run_skill)
        stepwise = len(steps) >= 2
        # step by step: each step is sent as its own turn, so keep the whole skill out of the system prompt
        messages = ([{"role": "system", "content": self._system_prompt(include_active=not stepwise)}]
                    + self.history + [self._pending_user])

        self._assistant_bubble = None
        self._tool_bubble = None
        self._think_used = self._think_for(model, stepwise)
        common = dict(tools=tools, mcp=self.manager, timeout=self._timeout(),
                      options={"temperature": TEMPERATURE, "num_ctx": NUM_CTX}, parent=self)
        if self._think_used is not None:
            common["think"] = self._think_used
        if stepwise:
            self.worker = SkillStepWorker(model, messages, steps=steps, checklist=checklist,
                                          skill_name=run_skill, **common)
            self.worker.step_started.connect(self._on_step_started)
        else:
            self.worker = OllamaChatWorker(model, messages, **common)
        self.worker.token.connect(self._on_token)
        self.worker.tool_call.connect(self._on_tool_call)
        self.worker.tool_result.connect(self._on_tool_result)
        self.worker.approval_needed.connect(self._on_approval_needed)
        self.worker.notice.connect(lambda t: self._add_bubble("notice", t))
        self.worker.discard_reply.connect(self._on_discard_reply)
        self.worker.done.connect(self._on_done)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(self._on_thread_finished)
        if hasattr(self.worker, "stats"):                 # present once OllamaWorker.py has the stats patch
            self.worker.stats.connect(self._on_stats)
        self._t_run = self._t_call = time.monotonic()
        self._t_first, self._call_open, self._calls, self._call_stats = None, True, 0, None
        self._approval_total = 0.0
        self._step_notice = None
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
        self._active_skill = None
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

    def _close_step(self, now):
        if self._step_notice is not None:
            waited = self._approval_total - self._approval_at_step
            self._step_notice.set_text(f"{self._step_label}   ({_fmt_s(now - self._step_t0 - waited)})")
            self._step_notice = None

    def _on_stats(self, stats):
        self._call_stats = stats

    def _on_step_started(self, index, total, title):
        now = time.monotonic()
        self._finish_assistant_bubble()          # every step gets its own bubble
        self._close_step(now)
        self._step_label = f"Step {index}/{total}: {title}"
        self._step_notice = self._add_bubble("notice", self._step_label)
        self._step_t0, self._approval_at_step = now, self._approval_total
        self._t_call, self._t_first, self._call_open, self._call_stats = now, None, True, None
        self._calls += 1
        self.status.setText(f"⏳ Step {index}/{total}: {title}")

    def _on_token(self, piece):
        if self._assistant_bubble is None:
            self._assistant_bubble = self._add_bubble("assistant", model=self._request_model)
            if self._t_call is not None:
                self._t_first = time.monotonic() - self._t_call
        self._assistant_bubble.append(piece)

    def _on_discard_reply(self):
        """The streamed text was a tool call / plan written as prose - remove it."""
        bubble, self._assistant_bubble = self._assistant_bubble, None
        if bubble is not None:
            self.feed_layout.removeWidget(bubble)
            bubble.deleteLater()

    def _on_tool_call(self, name, args_json):
        now = time.monotonic()
        had_text = self._assistant_bubble is not None
        call_was_open, stats = self._call_open, self._call_stats
        self._finish_assistant_bubble()          # a text bubble gets its own timing footer
        # a model call that only produced this tool call has no text bubble: report it on the tool bubble
        self._tool_model_info = ""
        if call_was_open and not had_text and self._t_call is not None:
            self._tool_model_info = _fmt_stats(now - self._t_call, None, stats, label="model ", think=self._think_used)
        self._call_open = False
        shown = args_json if len(args_json) <= 400 else args_json[:400] + "..."
        self._tool_bubble = self._add_bubble("tool", f"{name}\n{shown}", model=self._request_model)
        self._t_tool, self._approval_at_tool = now, self._approval_total
        self.status.setText("🔧 Running tool...")

    def _on_tool_result(self, name, preview, is_error):
        now = time.monotonic()
        if self._tool_bubble is not None:
            self._tool_bubble.append(f"\n{'✗' if is_error else '↳'} {preview}")
            if self._t_tool is not None:
                waited = self._approval_total - self._approval_at_tool
                tool_part = f"tool {_fmt_s(now - self._t_tool - waited)}"
                self._tool_bubble.set_footer(
                    f"{self._tool_model_info} · {tool_part}" if self._tool_model_info else f"⏱ {tool_part}")
        self._t_call, self._t_first, self._call_open, self._call_stats = now, None, True, None
        self._calls += 1
        self.status.setText("⏳ Thinking...")

    def _on_approval_needed(self, name, args_json, holder):
        t0 = time.monotonic()
        try:
            self._ask_approval(name, args_json, holder)
        finally:
            self._approval_total += time.monotonic() - t0       # waiting for the user is not "slow"

    def _ask_approval(self, name, args_json, holder):
        """GUI thread. The worker thread is waiting on holder['event']."""
        if name in self._always_allow:
            holder["allow"] = True
            holder["event"].set()
            return

        resolved = self.manager.resolve_tool(name)
        server, tool = resolved if resolved else ("?", name)
        if server == SKILLS_SERVER and tool in SKILL_TOOLS:      # reading instructions is harmless
            holder["allow"] = True
            holder["event"].set()
            return
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
        now = time.monotonic()
        self._close_step(now)
        if self._t_run is not None and self._calls >= 1:
            note = f"⏱ Total {_fmt_s(now - self._t_run - self._approval_total)}"
            if self._approval_total >= 1.0:
                note += f"  (+ {_fmt_s(self._approval_total)} waiting for approval)"
            self._add_bubble("notice", note)
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