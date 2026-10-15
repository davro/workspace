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
- **Code Intelligence** (plugin, right sidebar): Project-wide symbol index and navigation
  - **Jump to Definition** (`Ctrl+Shift+G`): ranked using the current file's imports, with a pick-menu when several definitions are equally likely
  - **Find All References** (`Ctrl+Shift+R`): results grouped by file in the *Refs* tab, marked as definition / reference / comment / string, click to jump
  - **Quick Symbol Search** (`Ctrl+T`): fuzzy search across every indexed class, function and method
  - **Symbols tab**: tree of the current file that follows the active editor tab
  - Uses the live editor text, so unsaved edits are included in jumps and reference searches
  - Indexes Python (AST), PHP and Go in a background thread; re-indexes on save and indexes files on demand
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
7. **Code intelligence**: Use the "🧠 Code Intel" tab on the right, then `Ctrl+Shift+G` to jump to a definition or `Ctrl+Shift+R` to list references

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
| `Ctrl+T` | Quick Symbol Search (Code Intelligence) |
| `Ctrl+Shift+G` | Jump to Definition (Code Intelligence) |
| `Ctrl+Shift+R` | Find All References (Code Intelligence) |
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

### Code Intelligence

1. **Index**: Activate your projects, then open the "🧠 Code Intel" tab (*Index* sub-tab). The first run indexes active projects in the background; use *Index Active Projects* or *Clear & Rebuild Index* to refresh by hand
2. **Jump to Definition**: Put the cursor on (or select) a name and press `Ctrl+Shift+G`. On an `import` line it prefers the module you are importing from
3. **Find References**: Press `Ctrl+Shift+R`. The *Refs* tab lists every whole-word match grouped by file; untick *Include comments & strings* to cut noise, and click a row to jump to it
4. **Search Symbols**: Press `Ctrl+T` and type part of a class, function or method name
5. **Browse a File**: The *Symbols* tab shows the current file's classes and methods; click one to jump

> References are matched by name, not by scope, so two unrelated methods with the same name will both be listed. See the roadmap for scope-aware references.

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
- **Code Intelligence Plugin**: Symbol database (name/file/qualified-name indexes with a JSON cache), AST-based Python indexer, ranked definition lookup, whole-word reference tracker and the sidebar panels (`ide/plugins/Codeintelligence/`)

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

Workspace is evolving into a lightweight, extensible development environment with local AI assistance and a project-centred workflow. 
Features below are grouped by their current status.

### Implemented

- [x] **Split Editor** — vertical and horizontal layouts, independent tab groups, and moving tabs between groups.
- [x] **Project Management** — activate projects and focus file searches on the projects you're working on.
- [x] **File Explorer** — create, rename, move, and delete files and folders, with deleted items sent to the system Trash.
- [x] **Session Persistence** — restore open tabs and preserve workspace state between sessions.
- [x] **Quick Open** — fuzzy file search with `Ctrl+P`, plus recent-file navigation.
- [x] **Code Outline** — navigate classes, functions, methods, and other supported symbols across multiple languages.
- [x] **Code Intelligence** — project-wide symbol index, jump to definition, quick symbol search, and find all references in a right-sidebar panel.
- [x] **Search and Replace** — regex support, matching options, and navigation through results.
- [x] **Editor Productivity** — line numbers, comment/uncomment, duplicate line or selection, indentation, and multiple cursors.
- [x] **Ollama Integration** — local AI assistance, configurable models, and code-aware prompts.
- [x] **Plugin Architecture** — discoverable plugins that can extend the IDE with new tools, interfaces, and workflows.
- [x] **Keyboard Shortcuts** — shortcuts for navigation, editing, split views, and AI actions.
- [x] **Configurable Settings** — persistent IDE settings and extensible configuration.

### Planned — Editor Improvements

- [ ] Code minimap and overview navigation.
- [ ] Expand syntax highlighting and language-specific editing support.
- [ ] Configurable auto-save and recovery options.
- [ ] Move lines or selections up and down.
- [ ] Code folding for functions, classes, and structured blocks.
- [ ] Breadcrumb navigation through files and symbols.
- [ ] Improved bracket matching and structural navigation.

### Planned — Development Workflow

- [ ] Git integration with change indicators, diffs, staging, and commit workflows.
- [ ] Integrated debugging and breakpoint support.
- [ ] Advanced refactoring tools, including rename symbol and safe code transformations (see *Planned — Code Intelligence*).
- [ ] Configurable themes and editor appearance.
- [ ] Unified diagnostics panel for errors, warnings, and task output.
- [ ] Project tasks for running tests, linters, formatters, and build commands.

### Planned — Code Intelligence

Code Intelligence currently matches symbols by name. The items below build on that foundation, roughly in priority order.

**Quick wins**

- [ ] Back/forward navigation history (`Alt+Left` / `Alt+Right`) so you can return after jumping to a definition.
- [ ] Follow-cursor outline — highlight the class or function under the cursor in the Symbols tab and show reference counts beside each symbol.
- [ ] Typed filters in Quick Symbol Search (for example `c:` for classes, `f:` for functions) and a "symbols in this file" mode.

**Medium effort**

- [ ] Scope-aware Python references using the AST, separating `self.save` from `other.save` and removing comment/string guesswork.
- [ ] Class hierarchy view showing subclasses and ancestors from the indexed base classes.
- [ ] Incremental re-indexing using file modification times, to pick up changes made outside the IDE.
- [ ] Run Find All References on a background thread (or keep an identifier index) so very large workspaces stay responsive.

**Builds on scope-aware references**

- [ ] Rename symbol with a preview of every change before it is applied.
- [ ] Unused-symbol finder listing functions and classes with no references.

### Planned — AI-Assisted Development

- [ ] Project-aware AI context with explicit control over which files are included.
- [ ] Reviewable AI code changes with diff previews before applying edits.
- [ ] Reusable AI workflows for explaining, testing, refactoring, and documenting code.
- [ ] Local model profiles for different tasks and hardware capabilities.

### Longer-Term Ideas

- [ ] Workspace profiles for different projects and development environments.
- [ ] Plugin discovery, documentation, and easier sharing of extensions.
- [ ] Project health dashboard covering tests, diagnostics, and Git status.
- [ ] Workflow automation that connects editor actions, terminal commands, and local AI tools.

*Roadmap items are indicative rather than release commitments. Features will be prioritised based on usefulness, stability, and the needs of the project.*


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
