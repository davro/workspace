# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [0.0.1] Phase 1 - 2025-12-11

### Added

- Fix: tab width is being set incorrectly
  Calculate the actual pixel width of a space character and multiplies it by desired 
  tab width (4), so 4 spaces will exactly equal 1 tab visually.

- Feature Documentation
  DocumentationDialog Class - A new dialog that:
    Reads the README.md file from ~/workspace/README.md
    Converts markdown to HTML with proper styling
    Displays it in a dark-themed, readable format
    Has syntax highlighting for code blocks
    Styled headers, lists, links, tables, etc.
  Menu Integration:
    Added "📖 Documentation" to the Help menu
    Keyboard shortcut: F1 (standard for help/documentation)
    Shows an error message if README.md doesn't exist
  Markdown Rendering:
    Headers (h1, h2, h3)
    Bold and italic text
    Inline code and code blocks
    Links
    Lists (ordered and unordered)
    Blockquotes
    Tables
    Horizontal rules

- Feature Persist Selected Projects
  Already working, but improved:
  Active projects saved to ~/.workspace/.workspace_ide_config.json
  Automatically saved when:
  You toggle a project checkbox
  You close the IDE
  Automatically restored when you reopen the IDE
  Single workspace config file stores all settings including projects

- Active Project Highlighting
  What You'll See:
  In the Files Tab (📁):
  Active projects: Dark green background (#2D5A2D) with light green bold text (#7FFF7F)
  Inactive projects: Normal gray/white appearance
  Updates instantly when you check/uncheck projects
  Once a project is selected it is included in Feature Quick Open File

- Feature Project-Based Architecture
  Left Sidebar - Two Tabs:
  📁 Files Tab:
  Traditional tree view of entire workspace
  Browse all files and folders
  Right-click context menus work as before
  📦 Projects Tab:
  Shows all top-level directories in workspace
  Checkboxes to activate/deactivate projects
  Only active projects are searched by Quick Open
  Shows "X of Y projects active" at bottom
  Refresh button (↻) to rescan

- Feature Quick Open File
  How to Use: Press Ctrl+P anywhere in the IDE
  Features:

  1. Fuzzy Matching
  Type part of filename: wspc matches workspace.py
  Characters must appear in order but don't need to be consecutive
  Intelligent scoring prioritizes better matches

  2. Smart Scoring
  Exact substring: Highest priority (e.g., "work" in "workspace.py")
  Consecutive characters: Bonus points
  Start of words: Matches at word boundaries score higher
  Shorter paths: Files in current directory ranked higher

  3. Color-Coded Results
  🟡 Python (.py) - Yellow/Gold
  🟠 JavaScript/TypeScript - Orange
  🔴 HTML/CSS - Red/Orange
  🟣 Config files (JSON, YAML, TOML) - Purple
  🔵 Markdown/Text - Blue
  ⚪ Others - Default

  4. Smart Filtering
  Ignores: .git, __pycache__, node_modules, virtual envs
  Skips: .pyc, .pyo, compiled files
  Shows up to 100 matches at a time

  5. Keyboard Navigation
  Type to filter instantly
  ↑↓ to navigate results
  Enter to open selected file
  Esc to cancel
  Double-click to open

- Feature Ollama 
  1. Configurable Timeout in Settings
  Setting: "Ollama Timeout" (30-600 seconds, default 180 = 3 minutes)
  Saved in your config file
  Applied to all Ollama requests
  Perfect for large models that take time to load into memory

  2. "Show Loaded Models" Button
  New button in Ollama tab: "Show Loaded Models"
  Runs ollama ps to show which models are currently in memory
  Displays output directly in chat
  Shows model name, size, and when it was loaded
  Helps you know if a model needs to load (which causes the timeout)

  3. Status Indicator
  Shows current state in top-right of Ollama tab:
  ✓ Ready - Idle, ready for requests
  ⏳ Waiting... - Currently processing
  ✗ Error - Last request failed

- Feature Line Status Bar Information (Bottom Right)
  Shows key pieces of info:
  Ln X, Col Y - Current cursor position (updates live as you type/move)
  UTF-8 - File encoding
  LF/CRLF/CR - Line ending type (auto-detected from file)
  Language - Detected from file extension

- Feature Line Numbers
  Displayed in left gutter with dark gray background
  Automatically adjusts width based on line count
  Current line highlighted with subtle background
  Can be toggled in Settings

- Feature Find & Replace 
  Keyboard Shortcuts:
  Ctrl+F - Open Find/Replace panel
  Ctrl+H - Open Find/Replace panel (alternate)
  F3 - Find Next
  Shift+F3 - Find Previous
  Enter in Find box - Find Next
  Enter in Replace box - Replace Current

- Feature Per-Tab Ollama Buttons
  Right click tab "Send to Ollama" button in toolbar
  Tab right click AI Actions (Submenu):
  Send Entire File to Ollama - Sends all content from that tab
  Send Selection to Ollama - Sends only selected text (prompts to select if nothing selected)

- Feature: Explorer Context Menu Features
  Right-click on a Folder:
  📄 New File   - Create a new file in this folder (auto-opens it)
  📁 New Folder - Create a new subfolder
  ✏️ Rename     - Rename the folder
  🗑️ Delete     - Delete the folder and all contents (with confirmation)

  Right-click on a File:
  📂 Open   - Open the file in editor
  ✏️ Rename - Rename the file (auto-closes/reopens if open)
  🗑️ Delete - Delete the file (with confirmation, auto-closes tab if open)

  Right-click on Empty Space:
  📁 New Folder... - Create folder in workspace root
  📄 New File... - Create file in workspace root

  Smart Features:
  Auto-close tabs when deleting/renaming:
  If you delete or rename an open file, its tab automatically closes
  When renaming, the file reopens with the new name

- Feature: Send to Ollama
  ✅ Works with selected text or entire file
  ✅ Keyboard shortcut: Ctrl+Shift+O
  ✅ Default prompt suggestions
  ✅ Auto-switches to Ollama tab
  ✅ Shows character count
  ✅ Non-blocking (runs in background thread)

- Feature: Tab Reordering Feature
  ✅ Drag and drop tabs - Set self.tabs.setMovable(True) to enable reordering
  ✅ Order is saved - When you close the IDE, tab order is preserved in session file
  ✅ Order is restored - Tabs reopen in the exact order you arranged them

- Feature: Settings Panel new settings dialog (click "Preferences" in File toolbar) Ctrl+, 
  ✅ Settings saved to .workspace_ide_config.json Both files load automatically on startup
  ✅ Some changes apply immediately, others need restart

- Feature: Session Persistence open tabs are now remembered:
  ✅ Session saved to .workspace_ide_session.json

- Ollama chat integration on bottom tab 
- Terminal implementation has limitations. For a proper terminal, we'd need a full terminal emulator library.
- Fzf integration for fuzzy file finding

- Phase 1 Core Functionality:
  Basic text editing capabilities
  Button to activate environment per project
  Environment management via build.sh with visual indicator (maybe a colored dot/icon showing active/inactive state)
  Tab-based file editor (top tabs, center content) with basic syntax highlighting
  PyQt6 file/project explorer (left panel) showing ~/workspace

- Define technologies and basic description of the project
  Python, Qt6, markdown, pip, bash
  Project workspace a lightweight, Python-focused IDE that solves a real pain point 
  the constant context switching and virtual environment management that comes with 
  working across multiple Python projects.
