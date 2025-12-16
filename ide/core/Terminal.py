import subprocess
from pathlib import Path

from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtGui import QFont, QTextCursor
from PyQt6.QtCore import Qt

from ide import VERSION, WORKSPACE_PATH

class Terminal(QTextEdit):
    def __init__(self, font_size=10):
        super().__init__()
        self.setFont(QFont("Monospace", font_size))
        self.setStyleSheet("QTextEdit { background-color: #1E1E1E; color: #CCCCCC; border: none; }")
        self.current_dir = str(Path.home() / WORKSPACE_PATH)
        self.command_history = []
        self.history_index = -1

        self.append("=== Simple Terminal ===\n")
        self.append("Note: This is a basic terminal. For complex programs, use a real terminal.\n\n")
        self.append(f"Working directory: {self.current_dir}\n\n")
        self.show_prompt()

    def show_prompt(self):
        self.append(f"{self.current_dir}$ ")
        self.command_start_pos = self.textCursor().position()

    def execute_command(self, command):
        command = command.strip()
        if not command:
            self.show_prompt()
            return

        self.command_history.append(command)
        self.history_index = len(self.command_history)

        if command.startswith("cd "):
            target = command[3:].strip()
            if target:
                try:
                    if target.startswith("~"):
                        target = str(Path.home()) + target[1:]
                    p = Path(target)
                    if not p.is_absolute():
                        p = Path(self.current_dir) / p
                    p = p.resolve()
                    if p.exists() and p.is_dir():
                        self.current_dir = str(p)
                        self.append("\n")
                    else:
                        self.append(f"\ncd: no such directory: {target}\n")
                except Exception as e:
                    self.append(f"\ncd error: {e}\n")
            self.show_prompt()
            return

        if command == "clear":
            self.clear()
            self.append("=== Simple Terminal ===\n")
            self.show_prompt()
            return

        if command == "pwd":
            self.append(f"\n{self.current_dir}\n")
            self.show_prompt()
            return

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.current_dir,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.stdout:
                self.append("\n" + result.stdout)
            if result.stderr:
                self.append(result.stderr)
        except subprocess.TimeoutExpired:
            self.append("\n[Command timed out after 10 seconds]\n")
        except Exception as e:
            self.append(f"\nError: {e}\n")

        self.show_prompt()

    def keyPressEvent(self, event):
        cursor_pos = self.textCursor().position()

        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            cursor = self.textCursor()
            cursor.setPosition(self.command_start_pos)
            cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
            cmd = cursor.selectedText()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.setTextCursor(cursor)
            self.execute_command(cmd)
            return

        elif event.key() == Qt.Key.Key_Backspace:
            if cursor_pos > self.command_start_pos:
                super().keyPressEvent(event)
            return

        elif event.key() == Qt.Key.Key_Up:
            if self.command_history and self.history_index > 0:
                self.history_index -= 1
                self.replace_command(self.command_history[self.history_index])
            return

        elif event.key() == Qt.Key.Key_Down:
            if self.command_history and self.history_index < len(self.command_history) - 1:
                self.history_index += 1
                self.replace_command(self.command_history[self.history_index])
            return

        super().keyPressEvent(event)

    def replace_command(self, text):
        cursor = self.textCursor()
        cursor.setPosition(self.command_start_pos)
        cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertText(text)