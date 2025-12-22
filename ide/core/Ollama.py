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