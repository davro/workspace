# """
# Ollama AI Plugin for Workspace IDE

# Provides local AI assistance using Ollama:
# - Chat interface with model selection
# - Smart context generation (file info, function context, imports)
# - Send code/selection to AI with custom prompts
# - Quick prompt templates
# - Keyboard shortcuts
# - Tab context menu integration

# """

from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QInputDialog, QLineEdit, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer

# Import core Ollama components
from OllamaPlugin.OllamaChatWidget import OllamaChatWidget
from OllamaPlugin.OllamaContext import OllamaContextBuilder
from OllamaPlugin.OllamaContextDialog import OllamaContextDialog

from ide.core.CodeEditor import CodeEditor
from ide.core.SettingDescriptor import SettingsProvider, SettingDescriptor, SettingType


# ============================================================================
# OllamaPlugin - Now a SettingsProvider!
# ============================================================================

class OllamaPlugin(SettingsProvider):
    """
    Ollama AI Plugin - Local AI assistance for code
    
    Features:
    - Chat interface with Ollama models
    - Smart context generation from code
    - Send code/selection to AI
    - Quick prompt templates
    - Model management
    """
    
    # ========================================================================
    # Plugin Metadata (Required)
    # ========================================================================
    
    PLUGIN_NAME = "Ollama AI"
    PLUGIN_VERSION = "1.0.1"
    PLUGIN_DESCRIPTION = "Local AI assistance using Ollama"
    PLUGIN_RUN_ON_STARTUP = True
    PLUGIN_HAS_UI = True
    PLUGIN_ICON = "🤖"
    
    # ========================================================================
    # Settings Descriptors - Define plugin settings
    # ========================================================================
    SETTINGS_DESCRIPTORS = [
        SettingDescriptor(
            key='ollama_timeout',
            label='Ollama Request Timeout',
            setting_type=SettingType.INTEGER,
            default=240,
            min_value=30,
            max_value=1200,
            suffix=' seconds',
            description='Maximum time to wait for Ollama response',
            section='Ollama'
        ),
        SettingDescriptor(
            key='ollama_context_level',
            label='Ollama Context Level',
            setting_type=SettingType.CHOICE,
            default='smart',
            choices=[
                ('Minimal (file + language)', 'minimal'),
                ('Basic (+ line numbers)', 'basic'),
                ('Smart (+ function/class)', 'smart'),
            ],
            description='How much context to include when sending code to Ollama',
            section='Ollama'
        ),
        SettingDescriptor(
            key='ollama_show_context_dialog',
            label='Preview Context Before Send',
            setting_type=SettingType.BOOLEAN,
            default=True,
            description='Show preview dialog before sending to Ollama',
            section='Ollama'
        ),
    ]
    
    # ========================================================================
    # Initialization
    # ========================================================================
    
    def __init__(self, api):
        """Initialize Ollama plugin"""
        # NOTE: Don't call super().__init__() - SettingsProvider has no __init__
        
        self.api = api
        self.initialized = False
        
        # Components
        self.widget = None
        self.context_builder = OllamaContextBuilder()
        
        # State
        self.panel_visible = False
        
        print(f"[{self.PLUGIN_NAME}] Instance created")
    
    def initialize(self):
        """Initialize plugin"""
        if self.initialized:
            return
        
        print(f"[{self.PLUGIN_NAME}] Initializing...")
        
        # ====================================================================
        # CRITICAL: Register this plugin's settings with the IDE
        # ====================================================================
        if hasattr(self.api, 'register_settings_provider'):
            self.api.register_settings_provider(OllamaPlugin)
            print(f"[{self.PLUGIN_NAME}] Settings registered")
        else:
            print(f"[{self.PLUGIN_NAME}] WARNING: Cannot register settings (API doesn't support it)")
        
        # Register keyboard shortcuts
        self.api.register_keyboard_shortcut(
            'Ctrl+Shift+O',
            self.send_to_ollama,
            'Send to Ollama AI'
        )
        
        self.api.register_keyboard_shortcut(
            'Ctrl+L',
            self.toggle_ai_panel,
            'Toggle AI Panel'
        )
        
        # Create widget and add to right sidebar
        print(f"[{self.PLUGIN_NAME}] Creating widget...")
        widget = self.get_widget(self.api.ide)
        
        print(f"[{self.PLUGIN_NAME}] Adding to right sidebar...")
        success = self.api.add_to_right_sidebar(widget, "AI", "🤖")
        
        if success:
            print(f"[{self.PLUGIN_NAME}] Successfully added to sidebar")
        else:
            print(f"[{self.PLUGIN_NAME}] WARNING: Failed to add to sidebar")
        
        self.initialized = True
        self.api.show_status_message(f"{self.PLUGIN_NAME} ready", 2000)
        
        print(f"[{self.PLUGIN_NAME}] Initialized")
    
    def get_widget(self, parent=None):
        """Return plugin's UI widget"""
        self.widget = OllamaPluginWidget(self, parent)
        return self.widget
    
    def cleanup(self):
        """Cleanup plugin resources"""
        print(f"[{self.PLUGIN_NAME}] Cleaning up...")
        
        if self.api:
            self.api.unregister_all_plugin_hooks('ollama_plugin')
        
        self.initialized = False
        print(f"[{self.PLUGIN_NAME}] Cleaned up")
    
    # ========================================================================
    # Settings Access Helpers
    # ========================================================================
    
    def get_ollama_timeout(self) -> int:
        """Get Ollama timeout from settings"""
        settings = self.api.get_settings()
        return settings.get('ollama_timeout', 240)
    
    def get_context_level(self) -> str:
        """Get context level from settings"""
        settings = self.api.get_settings()
        return settings.get('ollama_context_level', 'smart')
    
    def should_show_context_dialog(self) -> bool:
        """Check if context dialog should be shown"""
        settings = self.api.get_settings()
        return settings.get('ollama_show_context_dialog', True)
    
    # ========================================================================
    # Core AI Actions
    # ========================================================================
    
    def send_to_ollama(self):
        """Send current editor content to Ollama with smart context"""
        print("[DEBUG] send_to_ollama called")
        
        editor = self.api.get_current_editor()
        print(f"[DEBUG] Got editor: {editor}")

        if not isinstance(editor, CodeEditor):
            QMessageBox.warning(
                None,
                "No Editor",
                "Please open a file first before sending to Ollama."
            )
            return
        
        # Determine what to send
        cursor = editor.textCursor()
        if cursor.hasSelection():
            text_type = "selected text"
        else:
            text_type = "entire file"
        
        # Build smart context using setting
        context_level = self.get_context_level()
        context = self.context_builder.build_context(editor, level=context_level)
        
        # Show context dialog if enabled in settings
        if self.should_show_context_dialog():
            if not self.widget:
                QMessageBox.warning(
                    None,
                    "Plugin Not Ready",
                    "Ollama plugin widget not initialized. Please open the AI panel first."
                )
                return
            
            dialog = OllamaContextDialog(
                self.api.ide,
                context,
                self.context_builder,
                text_type,
                self.widget.ollama_widget
            )
            
            if not dialog.exec():
                return  # User cancelled
            
            prompt = dialog.get_prompt()
            
            if not prompt.strip():
                return
        else:
            # Skip dialog, use default prompt
            prompt = "Please review this code:"
        
        # Format full message with context
        formatted_context = self.context_builder.format_context(
            context,
            include_code=True
        )
        
        full_message = f"{prompt}\n\n{formatted_context}"
        
        # Send to Ollama
        self.widget.ollama_widget.send_text_message(full_message)
        
        # Show AI panel if hidden
        self.show_ai_panel()
        
        # Status message
        selection = context.get('selection')
        if selection:
            char_count = selection['char_count']
        else:
            char_count = len(editor.toPlainText())
        
        self.api.show_status_message(
            f"Sent {char_count} characters to Ollama",
            3000
        )
    
    def send_code_to_ollama(self, code: str, prompt: str = "Explain this code:"):
        """Send code directly to Ollama (for programmatic use)"""
        if not self.widget:
            return
        
        full_message = f"{prompt}\n\n```\n{code}\n```"
        self.widget.ollama_widget.send_text_message(full_message)
        self.show_ai_panel()
    
    # ========================================================================
    # Panel Management
    # ========================================================================
    
    def toggle_ai_panel(self):
        """Toggle AI panel visibility"""
        is_visible = self.api.get_right_sidebar_visible()
        
        if is_visible:
            if hasattr(self.api.ide, 'right_sidebar'):
                current_index = self.api.ide.right_sidebar.currentIndex()
                ai_tab_index = -1
                for i in range(self.api.ide.right_sidebar.count()):
                    tab_text = self.api.ide.right_sidebar.tabText(i)
                    if 'AI' in tab_text or '🤖' in tab_text:
                        ai_tab_index = i
                        break
                
                if ai_tab_index >= 0 and current_index == ai_tab_index:
                    self.api.set_right_sidebar_visible(False)
                    self.panel_visible = False
                else:
                    self.api.ide.right_sidebar.setCurrentIndex(ai_tab_index)
                    self.panel_visible = True
        else:
            self.api.set_right_sidebar_visible(True)
            self.api.focus_right_sidebar_tab("AI")
            self.panel_visible = True
        
        status = "shown" if self.panel_visible else "hidden"
        self.api.show_status_message(f"AI panel {status}", 1000)
    
    def show_ai_panel(self):
        """Show AI panel"""
        self.api.set_right_sidebar_visible(True)
        self.api.focus_right_sidebar_tab("AI")
        self.panel_visible = True
    
    def hide_ai_panel(self):
        """Hide AI panel"""
        self.api.set_right_sidebar_visible(False)
        self.panel_visible = False


