# Workspace IDE — Core Handover Document
**Generated:** 2026-06-09
**Repo:** https://github.com/davro/workspace
**Author:** David Stevens &lt;mail.davro@gmail.com&gt;
**Purpose:** AI/developer context handover for `ide/core/` and `ide/core/managers/`
**Scope:** Core only. See `ide/plugins/*/CONTEXT.md` for per-plugin handovers.

---

## 1. Project Overview

**Workspace IDE** is a Python desktop IDE built with **PyQt6** (Fusion dark theme), designed for managing multiple projects in a single workspace with an integrated plugin system and optional local AI via **Ollama**.

| Item | Detail |
|---|---|
| Language | Python 3.12+ |
| UI Framework | PyQt6 (Fusion style, dark theme) |
| AI Backend | Ollama HTTP API (moved to plugin) |
| Config/Session | `~/.config/workspace-ide/` via `AppDirs` |
| Launch | `./ide.sh` (auto-creates venv, installs deps) |
| Entry point | `ide.py` → `ide/core/Workspace.py` |

---

## 2. Repository Structure

```
workspace/
├── ide.py                        # Entry point — 28 lines, thin bootstrap
├── ide.sh                        # Shell launcher (venv management)
├── ide/
│   ├── core/
│   │   ├── Workspace.py          # Main QMainWindow — orchestrator
│   │   ├── CodeEditor.py         # QPlainTextEdit subclass — primary editor widget
│   │   ├── CodeFolding.py        # Code folding logic (gutter widget)
│   │   ├── CombinedTreeDelegate.py  # File tree icon + project highlight delegate
│   │   ├── Document.py           # README/Changelog viewer dialog
│   │   ├── DragDropTreeView.py   # File explorer with drag-drop support
│   │   ├── FileIconProvider.py   # Unicode emoji icons for file types
│   │   ├── FileMonitor.py        # QFileSystemWatcher wrapper (external change detection)
│   │   ├── FileScanner.py        # Background QThread file indexer
│   │   ├── FindReplace.py        # Find & Replace panel widget
│   │   ├── OutlineParser.py      # Multi-language symbol parser
│   │   ├── OutlineWidget.py      # Code outline navigator panel
│   │   ├── Plugin.py             # PluginWidget wrapper + PluginManager loader
│   │   ├── PluginAPI.py          # API surface exposed to plugins (~1066 lines)
│   │   ├── PluginManagerUI.py    # Plugin browser dialog + menu integration
│   │   ├── PluginToolbar.py      # Chrome-extension-style plugin icon toolbar
│   │   ├── ProjectsPanel.py      # Workspace project activation checkboxes
│   │   ├── QuickOpen.py          # Ctrl+P fuzzy file finder dialog
│   │   ├── Settings.py           # Dynamic settings dialog (built from descriptors)
│   │   ├── SettingDescriptor.py  # Dataclass-based settings descriptor system
│   │   ├── SyntaxHighlighter.py  # Python, PHP, INI highlighters
│   │   ├── TabBar.py             # StyledTabBar + StyledTabWidget (modified dot indicator)
│   │   ├── TabSwitcher.py        # Ctrl+Tab MRU switcher popup
│   │   └── managers/
│   │       ├── FileManager.py        # File system ops (create/rename/delete)
│   │       ├── MenuManager.py        # Menu bar construction
│   │       ├── RecentFilesManager.py # Recent files list with persistence
│   │       ├── SessionManager.py     # Save/restore open tabs + window geometry
│   │       ├── SettingsManager.py    # Settings persistence + provider registration
│   │       ├── SplitEditorManager.py # Split view (2 editor groups, H or V)
│   │       ├── StatusBarManager.py   # Status bar (line/col, encoding, EOL, language)
│   │       ├── TabManager.py         # Tab open/close/save operations
│   │       └── TabOrderManager.py    # MRU tab order tracking
│   ├── plugins/                  # See per-plugin CONTEXT.md files
│   └── tests/
```

