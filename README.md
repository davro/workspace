# Workspace IDE

A lightweight, feature-rich Python-based IDE built with PyQt6, designed for managing multiple projects in a single workspace with integrated AI assistance via Ollama.

![Python](https://img.shields.io/badge/python-3.12+-blue.svg)
![PyQt6](https://img.shields.io/badge/PyQt6-6.10.0-green.svg)
[![License: GPL v3](https://img.shields.io/badge/License-GPL%20v3-green.svg)](https://www.gnu.org/licenses/gpl-3.0)

## Features

### 🎯 Core IDE Features

- **Split View Editor**: 
  - Vertical and horizontal split views for side-by-side editing
  - Independent tab groups with drag-and-drop support
  - Move tabs between split groups (`Ctrl+Alt+M`)
  - Focus switching between groups (`Ctrl+Alt+O`)
  - All keyboard shortcuts work correctly in split view
- **Multi-File Editing**: Tabbed interface with syntax highlighting for Python and other languages
- **Line Numbers**: Toggle-able line numbers with current line highlighting
- **Project-Based Workflow**: Organize and activate specific projects within your workspace
- **File Explorer**: 
  - Tree view with context menus for file/folder operations
  - Unicode file icons (no image assets required)
  - Drag-and-drop file moving within the tree
  - Press Enter to open files
  - Project highlighting for active projects
- **Smart Tab Management**: 
  - Reorderable tabs with drag-and-drop
  - Middle-click to close tabs
  - Modified file indicators (● symbol)
  - Active tab highlighting
  - Full path tooltips on hover
  - Recent tab order switching (`Ctrl+Tab`)
  - Session persistence (reopens tabs on restart)

### 📋 Code Navigation

- **Outline Navigator**: Multi-language code structure view
  - Supports 12+ languages (Python, PHP, Go, Rust, JavaScript/TypeScript, Java, C/C++, Ruby, HTML, CSS, JSON)
  - Hierarchical view of classes, functions, methods
  - Click to jump to definition
  - Search/filter symbols
  - Auto-updates on tab switch
  - Works seamlessly with split view
- **Quick Open (Ctrl+P)**: Fuzzy file search across active projects
  - Intelligent scoring algorithm
  - Color-coded results by file type
  - Fast caching for instant subsequent opens
- **Go to Line (Ctrl+G)**: Jump directly to any line number
- **Recent Files (Ctrl+R)**: Quick access to recently opened files

### 🔍 Search & Replace

- **Find & Replace**: 
  - Fuzzy matching
  - Regular expression support
  - Case-sensitive and whole-word options
  - Find in selection
  - Replace all functionality
  - Match navigation (F3/Shift+F3)
  - Works independently in each split group

### 🤖 AI Integration

- **Ollama Chat**: Built-in AI assistance powered by Ollama
  - Support for multiple models
  - Configurable timeout settings
  - Model status monitoring (`ollama ps`)
  - Smart context-aware prompts
  - Send entire files or selections to AI
  - Context menu integration in tabs
- **AI Actions**:
  - Send entire file to Ollama (`Ctrl+Shift+O`)
  - Send selected text to Ollama
  - Custom prompts for code explanation, refactoring, etc.
  - Automatic project context inclusion
- **Intelligent Context**: AI receives relevant file context for better responses

### 💻 Editing Features

- **Comment/Uncomment** (`Ctrl+/`): Toggle line comments for multiple languages
- **Duplicate Line** (`Ctrl+D`): Duplicate current line or selection
- **Indent/Unindent** (`Tab`/`Shift+Tab`): Smart indentation
- **Auto-completion**: Context-aware code completion
- **Multiple Cursors**: Edit multiple locations simultaneously

### 📦 Project Management

- **Projects Panel**: Visual project activation/deactivation
  - Checkbox interface for selecting active projects
  - Quick Open searches only active projects
  - Project highlighting in file explorer
  - Persistent project selection across sessions

### ⚙️ Customization

- **Settings Dialog**:
  - Explorer width adjustment
  - Editor font size
  - Tab width (spaces)
  - Line number toggle
  - Gutter width configuration
  - Session restore options
  - Ollama timeout configuration

### 📊 Status Bar

- Real-time cursor position (Line, Column)
- File encoding (UTF-8)
- Line ending detection (LF/CRLF/CR)
- Language detection (20+ languages)
- Persistent status messages

### 📁 File Operations

- **Context Menus**:
  - Create new files/folders
  - Rename files/folders
  - Delete with confirmation
  - Open in editor
  - Copy file path (absolute/relative)
  - Drag and drop to move files/folders
- **Tab Context Menu**:
  - Save file
  - Close tab/Close others/Close all
  - Send to Ollama (entire or selection)
  - Copy file path

## Installation

### Prerequisites

- Python 3.12 or higher
- PyQt6

### Setup

```bash
# Clone the repository
git clone https://github.com/davro/workspace
cd workspace
```

Installation / first run
```bash
chmod +x ide.sh
./ide.sh
```

Usage section
```bash
./ide.sh                # Run (auto-install if needed)
./ide.sh install        # Force install
./ide.sh update         # Update dependencies
./ide.sh workspace.py   # Run alternate entry file
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

1. **Launch the IDE**: Run `./ide.sh`
2. **Default workspace**: `~/workspace` (created automatically if it doesn't exist)
3. **Activate projects**: Click the "📦 Projects" tab and check the projects you want to work on
4. **Open files**: Use the file explorer or Quick Open (Ctrl+P)
5. **Split view**: Press `Ctrl+\` for vertical split or `Ctrl+Shift+\` for horizontal split
6. **Code outline**: View code structure in the "📋 Outline" tab on the right

### Keyboard Shortcuts

#### File Operations
| Shortcut | Action |
|----------|--------|
| `Ctrl+N` | New File |
| `Ctrl+Shift+N` | New Folder |
| `Ctrl+P` | Quick Open (fuzzy file search) |
| `Ctrl+R` | Recent Files |
| `Ctrl+S` | Save current file |
| `Ctrl+Shift+S` | Save All |
| `Ctrl+W` | Close Tab |
| `Ctrl+Shift+W` | Close All Tabs |
| `Ctrl+Tab` | Tab Switcher (Recent Order) |
| `Ctrl+Shift+Tab` | Tab Switcher (Reverse) |
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
| `Ctrl+D` | Duplicate Line/Selection |
| `Ctrl+/` | Toggle Comment |

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
| `Ctrl+L` | Toggle AI Chat & Outline |
| `Ctrl+\` | Split Editor Vertically |
| `Ctrl+Shift+\` | Split Editor Horizontally |
| `Ctrl+Alt+W` | Close Split |

#### Split View Navigation
| Shortcut | Action |
|----------|--------|
| `Ctrl+Alt+M` | Move Tab to Other Group |
| `Ctrl+Alt+O` | Focus Other Group |
| `Ctrl+Alt+S` | Open in Split |

#### Navigation
| Shortcut | Action |
|----------|--------|
| `Ctrl+P` | Go to File |
| `Ctrl+G` | Go to Line |
| `Enter` | Open file (in File Explorer) |

#### Run
| Shortcut | Action |
|----------|--------|
| `F5` | Run Current File |

#### AI Features
| Shortcut | Action |
|----------|--------|
| `Ctrl+Shift+O` | Send to Ollama |

#### Help
| Shortcut | Action |
|----------|--------|
| `F1` | Documentation |
| `F2` | Changelog |
| `Ctrl+K Ctrl+S` | Keyboard Shortcuts |

### Split View Workflow

1. **Create Split**: Press `Ctrl+\` for vertical or `Ctrl+Shift+\` for horizontal split
2. **Move Tabs**: Press `Ctrl+Alt+M` to move current tab to other group
3. **Switch Focus**: Press `Ctrl+Alt+O` to focus the other editor group
4. **Open in Split**: Press `Ctrl+Alt+S` to open current file in the other group
5. **Close Split**: Press `Ctrl+Alt+W` to merge back to single editor

### Code Navigation

1. **View Outline**: Click the "📋 Outline" tab on the right sidebar
2. **Search Symbols**: Type in the search box to filter classes/functions
3. **Jump to Definition**: Click any symbol to jump to its location in the code
4. **Auto-Update**: Outline automatically updates when switching files or groups

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
5. View response in the "🤖 AI" tab with intelligent context

### File Management

- **Drag and Drop**: Drag files/folders to move them within the workspace
- **Enter to Open**: Navigate with arrow keys, press Enter to open files
- **Middle-Click**: Middle-click any tab to close it instantly
- **Recent Files**: Press `Ctrl+R` to see and open recently edited files

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

- **Split Editor Manager**: Manages multiple editor groups with independent tab sets
- **Outline Parser**: Multi-language code structure parser (Python AST + regex)
- **File Scanner**: Background threading for non-blocking file indexing
- **Syntax Highlighter**: Extensible highlighting system
- **Find & Replace**: Regex-capable search with scoring algorithm
- **Session Manager**: Persistent state across restarts
- **Tab Order Manager**: Intelligent tab switching based on recent usage

### Supported Languages (Outline)

- Python (classes, functions, methods - AST-based)
- PHP (classes, functions)
- Go (structs, interfaces, functions)
- Rust (structs, enums, traits, functions)
- JavaScript/TypeScript (classes, functions, arrow functions)
- Java (classes, interfaces, methods)
- C/C++ (structs, classes, functions)
- Ruby (classes, modules, methods)
- HTML (tags with IDs)
- CSS/SCSS (selectors)
- JSON (top-level keys)

## Roadmap

### Recently Completed ✅

- ✅ Split view (side-by-side editing)
- ✅ Drag-and-drop file moving
- ✅ Unicode file icons
- ✅ Middle-click to close tabs
- ✅ Multi-language outline navigator
- ✅ Comment/uncomment with proper indentation
- ✅ Duplicate line/selection
- ✅ Tab switcher with recent order
- ✅ Recent files menu
- ✅ Enter key to open files in tree

### Planned Features

- [ ] Minimap for code overview
- [ ] Additional syntax highlighting (more languages)
- [ ] Auto-save functionality
- [ ] Move line up/down
- [ ] Multi-cursor support
- [ ] Code folding
- [ ] Git integration
- [ ] Extensions system
- [ ] Themes support
- [ ] Debug console integration
- [ ] Breadcrumb navigation
- [ ] Symbol search across project
- [ ] Advanced refactoring tools

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development Setup

```bash
# Fork and clone the repository
git clone https://github.com/yourusername/workspace-ide.git

# Create a feature branch
git checkout -b feature/amazing-feature

# Make your changes and test
python workspace.py

# Commit and push
git commit -m "Add amazing feature"
git push origin feature/amazing-feature
```

## License

This project is licensed under the GPL v3 License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [PyQt6](https://www.riverbankcomputing.com/software/pyqt/)
- AI integration powered by [Ollama](https://ollama.ai)
- Inspired by modern IDEs like Cursor, VS Code, and PyCharm

## Screenshots

### Main Interface
The IDE features a clean, dark-themed interface with:
- File explorer with Unicode icons
- Split view editor support
- Code outline navigator
- Integrated AI chat

### Split View Editing
Work on multiple files side-by-side with independent tab groups and synchronized features.

### Code Outline
Navigate large files easily with the hierarchical code structure view supporting 12+ languages.

### AI Integration
Send code directly to Ollama with intelligent context for explanations, refactoring, and assistance.

## Support

For issues, questions, or feature requests, please [open an issue](https://github.com/davro/workspace/issues) on GitHub.

---

**Built with ❤️ for developers who want a lightweight, AI-enhanced IDE with modern productivity features**
