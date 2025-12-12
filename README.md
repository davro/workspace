# Workspace IDE

A lightweight, Python-based IDE built with PyQt6, designed for managing multiple projects in a single workspace with integrated AI assistance via Ollama.

![Python](https://img.shields.io/badge/python-3.12+-blue.svg)
![PyQt6](https://img.shields.io/badge/PyQt6-6.10.0-green.svg)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

## Features

### 🎯 Core IDE Features

- **Multi-File Editing**: Tabbed interface with syntax highlighting for Python and other languages
- **Line Numbers**: Toggle-able line numbers with current line highlighting
- **Project-Based Workflow**: Organize and activate specific projects within your workspace
- **File Explorer**: Tree view with context menus for file/folder operations
- **Smart Tab Management**:
  - Reorderable tabs with drag-and-drop
  - Modified file indicators (● symbol)
  - Active tab highlighting
  - Full path tooltips on hover
  - Session persistence (reopens tabs on restart)

### 🔍 Search & Navigation

- **Quick Open (Ctrl+P)**: Fuzzy file search across active projects
  - Intelligent scoring algorithm
  - Color-coded results by file type
  - Fast caching for instant subsequent opens
- **Find & Replace**:
  - Fuzzy matching
  - Regular expression support
  - Case-sensitive and whole-word options
  - Find in selection
  - Replace all functionality
  - Match navigation (F3/Shift+F3)

### 🤖 AI Integration

- **Ollama Chat**: Built-in AI assistance powered by Ollama
  - Support for multiple models
  - Configurable timeout settings
  - Model status monitoring (`ollama ps`)
  - Send entire files or selections to AI
  - Context menu integration in tabs
- **AI Actions**:
  - Send entire file to Ollama
  - Send selected text to Ollama
  - Custom prompts for code explanation, refactoring, etc.

### 💻 Terminal

- **Integrated Terminal**: Simple command execution environment
  - Command history (up/down arrows)
  - Current directory tracking
  - Built-in commands (cd, pwd, clear)
  - Suitable for basic shell operations

### 📦 Project Management

- **Projects Panel**: Visual project activation/deactivation
  - Checkbox interface for selecting active projects
  - Quick Open searches only active projects
  - Project highlighting in file explorer
  - Persistent project selection across sessions

### ⚙️ Customization

- **Settings Dialog**:
  - Explorer width adjustment
  - Terminal height configuration
  - Editor font size
  - Terminal font size
  - Tab width (spaces)
  - Line number toggle
  - Auto-save options
  - Ollama timeout configuration

### 📊 Status Bar

- Real-time cursor position (Line, Column)
- File encoding (UTF-8)
- Line ending detection (LF/CRLF/CR)
- Language detection (20+ languages)
- Persistent status messages

### 📝 File Operations

- **Context Menus**:
  - Create new files/folders
  - Rename files/folders
  - Delete with confirmation
  - Open in editor
- **Tab Context Menu**:
  - Save file
  - Close tab/Close others/Close all
  - Send to Ollama (entire or selection)

## Installation

### Prerequisites

- Python 3.12 or higher
- PyQt6

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/workspace-ide.git
cd workspace-ide
test
# Create virtual environment
python -m venv workspace-env
source workspace-env/bin/activate  # On Windows: workspace-env\Scripts\activate

# Install dependencies
pip install PyQt6

# Run the IDE
python workspace_ide.py
```

### Optional: Ollama Integration

To use the AI features, install [Ollama](https://ollama.ai):

```bash
# Install Ollama (see https://ollama.ai for platform-specific instructions)

# Pull a model (e.g., llama3)
ollama pull llama3

# The IDE will automatically detect installed models
```

## Usage

### Quick Start

1. **Launch the IDE**: Run `python workspace_ide.py`
2. **Default workspace**: `~/workspace` (created automatically if it doesn't exist)
3. **Activate projects**: Click the "📦 Projects" tab and check the projects you want to work on
4. **Open files**: Use the file explorer or Quick Open (Ctrl+P)

### Keyboard Shortcuts

#### File Operations
| Shortcut | Action |
|----------|--------|
| `Ctrl+N` | New File |
| `Ctrl+Shift+N` | New Folder |
| `Ctrl+P` | Quick Open (fuzzy file search) |
| `Ctrl+S` | Save current file |
| `Ctrl+Shift+S` | Save All |
| `Ctrl+W` | Close Tab |
| `Ctrl+Shift+W` | Close All Tabs |
| `Ctrl+,` | Preferences |
| `Ctrl+Q` | Exit |

#### Edit Operations
| Shortcut | Action |
|----------|--------|
| `Ctrl+Z` | Undo |
| `Ctrl+Shift+Z` | Redo |
| `Ctrl+X` | Cut |
| `Ctrl+C` | Copy |
| `Ctrl+V` | Paste |
| `Ctrl+A` | Select All |

#### Search & Replace
| Shortcut | Action |
|----------|--------|
| `Ctrl+F` | Find & Replace |
| `Ctrl+H` | Replace |
| `F3` | Find Next |
| `Shift+F3` | Find Previous |

#### View
| Shortcut | Action |
|----------|--------|
| `Ctrl+B` | Toggle Explorer |
| `Ctrl+\`` | Toggle Terminal |

#### Navigation
| Shortcut | Action |
|----------|--------|
| `Ctrl+P` | Go to File |
| `Ctrl+G` | Go to Line |

#### Run
| Shortcut | Action |
|----------|--------|
| `F5` | Run Current File |

#### Terminal
| Shortcut | Action |
|----------|--------|
| `Ctrl+Shift+\`` | New Terminal |

#### AI Features
| Shortcut | Action |
|----------|--------|
| `Ctrl+Shift+O` | Send to Ollama |

#### Help
| Shortcut | Action |
|----------|--------|
| `F1` | Documentation |
| `Ctrl+K Ctrl+S` | Keyboard Shortcuts |

### Project Workflow

1. **Organize**: Place your projects as directories in `~/workspace/`
2. **Activate**: Open the "📦 Projects" tab and check the projects you're working on
3. **Search**: Press `Ctrl+P` to search files only in active projects
4. **Visual Feedback**: Active projects are highlighted in green in the file explorer

### AI-Assisted Development

1. **Select code** in the editor (or don't select for entire file)
2. **Right-click on the tab** → "🤖 AI Actions"
3. Choose "Send Entire File" or "Send Selection"
4. Enter your prompt (e.g., "Explain this code", "Find bugs", "Add comments")
5. View response in the "Ollama Chat" tab

## Configuration Files

The IDE stores configuration in your workspace directory:

- `~/.workspace/.workspace_ide_config.json` - Settings and active projects
- `~/.workspace/.workspace_ide_session.json` - Open tabs and window state

## Architecture

### Technology Stack

- **UI Framework**: PyQt6
- **Language**: Python 3.12+
- **AI Backend**: Ollama (optional)

### Key Components

- **Main Window**: Tabbed sidebar (Files/Projects) + Editor + Terminal/Ollama
- **File Scanner**: Background threading for non-blocking file indexing
- **Syntax Highlighter**: Extensible highlighting system
- **Find & Replace**: Regex-capable search with scoring algorithm
- **Session Manager**: Persistent state across restarts

## Roadmap

### Planned Features

- [ ] Additional syntax highlighting (JavaScript, TypeScript, HTML, CSS, etc.)
- [ ] Auto-save functionality
- [ ] Duplicate line / Move line up/down
- [ ] Multi-cursor support
- [ ] Code folding
- [ ] Split view (side-by-side editing)
- [ ] Git integration
- [ ] Extensions system
- [ ] Themes support
- [ ] Debug console integration

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development Setup

```bash
# Fork and clone the repository
git clone https://github.com/yourusername/workspace-ide.git

# Create a feature branch
git checkout -b feature/amazing-feature

# Make your changes and test
python workspace_ide.py

# Commit and push
git commit -m "Add amazing feature"
git push origin feature/amazing-feature
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [PyQt6](https://www.riverbankcomputing.com/software/pyqt/)
- AI integration powered by [Ollama](https://ollama.ai)
- Inspired by modern IDEs like Cursor, VS Code, and PyCharm

## Screenshots

### Main Interface
The IDE features a clean, dark-themed interface with a file explorer, project management, and integrated terminal.

### Quick Open
Fast fuzzy file searching across active projects with intelligent scoring.

### AI Integration
Send code directly to Ollama for explanations, refactoring, and assistance.

## Support

For issues, questions, or feature requests, please [open an issue](https://github.com/yourusername/workspace-ide/issues) on GitHub.

---

**Built with ❤️ for developers who want a lightweight, AI-enhanced IDE**
