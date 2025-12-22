# ============================================================================
# managers/tab_manager.py
# ============================================================================

from pathlib import Path
from PyQt6.QtWidgets import QMessageBox, QInputDialog, QLineEdit
from PyQt6.QtCore import QTimer
from ide.core.CodeEditor import CodeEditor


class TabManager:
    """Manages editor tabs and their operations"""

    def __init__(self, tabs_widget, parent):
        self.tabs = tabs_widget
        self.parent = parent


    def open_file_by_path(self, path, settings=None):
        """Open a file in a new tab or switch to existing tab"""
        # Check if already open
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if isinstance(widget, CodeEditor) and widget.file_path == str(path):
                self.tabs.setCurrentIndex(i)
                
                # Track in recent files when switching to existing tab
                if hasattr(self.parent, 'recent_files_manager'):
                    self.parent.recent_files_manager.add_file(str(path))
                
                return widget
    
        # Create new editor
        if settings is None:
            settings = {}
        
        editor = CodeEditor(
            font_size=settings.get('editor_font_size', 11),
            tab_width=settings.get('tab_width', 4),
            show_line_numbers=settings.get('show_line_numbers', True),
            gutter_width=settings.get('gutter_width', 10)  # ADD THIS
        )
        
        if editor.load_file(str(path)):
            tab_index = self.tabs.addTab(editor, path.name)
            self.tabs.setTabToolTip(tab_index, str(path))
            editor.textChanged.connect(lambda: self.parent.on_editor_modified(editor))
            self.tabs.setCurrentWidget(editor)
            
            # Track in recent files when opening new file
            if hasattr(self.parent, 'recent_files_manager'):
                self.parent.recent_files_manager.add_file(str(path))
            
            return editor
        
        return None


    def close_tab(self, index):
        """Close a tab at the given index"""
        editor = self.tabs.widget(index)
        if isinstance(editor, CodeEditor) and editor.document().isModified():
            reply = QMessageBox.question(
                self.parent,
                "Unsaved Changes",
                f"Save changes to {self.tabs.tabText(index)}?",
                QMessageBox.StandardButton.Yes |
                QMessageBox.StandardButton.No |
                QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Yes:
                editor.save_file()
            elif reply == QMessageBox.StandardButton.Cancel:
                return False

        # Update tab order tracking
        if hasattr(self.parent, 'tab_order_manager'):
            self.parent.tab_order_manager.remove_tab(index)

        self.tabs.removeTab(index)
        return True

    def close_tab_by_path(self, file_path):
        """Close tab with the given file path"""
        for i in range(self.tabs.count()):
            editor = self.tabs.widget(i)
            if isinstance(editor, CodeEditor) and editor.file_path == file_path:
                self.tabs.removeTab(i)
                return True
        return False

    def close_other_tabs(self, keep_index):
        """Close all tabs except the one at keep_index"""
        indices_to_close = [i for i in range(self.tabs.count()) if i != keep_index]

        for i in reversed(indices_to_close):
            if not self.close_tab(i):
                break

    def close_all_tabs(self):
        """Close all tabs"""
        while self.tabs.count() > 0:
            if not self.close_tab(0):
                break

    def save_tab(self, index):
        """Save the file in the tab at the given index"""
        editor = self.tabs.widget(index)
        if isinstance(editor, CodeEditor):
            if editor.save_file():
                editor.document().setModified(False)
                self.parent.on_editor_modified(editor)
                self.parent.status_message.setText("File saved")
                QTimer.singleShot(2000, lambda: self.parent.status_message.setText(""))
                return True
        return False

    def save_all_tabs(self):
        """Save all modified files"""
        saved_count = 0
        for i in range(self.tabs.count()):
            editor = self.tabs.widget(i)
            if isinstance(editor, CodeEditor) and editor.document().isModified():
                if editor.save_file():
                    editor.document().setModified(False)
                    self.parent.on_editor_modified(editor)
                    saved_count += 1

        if saved_count > 0:
            self.parent.status_message.setText(f"Saved {saved_count} file(s)")
            QTimer.singleShot(3000, lambda: self.parent.status_message.setText(""))
        else:
            self.parent.status_message.setText("No files to save")
            QTimer.singleShot(2000, lambda: self.parent.status_message.setText(""))

        return saved_count


    def send_tab_to_ollama(self, tab_index, send_all=False):
        """Send tab content to Ollama with smart context"""
        from ide.core.OllamaContext import OllamaContextBuilder
        
        editor = self.tabs.widget(tab_index)
        if not isinstance(editor, CodeEditor):
            return
    
        # Get context level from settings
        context_level = 'smart'
        if hasattr(self.parent, 'settings_manager'):
            context_level = self.parent.settings_manager.get('ollama_context_level', 'smart')
        
        # Build context
        context_builder = OllamaContextBuilder()
        context = context_builder.build_context(editor, level=context_level)
        
        # Get text to send
        if send_all:
            text_to_send = editor.toPlainText()
            text_type = "entire file"
            # For full file, update context
            context['selection'] = {
                'start_line': 1,
                'end_line': editor.blockCount(),
                'line_count': editor.blockCount(),
                'char_count': len(text_to_send),
                'text': text_to_send
            }
        else:
            cursor = editor.textCursor()
            if cursor.hasSelection():
                text_to_send = cursor.selectedText().replace('\u2029', '\n')
                text_type = "selected text"
            else:
                QMessageBox.warning(
                    self.parent,
                    "No Selection",
                    "Please select some text first, or use 'Send Entire File to Ollama'."
                )
                return
    
        if not text_to_send.strip():
            QMessageBox.warning(self.parent, "No Text", "No text to send.")
            return
    
        # Show context preview dialog
        from ide.core.OllamaContextDialog import OllamaContextDialog
        
        dialog = OllamaContextDialog(
            self.parent,
            context,
            context_builder,
            text_type
        )
        
        if dialog.exec() == QMessageBox.DialogCode.Accepted:
            # User confirmed, send with selected context level
            final_context_level = dialog.get_context_level()
            
            # Rebuild context with final level
            context = context_builder.build_context(editor, level=final_context_level)
            if send_all:
                context['selection'] = {
                    'start_line': 1,
                    'end_line': editor.blockCount(),
                    'line_count': editor.blockCount(),
                    'char_count': len(text_to_send),
                    'text': text_to_send
                }
            
            # Format full message
            context_text = context_builder.format_context(context, include_code=True)
            user_prompt = dialog.get_prompt()
            
            full_message = f"{user_prompt}\n\n{context_text}"
            
            self.parent.ollama_widget.send_text_message(full_message)
            self.parent.show_ollama_panel()
            self.parent.status_message.setText(f"Sent {len(text_to_send)} characters with context to Ollama")
            QTimer.singleShot(3000, lambda: self.parent.status_message.setText(""))


    # def send_tab_to_ollama(self, tab_index, send_all=False):
        # """Send tab content to Ollama"""
        # editor = self.tabs.widget(tab_index)
        # if not isinstance(editor, CodeEditor):
            # return

        # if send_all:
            # text_to_send = editor.toPlainText()
            # text_type = "entire file"
        # else:
            # cursor = editor.textCursor()
            # if cursor.hasSelection():
                # text_to_send = cursor.selectedText().replace('\u2029', '\n')
                # text_type = "selected text"
            # else:
                # QMessageBox.warning(
                    # self.parent,
                    # "No Selection",
                    # "Please select some text first, or use 'Send Entire File to Ollama'."
                # )
                # return

        # if not text_to_send.strip():
            # QMessageBox.warning(self.parent, "No Text", "No text to send.")
            # return

        # prompt, ok = QInputDialog.getText(
            # self.parent,
            # "Send to Ollama",
            # f"Enter your instruction for Ollama:\n(Sending {text_type}, {len(text_to_send)} characters)",
            # QLineEdit.EchoMode.Normal,
            # "Explain this code:"
        # )

        # if ok and prompt.strip():
            # full_message = f"{prompt}\n\n```\n{text_to_send}\n```"
            # self.parent.ollama_widget.send_text_message(full_message)
            # self.parent.show_ollama_panel()
            # self.parent.status_message.setText(f"Sent {len(text_to_send)} characters to Ollama")
            # QTimer.singleShot(3000, lambda: self.parent.status_message.setText(""))

    def get_current_editor(self):
        """Get the currently active editor"""
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, CodeEditor) else None