# ============================================================================
# Plugin UI Widget (unchanged)
# ============================================================================

class OllamaPluginWidget(QWidget):
    """Ollama Plugin UI Widget"""
    
    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Header
        header_layout = QHBoxLayout()
        header = QLabel(f"{self.plugin.PLUGIN_ICON} {self.plugin.PLUGIN_NAME}")
        header.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #4A9EFF;
            padding: 5px;
        """)
        header_layout.addWidget(header)
        header_layout.addStretch()
        
        # Quick send button
        send_file_btn = QPushButton("📄")
        send_file_btn.setToolTip("Send current file to AI (Ctrl+Shift+O)")
        send_file_btn.setMaximumWidth(35)
        send_file_btn.clicked.connect(self.plugin.send_to_ollama)
        send_file_btn.setStyleSheet("""
            QPushButton {
                padding: 4px;
                border: 1px solid #3C3F41;
                border-radius: 3px;
                background-color: #2B2B2B;
            }
            QPushButton:hover {
                background-color: #3C3F41;
                border-color: #4A9EFF;
            }
        """)
        header_layout.addWidget(send_file_btn)
        layout.addLayout(header_layout)
        
        # Info
        info = QLabel("Local AI powered by Ollama")
        info.setStyleSheet("color: #888; font-size: 10pt; padding: 2px 5px;")
        layout.addWidget(info)
        
        # Chat widget
        self.ollama_widget = OllamaChatWidget(parent=self)
        layout.addWidget(self.ollama_widget)
        
        # Quick prompts
        prompts_label = QLabel("<b>Quick Prompts:</b>")
        prompts_label.setStyleSheet("padding: 5px; color: #CCC;")
        layout.addWidget(prompts_label)
        
        quick_prompts_layout = QVBoxLayout()
        quick_prompts_layout.setSpacing(3)
        
        quick_prompts = [
            ("💡 Explain Code", "Explain this code:", "Send current file/selection for explanation"),
            ("🐛 Debug", "Find bugs:", "Analyze for bugs and issues"),
            ("📝 Document", "Add documentation:", "Generate documentation"),
            ("🔧 Refactor", "Suggest refactoring:", "Get refactoring suggestions"),
            ("⚡ Optimize", "Optimize performance:", "Get optimization tips"),
            ("✅ Tests", "Generate tests:", "Create unit tests"),
        ]
        
        for btn_text, prompt, tooltip in quick_prompts:
            btn = QPushButton(btn_text)
            btn.setToolTip(tooltip)
            btn.clicked.connect(lambda checked=False, p=prompt: self.quick_prompt(p))
            btn.setStyleSheet("""
                QPushButton {
                    text-align: left;
                    padding: 6px 10px;
                    border: 1px solid #3C3F41;
                    border-radius: 3px;
                    background-color: #2B2B2B;
                }
                QPushButton:hover {
                    background-color: #3C3F41;
                    border-color: #4A9EFF;
                }
            """)
            quick_prompts_layout.addWidget(btn)
        
        layout.addLayout(quick_prompts_layout)
        
        # Status
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #888; font-size: 9pt;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        
        hint = QLabel("Ctrl+Shift+O: Send to AI")
        hint.setStyleSheet("color: #666; font-size: 9pt; font-style: italic;")
        status_layout.addWidget(hint)
        layout.addLayout(status_layout)
    
    def quick_prompt(self, prompt: str):
        """Execute a quick prompt on current editor content"""
        editor = self.plugin.api.get_current_editor()
        
        if not isinstance(editor, CodeEditor):
            QMessageBox.warning(self, "No Editor", "Please open a file first.")
            return
        
        cursor = editor.textCursor()
        if cursor.hasSelection():
            code = cursor.selectedText().replace('\u2029', '\n')
            text_type = "selection"
        else:
            code = editor.toPlainText()
            text_type = "file"
        
        if not code.strip():
            QMessageBox.warning(self, "No Code", "No code to send.")
            return
        
        # Build context using setting
        context_level = self.plugin.get_context_level()
        context = self.plugin.context_builder.build_context(editor, level=context_level)
        formatted_context = self.plugin.context_builder.format_context(
            context,
            include_code=True
        )
        
        # Send to Ollama
        full_message = f"{prompt}\n\n{formatted_context}"
        self.ollama_widget.send_text_message(full_message)
        
        # Update status
        self.status_label.setText(f"Sent {text_type} to AI")
        QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))