---

## 3. Entry Point Walkthrough

### `ide.py`
```python
app = QApplication(sys.argv)
app.setStyle("Fusion")
ide = Workspace()
ide.show()
# NOTE: QTimer.singleShot(50, ide.apply_initial_layout) was REMOVED — no longer needed
sys.exit(app.exec())
```

### `ide.sh`
- Auto-creates `workspace-env/` venv if missing
- Supports `./ide.sh [file.py] [install|update]`
- **Pending cleanup:** `PyQt6-WebEngine` and `tree-sitter` should be removed (deprecated browser plugin, tree-sitter not in active use)
- **Planned feature:** Per-plugin dependency installation system (see Bug #18)

---

## 4. Architecture & Key Patterns

### 4.1 Workspace Orchestrator
`Workspace.py` creates and wires all managers. It does not do logic itself — it delegates:
- File ops → `FileManager`
- Tab ops → `TabManager`
- Session → `SessionManager`
- Settings → `SettingsManager`
- Status bar → `StatusBarManager`
- Menus → `MenuManager`
- Recent files → `RecentFilesManager`
- Split view → `SplitEditorManager`
- Tab order → `TabOrderManager`
- Plugins → `PluginManager` + `PluginManagerUI`

### 4.2 Settings Descriptor System
Settings are declared as `SettingDescriptor` dataclasses on each component class:

```python
class CodeEditor(QPlainTextEdit, SettingsProvider):
    SETTINGS_DESCRIPTORS = [
        SettingDescriptor(key='editor_font_size', label='Font Size',
                         setting_type=SettingType.INTEGER, default=11, ...),
        ...
    ]
```

`SettingsManager.register_provider(CodeEditor)` collects all descriptors. `SettingsDialog` auto-builds the UI from them. Adding a new setting = add a descriptor, no other changes needed.

**Pending:** `SettingDescriptor` needs a `hidden: bool = False` field (for settings managed programmatically, not via dialog) and a `restart_required: bool = False` field.

### 4.3 Plugin System

Plugin contract — every plugin must be a class with:
```python
class MyPlugin:
    PLUGIN_NAME = "My Plugin"
    PLUGIN_VERSION = "1.0.0"
    PLUGIN_DESCRIPTION = "..."
    PLUGIN_RUN_ON_STARTUP = False   # True = auto-load at startup
    PLUGIN_HAS_UI = True            # False = background-only
    PLUGIN_ICON = "🔌"

    def __init__(self, api: PluginAPI): ...
    def initialize(self): ...
    def get_widget(self, parent) -> QWidget: ...
    def cleanup(self): ...
```

**Pending:** `PLUGIN_DEPENDENCIES = []` attribute needs to be added to the contract for per-plugin pip dependency management (Bug #18, #41).

`PluginManager.scan_plugins()` is currently **commented out** in `Workspace.__init__` (Bug #5). Plugins do not load at startup.

### 4.4 PluginAPI Surface
`PluginAPI` exposes ~60 methods to plugins. Key categories:
- File ops: `get_current_file()`, `open_file()`, `save_file()`, `close_file()` *(placeholder)*
- Editor access: `get_current_editor()`, `get_all_editors()`
- UI injection: `add_toolbar_button()`, `add_menu_action()`, `add_status_bar_widget()`, `add_editor_context_menu_item()`
- Hooks: `on_file_saved`, `on_file_opened`, `on_file_closed`, `on_editor_focus`, `on_cursor_moved`, `on_workspace_closed`
- Shortcuts: `register_keyboard_shortcut()`
- Settings: `get_setting()`, `set_setting()`
- Status: `show_status_message()`

**Warning:** `PluginAPI.py` has several methods defined twice (last definition wins in Python). See Bugs #43–46. A de-duplication pass is needed.

### 4.5 Split Editor Model
- `SplitEditorManager` manages a list of `EditorGroup` instances (max 2 currently)
- Each `EditorGroup` owns a `StyledTabWidget`
- `active_group_id` tracks which group has focus (set via `focusInEvent` monkey-patching)
- `Workspace.tabs` always points to the active group's tab widget
- `split_manager.get_all_editors()` returns all editors across all groups — use this for any operation that should affect all open files

---

## 5. Complete Bug & Task List

### Critical — Fix First
| # | File | Issue |
|---|---|---|
| 1 | `Workspace.py` | `tabCloseRequested` commented out — tab × button and middle-click close broken |
| 5 | `Workspace.py` | `plugin_manager.scan_plugins()` commented out — plugins never load at startup |
| 26 | `FindReplace.py` | `QTextEdit` not imported — `NameError` crash on first search result |
| 43 | `PluginAPI.py` | `register_keyboard_shortcut` defined twice — good version (line 565) is dead |
| 48 | `PluginAPI.py` | `add_menu_action` uses `self.workspace` — should be `self.ide` — `AttributeError` |
| 64 | `SyntaxHighlighter.py` | Python: `#` inside strings triggers false comment highlighting |
| 65 | `SyntaxHighlighter.py` | PHP: same `#` inside string false comment issue |
| 78 | `RecentFilesManager.py` | `Ctrl+1`–`Ctrl+9` shortcuts active globally — intercept editor digit input |
| 81 | `SessionManager.py` | `save_session` only saves primary tab group — split view tabs silently lost |
| 86 | `SplitEditorManager.py` | `on_group_tab_changed` accumulates `cursorPositionChanged` connections — status bar fires N times |
| 92 | `TabManager.py` | `close_tab_by_path` doesn't call `file_monitor.unwatch_file` — file watched forever |
| 93 | `TabManager.py` | `close_tab_by_path` doesn't check unsaved changes — silently discards edits |
| 94 | `TabManager.py` | `save_all_tabs` only saves primary group — split group files skipped |
| 95 | `TabManager.py` | `open_file_by_path` duplicate check misses split group — opens duplicate tabs |

### High Priority
| # | File | Issue |
|---|---|---|
| 11 | `CodeEditor.py` | HTML/XML comment toggle broken — prefixes `<!--` but never closes with `-->` |
| 18 | `ide.sh` | Plugin deps hardcoded globally — needs per-plugin `PLUGIN_DEPENDENCIES` system |
| 35 | `OutlineParser.py` | `async def` functions missing from Python outline (use `ast.AsyncFunctionDef`) |
| 41 | `Plugin.py` | `PLUGIN_DEPENDENCIES` attribute missing from plugin contract |
| 42 | `Plugin.py` | A broken `PLUGIN_RUN_ON_STARTUP` plugin can block all others from loading |
| 80 | `SessionManager.py` | Cursor restore uses slow `MoveOperation.Down` N times — use `findBlockByLineNumber` |

### Medium Priority
| # | File | Issue |
|---|---|---|
| 2 | `Workspace.py` | `view_menu = findChildren(QMenu)[2]` — fragile index, breaks if menus reordered |
| 3 | `Workspace.py` | `cursorPositionChanged.disconnect()` kills all connections incl. plugin ones |
| 6 | `Workspace.py` | Tab context menu only works on primary split group, not secondary |
| 9 | `CodeEditor.py` | `check_external_changes_before_save` exists but never called from `save_file` |
| 10 | `CodeEditor.py` | No fallback encoding in `load_file` — Latin-1/Windows-1252 files show error |
| 13 | `CodeFolding.py` | Fold state lost after line insertions/deletions (matched by line number, not content) |
| 14 | `CodeFolding.py` | `_parse_braces` counts `{`/`}` inside strings and comments |
| 15 | `CodeFolding.py` | Python multiline string `"""` detection fragile |
| 16 | `CodeFolding.py` | Fold state not persisted in session |
| 20 | `DragDropTreeView.py` | `dragged_path` not cleared on drag cancel — stale state on next drag |
| 21 | `DragDropTreeView.py` | `layoutChanged.emit()` after move collapses entire file tree |
| 25 | `FileScanner.py` | `progress` signal cross-thread UI update — verify `QueuedConnection` |
| 28 | `FindReplace.py` | `in_selection` range not frozen when checkbox ticked — shifts on click |
| 30 | `OutlineParser.py` | O(n) line number calculation per symbol in all regex parsers (fix: `enumerate` lines) |
| 31 | `OutlineParser.py` | PHP: class methods also appear as top-level functions (duplicate symbols) |
| 32 | `OutlineParser.py` | Java: method regex matches variable declarations — false symbols |
| 39 | `Plugin.py` | `scan_plugins` loads module twice for `PLUGIN_RUN_ON_STARTUP` plugins |
| 44 | `PluginAPI.py` | `get_current_editor` defined twice |
| 45 | `PluginAPI.py` | `get_workspace_path` defined twice (second safer version masks first) |
| 46 | `PluginAPI.py` | `show_status_message` defined twice — fallback lost |
| 47 | `PluginAPI.py` | `close_file` is a placeholder — returns `False` silently |
| 50 | `PluginManagerUI.py` | Duplicate tab detection misses split group tabs |
| 54 | `ProjectsPanel.py` | `rglob('*')` file count blocks UI thread on panel open |
| 57 | `QuickOpen.py` | Scanner thread not stopped on dialog close — fires `on_files_loaded` on destroyed dialog |
| 58 | `QuickOpen.py` | `keyPressEvent` calls `search_input.keyPressEvent` directly — bypasses Qt event system |
| 67 | `SyntaxHighlighter.py` | Only Python, PHP, INI highlighters — JS/TS/HTML/CSS/SQL etc. have none |
| 68 | `TabBar.py` | `tabMoved` index adjustment wrong for forward moves — modified dot lost |
| 70 | `TabSwitcher.py` | `recent_order` indices can be stale if tabs closed outside `TabManager.close_tab` |
| 72 | `FileManager.py` | `rename_item` reopens file even if it wasn't open before rename |
| 73 | `FileManager.py` | Folder delete dialog doesn't warn about recursive content deletion |
| 76 | `MenuManager.py` | Recent files menu-building logic duplicated in `_refresh_recent_files_menu` |
| 83 | `SessionManager.py` | No atomic session file write — corrupt file on crash |
| 84 | `SplitEditorManager.py` | Two different focus handler closure patterns — use `_create_focus_handler` consistently |
| 87 | `SplitEditorManager.py` | `show_tab_context_menu` uses shared `active_group_id` state — breaks if async action fires |
| 89 | `StatusBarManager.py` | EOL detection reads 1024 bytes from disk on every tab switch |
| 91 | `StatusBarManager.py` | `_on_language_label_click` reads from primary group only — wrong file in split view |
| 97 | `TabOrderManager.py` | Stale indices if tabs closed outside `TabManager.close_tab` — `remove_tab` not called |

### Low Priority / Cleanup
| # | File | Issue |
|---|---|---|
| 4 | `Workspace.py` | `auto_save` setting conflates file save vs session save — misleading label |
| 7 | `CodeEditor.py` | `blockCountChanged`/`updateRequest` signals connected twice |
| 8 | `CodeEditor.py` | `textChanged` connected twice (`on_text_changed` + no-op `_on_text_changed`) |
| 12 | `CodeEditor.py` | `_is_folding_enabled` walks parent tree on every keypress — cache it |
| 17 | `ide.sh` | `PyQt6-WebEngine` and `tree-sitter` can be removed (browser plugin deprecated) |
| 19 | `DragDropTreeView.py` | `fileActivated` signal declared but never emitted — dead code |
| 22 | `DragDropTreeView.py` | Status bar access inconsistent (`parent()` vs `window()`) |
| 23 | `Document.py` | Duplicate commented code removed ✅ |
| 24 | `FileMonitor.py` | 100ms hash update timer races with large file writes |
| 27 | `FindReplace.py` | `replace_all` shows modal `QMessageBox` — should be inline label update |
| 29 | `FindReplace.py` | `toPlainText()` called on every keystroke for `end` position — use `characterCount()` |
| 33 | `OutlineParser.py` | JSON: O(n) key search + duplicate key line number issue |
| 34 | `OutlineParser.py` | HTML: only captures `id=` elements — misses `<h1>`–`<h6>`, landmarks |
| 36 | `OutlineWidget.py` | Bare `except: pass` swallows `SystemExit` — use `except RuntimeError` |
| 37 | `OutlineWidget.py` | `_refresh_timer` created lazily in `on_text_changed` — should be in `__init__` |
| 38 | `OutlineWidget.py` | Commented duplicate `jump_to_line` and `cleanup` — dead code to remove |
| 40 | `Plugin.py` | Stray `print("####...")` fires on every plugin load |
| 49 | `PluginAPI.py` | `_context_menu_items` not initialised in `__init__` — lazy creation on every call |
| 51 | `PluginManagerUI.py` | `scan_plugins()` called on every menu open — should cache |
| 52 | `PluginToolbar.py` | `show_plugin_info` dialog has no dark theme applied |
| 53 | `PluginToolbar.py` / `PluginManagerUI.py` | Large commented dead code blocks — cleanup pass needed |
| 55 | `ProjectsPanel.py` | Bare `except` on file count — use `except (PermissionError, OSError)` |
| 56 | `ProjectsPanel.py` | `set_active_projects` emits signal during session restore — unnecessary startup scan |
| 59 | `QuickOpen.py` | Empty search shows first 50 files alphabetically — should show recent files |
| 60 | `SettingDescriptor.py` | `hidden` flag missing — needed by `ProjectsPanel` and settings-only keys |
| 61 | `SettingDescriptor.py` | `CHOICE` invalid stored value silently resets — should log warning |
| 62 | `Settings.py` | `max_value=0.0` treated as falsy for FLOAT widgets — use `is not None` check |
| 63 | `Settings.py` | Dialog not rebuilt after plugin hot-reload — new descriptors not shown |
| 66 | `SyntaxHighlighter.py` | PHP: no heredoc/nowdoc support |
| 69 | `TabSwitcher.py` | `center_on_parent` called before dialog has size — use `adjustSize()` first |
| 71 | `TabSwitcher.py` | `eventFilter` installed but is dead code |
| 74 | `MenuManager.py` | Old `create_file_menu` dead alongside `create_file_menu_with_recent` |
| 75 | `MenuManager.py` | `create_view_menu` has two commented dead implementations |
| 77 | `MenuManager.py` | `Ctrl+O` for Go to File conflicts with system open on some platforms |
| 79 | `RecentFilesManager.py` | `_load_recent_files` writes to disk on every startup with stale files |
| 82 | `SessionManager.py` | 50ms scroll restore timer fragile on slow machines/large files |
| 85 | `SplitEditorManager.py` | `close_split` disconnects signals unconditionally — raises `TypeError` if none connected |
| 88 | `SplitEditorManager.py` | `setSizes([0, 0])` if split created before widget has geometry |
| 90 | `StatusBarManager.py` | Bare `except` on EOL detection — use `except (OSError, PermissionError)` |
| 96 | `TabOrderManager.py` | `remove_tab` runs index adjustment unconditionally — harmless but confusing |

---

## 6. Planned Features (from codebase comments + README roadmap)

| Feature | Notes |
|---|---|
| Per-plugin dependency installation | `PLUGIN_DEPENDENCIES` on plugin class; `scan_plugins` installs via pip |
| Auto-save file content | Timer + dirty flag; `auto_save_timer` already in `Workspace` for session only |
| Move line up/down | `Alt+Up`/`Alt+Down` — simple text cursor manipulation |
| Built-in terminal panel | `terminal_height` setting exists in descriptors, marked "not currently used" |
| Git status in file tree | Read-only `git status` subprocess; colour indicators in `CombinedTreeDelegate` |
| Themes / QSS theming | Hardcoded `#2B2B2B` etc. throughout — needs CSS variable abstraction |
| Code folding improvements | Persist fold state; fix string/comment-aware brace matching |
| Minimap | Scaled-down editor render in side panel |
| Multi-cursor | Complex in `QPlainTextEdit`; not started |
| Symbol search across project | Cross-file outline search |
| Breadcrumb navigation | File path + symbol chain above editor |
| More syntax highlighters | JS/TS/HTML/CSS/SQL/Rust/Go etc. currently have no highlighting |
| AI backend abstraction | Abstract Ollama calls behind `AIProvider` interface to allow other backends |
| `PluginManager` scan cache | Cache `scan_plugins()` result; invalidate on explicit refresh only |

---

## 7. Open Questions for Next Developer

1. **`.tl` extension** — `FileIconProvider` has a `🔷` icon for `.tl` but no `OutlineParser` entry and no `SyntaxHighlighter`. What is this format? Is there a custom language parser needed?

2. **`tree-sitter` dependency** — Listed in `ide.sh` requirements but no `tree-sitter` imports found in core. Confirm it can be removed safely.

3. **`PyQt6-WebEngine`** — Browser plugin deprecated. Confirm removal from `ide.sh`. Check no other code references `QWebEngineView`.

4. **`scan_plugins()` being commented out** — Was this intentional (stability) or forgotten? The plugin system is otherwise complete. Uncommenting and testing should be an early task.

5. **`tabCloseRequested` commented out in `Workspace.py`** — The comment says "BUG CLOSES MULTIPLE TABS AFTER TAB CLOSE". The `SplitEditorManager.EditorGroup` already handles `tabCloseRequested` correctly via `close_tab_in_group`. The primary `Workspace.tabs` connection needs the same treatment — wire to `split_manager.close_tab_in_group(0, idx)` rather than the old `tab_manager.close_tab(idx)`.

6. **Session + split view** — `save_session` and `restore_session` have no awareness of split layout. Decide: (a) save/restore split state fully, or (b) always restore to single-group view. Option (b) is simpler and acceptable.

7. **Language map duplication** — `StatusBarManager`, `CodeEditor` (syntax highlighter selection), and implicitly `SyntaxHighlighter` all have separate extension→language mappings. Consolidate into a single `LANGUAGE_MAP` dict, suggested location: a new `ide/core/LanguageRegistry.py`.

---

## 8. Keyboard Shortcuts Reference

| Action | Shortcut |
|---|---|
| Quick Open | `Ctrl+P` |
| Go to File | `Ctrl+O` |
| Go to Line | `Ctrl+G` |
| Recent Files menu | `Ctrl+R` |
| Find | `Ctrl+F` |
| Replace | `Ctrl+H` |
| Save | `Ctrl+S` |
| Save All | `Ctrl+Shift+S` |
| New File | `Ctrl+N` |
| New Folder | `Ctrl+Shift+N` |
| Close Tab | `Ctrl+W` |
| Close All Tabs | `Ctrl+Shift+W` |
| Split Vertical | `Ctrl+\` |
| Split Horizontal | `Ctrl+Shift+\` |
| Move Tab to Other Group | `Ctrl+Alt+M` |
| Focus Other Group | `Ctrl+Alt+O` |
| Open in Split | `Ctrl+Alt+S` |
| Close Split | `Ctrl+Alt+W` |
| Toggle Explorer | `Ctrl+B` |
| Toggle Right Sidebar | `Ctrl+Shift+B` |
| Toggle Comment | `Ctrl+/` |
| Duplicate Line | `Ctrl+D` |
| Run File | `F5` |
| Preferences | `Ctrl+,` |
| Tab Switcher (MRU) | `Ctrl+Tab` |
| Keyboard Shortcuts Help | `Ctrl+K Ctrl+S` |
| Documentation | `F1` |
| Changelog | `F2` |

---

## 9. Recommended First Session Agenda

Work through these in order for maximum impact:

**Session 1 — Critical crashes and broken core features**
1. Fix Bug #26 — add `QTextEdit` import to `FindReplace.py`
2. Fix Bug #1 — wire `tabCloseRequested` in `Workspace.py` via `split_manager` (see Open Question #5)
3. Fix Bug #5 — uncomment `scan_plugins()` in `Workspace.__init__`, test with existing plugins
4. Fix Bug #48 — `self.workspace` → `self.ide` in `PluginAPI.add_menu_action`
5. Fix Bug #43 — remove duplicate `register_keyboard_shortcut` keeping the line 565 version

**Session 2 — Split view correctness**
6. Fix Bug #86 — disconnect `cursorPositionChanged` before reconnecting in `SplitEditorManager.on_group_tab_changed`
7. Fix Bug #94/95 — use `split_manager.get_all_editors()` in `save_all_tabs` and duplicate-file check
8. Fix Bug #81 — save split group tabs in `save_session`
9. Fix Bug #92/93 — add unwatch + unsaved check to `close_tab_by_path`

**Session 3 — Syntax highlighting**
10. Fix Bug #64/65 — Python and PHP false comment from `#` inside strings
11. Fix Bug #67 — add JS/TS/HTML/CSS/SQL highlighters
12. Fix Bug #35 — add `ast.AsyncFunctionDef` to `PythonParser`

**Session 4 — Plugin dependency system**
13. Add `PLUGIN_DEPENDENCIES = []` to plugin contract
14. Implement per-plugin pip install in `scan_plugins`
15. Remove `web3`, `bip_utils`, `psycopg`, `PyQt6-WebEngine`, `tree-sitter` from global `ide.sh` requirements

**Session 5 — Polish and cleanup**
16. Fix Bug #78 — scope `Ctrl+1`–`Ctrl+9` to menu context only
17. Fix Bug #80 — use `findBlockByLineNumber` in `SessionManager.restore_session`
18. Fix Bug #89 — cache EOL detection in `CodeEditor`, read from attribute in `StatusBarManager`
19. Add `hidden` flag to `SettingDescriptor` (Bug #60)
20. Consolidate language maps into `LanguageRegistry` (Open Question #7)
21. General dead code cleanup pass (commented blocks in `PluginAPI`, `MenuManager`, `PluginManagerUI`, `PluginToolbar`, `OutlineWidget`)

---

## 10. Tech Stack & Dependencies

| Package | Purpose | Status |
|---|---|---|
| `PyQt6` | UI framework | Core — keep |
| `PyQt6-WebEngine` | Browser panel | **Remove** — plugin deprecated |
| `markdown` | README viewer (`Document.py`) | Keep |
| `requests` | Ollama HTTP calls | Keep (used by Ollama plugin) |
| `tree-sitter` | Code parsing | **Likely remove** — not used in core |
| `tree-sitter-python` | Python grammar | **Likely remove** |
| `web3` | Blockchain/wallet | Move to WalletPlugin dependencies |
| `bip_utils` | HD wallet | Move to WalletPlugin dependencies |
| `cryptography` | Crypto ops | Move to WalletPlugin dependencies |
| `argon2` / `argon2-cffi` | Password hashing | Move to WalletPlugin dependencies |
| `psycopg` | PostgreSQL | Move to DB plugin dependencies |

---

*This document covers `ide/core/` and `ide/core/managers/` only.*
*For plugin-specific context see `ide/plugins/<PluginName>/CONTEXT.md`*
*Generated from full file-by-file review of all 27 core files + 9 manager files.*
