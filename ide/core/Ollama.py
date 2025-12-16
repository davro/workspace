import subprocess
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QTextEdit,
    QLineEdit,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

# If using PySide6 instead, replace the imports above with:
# from PySide6.QtWidgets import (
#     QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
#     QPushButton, QTextEdit, QLineEdit
# )
# from PySide6.QtCore import Qt, QThread, pyqtSignal


# class OllamaWorker(QThread):
    # """Background worker to call Ollama without blocking the UI"""
    # finished = pyqtSignal(str)
    # error = pyqtSignal(str)

    # def __init__(self, model: str, prompt: str, timeout: int):
        # super().__init__()
        # self.model = model
        # self.prompt = prompt
        # self.timeout = timeout

    # def run(self):
        # try:
            # result = subprocess.run(
                # ["ollama", "run", self.model],
                # input=self.prompt,
                # capture_output=True,
                # text=True,
                # encoding="utf-8",
                # timeout=self.timeout,
            # )
            # if result.returncode == 0:
                # self.finished.emit(result.stdout.strip())
            # else:
                # self.error.emit(result.stderr.strip() or "Unknown error from ollama")
        # except subprocess.TimeoutExpired:
            # self.error.emit(f"Request timed out after {self.timeout} seconds")
        # except FileNotFoundError:
            # self.error.emit("ollama command not found – is Ollama installed and in PATH?")
        # except Exception as e:
            # self.error.emit(str(e))


# class OllamaChatWidget(QWidget):
    # def __init__(self, parent=None):
        # super().__init__(parent)
        # self.parent_ide = parent  # Reference to main IDE window for settings access

        # layout = QVBoxLayout(self)

        # # ---------------- Top bar ----------------
        # top_bar = QHBoxLayout()
        # top_bar.addWidget(QLabel("Model:"))

        # self.model_box = QComboBox()
        # self.model_box.setMinimumWidth(200)
        # top_bar.addWidget(self.model_box)

        # self.refresh_btn = QPushButton("Refresh Models")
        # self.refresh_btn.clicked.connect(self.refresh_models)
        # top_bar.addWidget(self.refresh_btn)

        # self.ps_btn = QPushButton("Show Loaded")
        # self.ps_btn.clicked.connect(self.show_ollama_ps)
        # top_bar.addWidget(self.ps_btn)

        # top_bar.addStretch()

        # self.status_label = QLabel("Ready")
        # self.status_label.setStyleSheet("color: #999;")
        # top_bar.addWidget(self.status_label)

        # layout.addLayout(top_bar)

        # # ---------------- Chat display ----------------
        # self.chat = QTextEdit()
        # self.chat.setReadOnly(True)
        # self.chat.setStyleSheet("background:#1E1E1E; color:#CCC; font-family: Consolas, Monaco, monospace;")
        # layout.addWidget(self.chat)

        # # ---------------- Input bar ----------------
        # bottom = QHBoxLayout()
        # self.input = QLineEdit()
        # self.input.setPlaceholderText("Type your message here...")
        # self.input.returnPressed.connect(self.send_message)
        # bottom.addWidget(self.input)

        # self.send_btn = QPushButton("Send")
        # self.send_btn.clicked.connect(self.send_message)
        # bottom.addWidget(self.send_btn)

        # layout.addLayout(bottom)

        # # Initial model list load
        # self.worker: Optional[OllamaWorker] = None
        # self.refresh_models()

    # def get_timeout(self) -> int:
        # if self.parent_ide and hasattr(self.parent_ide, 'settings'):
            # return self.parent_ide.settings.get('ollama_timeout', 180)
        # return 180

    # def show_ollama_ps(self):
        # try:
            # result = subprocess.run(
                # ["ollama", "ps"],
                # capture_output=True,
                # text=True,
                # encoding="utf-8",
                # timeout=10
            # )
            # output = result.stdout.strip() or "No models currently loaded."
            # self.chat.append("\n=== Currently Loaded Models ===\n")
            # self.chat.append(output)
            # self.chat.append("================================\n")
        # except Exception as e:
            # self.chat.append(f"\nError running 'ollama ps': {e}\n")

    # def refresh_models(self):
        # self.model_box.clear()
        # try:
            # result = subprocess.run(
                # ["ollama", "list"],
                # capture_output=True,
                # text=True,
                # encoding="utf-8",
                # timeout=10
            # )
            # lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            # if len(lines) > 1:  # Skip header
                # for line in lines[1:]:
                    # model_name = line.split()[0]
                    # self.model_box.addItem(model_name)
            # if self.model_box.count() == 0:
                # self.model_box.addItem("No models found")
                # self.status_label.setText("⚠ No models")
        # except FileNotFoundError:
            # self.model_box.addItem("ollama not available")
            # self.status_label.setText("⚠ ollama not found")
        # except Exception:
            # self.model_box.addItem("Error loading models")
            # self.status_label.setText("⚠ Error")

    # def send_message(self):
        # text = self.input.text().strip()
        # if not text:
            # return
        # self._send(text)
        # self.input.clear()

    # def send_text_message(self, text: str):
        # """Programmatic way to send a message (e.g. from other parts of IDE)"""
        # if not text.strip():
            # return
        # self.chat.append(f"You: {text}\n")
        # self._send(text)

    # def _send(self, text: str):
        # model = self.model_box.currentText()
        # if model in {"No models found", "ollama not available", "Error loading models"}:
            # self.chat.append("Error: No valid Ollama model available\n")
            # return

        # self.chat.append(f"You: {text}\n")
        # self.chat.append("Ollama: <i>[thinking...]</i>\n")
        # self.send_btn.setEnabled(False)
        # self.status_label.setText("⏳ Thinking...")

        # timeout = self.get_timeout()
        # self.worker = OllamaWorker(model, text + "\n", timeout)  # ollama run reads from stdin
        # self.worker.finished.connect(self.handle_response)
        # self.worker.error.connect(self.handle_error)
        # self.worker.start()

    # def handle_response(self, response: str):
        # # Remove the "[thinking...]" line
        # self._remove_thinking_line()
        # self.chat.append(f"Ollama: {response}\n")
        # self.send_btn.setEnabled(True)
        # self.status_label.setText("✓ Ready")

    # def handle_error(self, error_msg: str):
        # self._remove_thinking_line()
        # self.chat.append(f"<font color='#FF5555'>Error: {error_msg}</font>\n")
        # self.send_btn.setEnabled(True)
        # self.status_label.setText("✗ Error")

    # def _remove_thinking_line(self):
        # cursor = self.chat.textCursor()
        # cursor.movePosition(cursor.MoveOperation.End)
        # cursor.select(cursor.BlockUnderCursor)
        # if "[thinking...]" in cursor.selectedText():
            # cursor.removeSelectedText()
            # self.chat.setTextCursor(cursor)
            # # Remove extra newline if needed
            # if self.chat.toPlainText().endswith("\n\n"):
                # cursor.deletePreviousChar()



