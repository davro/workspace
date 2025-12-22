"""
Create new file: ide/core/OllamaContextDialog.py
Dialog to preview and customize context before sending
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QComboBox, QPushButton, QCheckBox, QGroupBox
)
from PyQt6.QtCore import Qt


class OllamaContextDialog(QDialog):
    """
    Dialog to preview context and customize before sending to Ollama
    
    Shows:
    - User prompt input
    - Model selector (synced with Ollama widget)
    - Context level selector
    - Context preview
    - Token count estimate
    """
    
    def __init__(self, parent, context, context_builder, text_type, ollama_widget):
        super().__init__(parent)
        
        self.context = context
        self.context_builder = context_builder
        self.text_type = text_type
        self.ollama_widget = ollama_widget  # Reference to OllamaChatWidget
        
        self.setWindowTitle("Send to Ollama with Context")
        self.setMinimumWidth(700)
        self.setMinimumHeight(550)
        
        self.setup_ui()
        self.update_preview()
    
    def setup_ui(self):
        """Setup the UI"""
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel(f"<b>Sending {self.text_type} to Ollama</b>")
        title.setStyleSheet("font-size: 14px; padding: 5px;")
        layout.addWidget(title)
        
        # Model selector
        model_group = QGroupBox("Model Selection")
        model_layout = QHBoxLayout(model_group)
        
        model_layout.addWidget(QLabel("Model:"))
        
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(200)
        
        # Populate with models from Ollama widget
        self.sync_models_from_ollama()
        
        model_layout.addWidget(self.model_combo)
        
        # Refresh button
        refresh_btn = QPushButton("🔄")
        refresh_btn.setToolTip("Refresh model list")
        refresh_btn.setMaximumWidth(40)
        refresh_btn.clicked.connect(self.refresh_models)
        model_layout.addWidget(refresh_btn)
        
        model_layout.addStretch()
        layout.addWidget(model_group)
        
        # Smart Prompt Buttons
        prompt_buttons_layout = QHBoxLayout()
        prompt_buttons_layout.addWidget(QLabel("<b>Quick Prompts:</b>"))
        
        quick_prompts = [
            ("💡 Explain", "Explain this code in detail:"),
            ("🐛 Debug", "Find and explain any bugs or issues in this code:"),
            ("📝 Document", "Add comprehensive documentation and comments to this code:"),
            ("🔧 Refactor", "Suggest refactoring improvements for this code:"),
            ("⚡ Optimize", "Suggest performance optimizations for this code:"),
            ("✅ Tests", "Generate unit tests for this code:"),
            ("📖 Expand", "Provide more detailed information about this code:")
        ]
        
        for emoji_text, prompt_text in quick_prompts:
            btn = QPushButton(emoji_text)
            btn.setToolTip(prompt_text)
            btn.clicked.connect(lambda checked=False, p=prompt_text: self.set_prompt(p))
            btn.setStyleSheet("""
                QPushButton {
                    padding: 4px 8px;
                    border: 1px solid #3C3F41;
                    border-radius: 3px;
                    background-color: #2B2B2B;
                }
                QPushButton:hover {
                    background-color: #3C3F41;
                    border-color: #4A9EFF;
                }
            """)
            prompt_buttons_layout.addWidget(btn)
        
        prompt_buttons_layout.addStretch()
        layout.addLayout(prompt_buttons_layout)
        
        # Prompt input
        prompt_label = QLabel("Your prompt:")
        layout.addWidget(prompt_label)
        
        self.prompt_input = QLineEdit()
        self.prompt_input.setText(self.load_last_prompt())
        self.prompt_input.setPlaceholderText("What would you like Ollama to do?")
        layout.addWidget(self.prompt_input)
        
        # Context level selector with presets
        context_group = QGroupBox("Context Settings")
        context_layout = QVBoxLayout(context_group)
        
        # Template presets
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("Templates:"))
        
        presets = [
            ("🐛 Bug Hunter", "minimal", "Find and fix bugs:"),
            ("📚 Documentor", "smart", "Add documentation:"),
            ("🔄 Refactorer", "smart", "Suggest refactoring:")
        ]
        
        for preset_name, level, prompt in presets:
            btn = QPushButton(preset_name)
            btn.setToolTip(f"Context: {level.title()}, Prompt: {prompt}")
            btn.clicked.connect(lambda checked=False, l=level, p=prompt: self.apply_preset(l, p))
            btn.setStyleSheet("""
                QPushButton {
                    padding: 3px 8px;
                    border: 1px solid #3C3F41;
                    border-radius: 3px;
                    background-color: #2B2B2B;
                    font-size: 9pt;
                }
                QPushButton:hover {
                    background-color: #3C3F41;
                }
            """)
            preset_layout.addWidget(btn)
        
        preset_layout.addStretch()
        context_layout.addLayout(preset_layout)
        
        # Context level selector
        level_layout = QHBoxLayout()
        level_layout.addWidget(QLabel("Level:"))
        
        self.context_combo = QComboBox()
        self.context_combo.addItem("Minimal (file + language)", "minimal")
        self.context_combo.addItem("Basic (+ line numbers)", "basic")
        self.context_combo.addItem("Smart (+ function/class context)", "smart")
        
        # Load last used context level
        last_level = self.load_last_context_level()
        for i in range(self.context_combo.count()):
            if self.context_combo.itemData(i) == last_level:
                self.context_combo.setCurrentIndex(i)
                break
        
        self.context_combo.currentIndexChanged.connect(self.update_preview)
        level_layout.addWidget(self.context_combo)
        level_layout.addStretch()
        
        context_layout.addLayout(level_layout)
        layout.addWidget(context_group)
        
        # Context preview
        preview_layout = QHBoxLayout()
        preview_label = QLabel("Context preview:")
        preview_layout.addWidget(preview_label)
        preview_layout.addStretch()
        
        # Copy context button
        copy_btn = QPushButton("📋 Copy Context")
        copy_btn.setToolTip("Copy context to clipboard without sending")
        copy_btn.clicked.connect(self.copy_context_to_clipboard)
        copy_btn.setStyleSheet("""
            QPushButton {
                padding: 3px 10px;
                border: 1px solid #3C3F41;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #3C3F41;
            }
        """)
        preview_layout.addWidget(copy_btn)
        
        layout.addLayout(preview_layout)
        
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #A9B7C6;
                border: 1px solid #3C3F41;
                font-family: 'Courier New', monospace;
                font-size: 10pt;
            }
        """)
        layout.addWidget(self.preview_text)
        
        # Token count estimate
        self.token_label = QLabel()
        self.token_label.setStyleSheet("color: #888; font-size: 10pt;")
        layout.addWidget(self.token_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        send_btn = QPushButton("Send to Ollama")
        send_btn.setDefault(True)
        send_btn.setStyleSheet("""
            QPushButton {
                background-color: #4A9EFF;
                color: white;
                padding: 6px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5AAFFF;
            }
        """)
        send_btn.clicked.connect(self.accept)
        button_layout.addWidget(send_btn)
        
        layout.addLayout(button_layout)
    
    def set_prompt(self, prompt_text: str):
        """Set the prompt text from quick button"""
        self.prompt_input.setText(prompt_text)
        self.prompt_input.setFocus()
        self.update_preview()
    
    def apply_preset(self, level: str, prompt: str):
        """Apply a context template preset"""
        # Set context level
        for i in range(self.context_combo.count()):
            if self.context_combo.itemData(i) == level:
                self.context_combo.setCurrentIndex(i)
                break
        
        # Set prompt
        self.prompt_input.setText(prompt)
        self.update_preview()
    
    def copy_context_to_clipboard(self):
        """Copy the formatted context to clipboard"""
        from PyQt6.QtWidgets import QApplication
        
        context_text = self.preview_text.toPlainText()
        clipboard = QApplication.clipboard()
        clipboard.setText(context_text)
        
        # Show confirmation
        original_text = self.token_label.text()
        self.token_label.setText("✓ Context copied to clipboard")
        self.token_label.setStyleSheet("color: #4A9EFF; font-size: 10pt;")
        
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: (
            self.token_label.setText(original_text),
            self.token_label.setStyleSheet("color: #888; font-size: 10pt;")
        ))
    
    def load_last_prompt(self) -> str:
        """Load last used prompt from settings"""
        # Try to get from parent's settings
        if hasattr(self.parent(), 'settings_manager'):
            return self.parent().settings_manager.get('last_ollama_prompt', 'Explain this code:')
        return 'Explain this code:'
    
    def load_last_context_level(self) -> str:
        """Load last used context level from settings"""
        if hasattr(self.parent(), 'settings_manager'):
            return self.parent().settings_manager.get('ollama_context_level', 'smart')
        return 'smart'
    
    def save_last_settings(self):
        """Save current settings for next time"""
        if hasattr(self.parent(), 'settings_manager'):
            settings = self.parent().settings_manager
            settings.set('last_ollama_prompt', self.prompt_input.text())
            settings.set('ollama_context_level', self.context_combo.currentData())
            settings.save()
    
    def sync_models_from_ollama(self):
        """Sync model list from Ollama widget"""
        self.model_combo.clear()
        
        # Copy all models from Ollama widget
        for i in range(self.ollama_widget.model_box.count()):
            model_name = self.ollama_widget.model_box.itemText(i)
            self.model_combo.addItem(model_name)
        
        # Set current selection to match Ollama widget
        current_model = self.ollama_widget.model_box.currentText()
        index = self.model_combo.findText(current_model)
        if index >= 0:
            self.model_combo.setCurrentIndex(index)
    
    def refresh_models(self):
        """Refresh model list from Ollama"""
        # Call refresh on Ollama widget
        self.ollama_widget.refresh_models()
        
        # Re-sync our combo box
        self.sync_models_from_ollama()
        
        # Show brief confirmation
        original_text = self.token_label.text()
        self.token_label.setText("✓ Models refreshed")
        self.token_label.setStyleSheet("color: #4A9EFF; font-size: 10pt;")
        
        # Reset after 2 seconds
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: (
            self.token_label.setText(original_text),
            self.token_label.setStyleSheet("color: #888; font-size: 10pt;")
        ))
    
    def update_preview(self):
        """Update the context preview"""
        level = self.context_combo.currentData()
        
        # Rebuild context with selected level
        # (In real implementation, you'd call context_builder.build_context again)
        # For now, just format what we have
        preview_text = self.context_builder.format_context(
            self.context,
            include_code=True
        )
        
        self.preview_text.setPlainText(preview_text)
        
        # Estimate token count (rough: ~4 chars per token)
        char_count = len(preview_text) + len(self.prompt_input.text())
        token_estimate = char_count // 4
        
        self.token_label.setText(
            f"Estimated size: ~{token_estimate} tokens "
            f"({char_count} characters)"
        )
    
    def get_prompt(self) -> str:
        """Get the user's prompt"""
        return self.prompt_input.text().strip()
    
    def get_context_level(self) -> str:
        """Get selected context level"""
        return self.context_combo.currentData()
    
    def get_selected_model(self) -> str:
        """Get the selected model"""
        return self.model_combo.currentText()
    
    def accept(self):
        """Override accept to sync model selection back to Ollama widget and save settings"""
        # Update Ollama widget's model selection to match dialog
        selected_model = self.get_selected_model()
        index = self.ollama_widget.model_box.findText(selected_model)
        if index >= 0:
            self.ollama_widget.model_box.setCurrentIndex(index)
        
        # Save settings for next time
        self.save_last_settings()
        
        super().accept()