# OLD

class OllamaWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, model, prompt, timeout=180):
        super().__init__()
        self.model = model
        self.prompt = prompt
        self.timeout = timeout

    def run(self):
        try:
            result = subprocess.run(
                ["ollama", "run", self.model, self.prompt],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            self.finished.emit(result.stdout.strip())
        except subprocess.TimeoutExpired:
            self.error.emit(f"Ollama request timed out after {self.timeout} seconds")
        except Exception as e:
            self.error.emit(str(e))




class OllamaChatWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_ide = parent
        layout = QVBoxLayout(self)

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

        top_bar.addStretch()

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #999;")
        top_bar.addWidget(self.status_label)

        layout.addLayout(top_bar)

        self.chat = QTextEdit()
        self.chat.setReadOnly(True)
        self.chat.setStyleSheet("background:#1E1E1E;color:#CCC;")
        layout.addWidget(self.chat)

        bottom = QHBoxLayout()
        self.input = QLineEdit()
        self.input.returnPressed.connect(self.send_message)
        bottom.addWidget(self.input)
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.send_message)
        bottom.addWidget(self.send_btn)
        layout.addLayout(bottom)

        self.worker = None
        self.refresh_models()

    def get_timeout(self):
        if self.parent_ide and hasattr(self.parent_ide, 'settings'):
            return self.parent_ide.settings.get('ollama_timeout', 180)
        return 180

    def show_ollama_ps(self):
        try:
            result = subprocess.run(
                ["ollama", "ps"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.stdout.strip():
                self.chat.append("\n=== Currently Loaded Models ===\n")
                self.chat.append(result.stdout)
                self.chat.append("================================\n")
            else:
                self.chat.append("\n=== No models currently loaded ===\n")
        except Exception as e:
            self.chat.append(f"\nError checking loaded models: {e}\n")

    def refresh_models(self):
        self.model_box.clear()
        try:
            r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
            lines = [l.strip() for l in r.stdout.splitlines() if l.strip()]
            if len(lines) > 1:
                for line in lines[1:]:
                    parts = line.split()
                    if parts:
                        self.model_box.addItem(parts[0])
            if self.model_box.count() == 0:
                self.model_box.addItem("No models found")
        except Exception:
            self.model_box.addItem("ollama not available")

    def send_message(self):
        text = self.input.text().strip()
        if not text:
            return

        model = self.model_box.currentText()
        if model in ["No models found", "ollama not available"]:
            self.chat.append("Error: No valid Ollama model selected\n")
            return

        self.chat.append(f"You: {text}\n")
        self.input.clear()
        self.send_btn.setEnabled(False)
        self.status_label.setText("⏳ Waiting...")
        self.chat.append("Ollama: [thinking...]\n")

        timeout = self.get_timeout()
        self.worker = OllamaWorker(model, text, timeout)
        self.worker.finished.connect(self.handle_response)
        self.worker.error.connect(self.handle_error)
        self.worker.start()

    def send_text_message(self, text):
        if not text.strip():
            return

        model = self.model_box.currentText()
        if model in ["No models found", "ollama not available"]:
            self.chat.append("Error: No valid Ollama model selected\n")
            return

        self.chat.append(f"You: {text}\n")
        self.send_btn.setEnabled(False)
        self.status_label.setText("⏳ Waiting...")
        self.chat.append("Ollama: [thinking...]\n")

        timeout = self.get_timeout()
        self.worker = OllamaWorker(model, text, timeout)
        self.worker.finished.connect(self.handle_response)
        self.worker.error.connect(self.handle_error)
        self.worker.start()

    def handle_response(self, response):
        text = self.chat.toPlainText()
        lines = text.split('\n')
        if lines and '[thinking...]' in lines[-2]:
            lines = lines[:-2]
            self.chat.setPlainText('\n'.join(lines))

        self.chat.append(f"Ollama: {response}\n")
        self.send_btn.setEnabled(True)
        self.status_label.setText("✓ Ready")

    def handle_error(self, error_msg):
        text = self.chat.toPlainText()
        lines = text.split('\n')
        if lines and '[thinking...]' in lines[-2]:
            lines = lines[:-2]
            self.chat.setPlainText('\n'.join(lines))

        self.chat.append(f"Error: {error_msg}\n")
        self.send_btn.setEnabled(True)
        self.status_label.setText("✗ Error")