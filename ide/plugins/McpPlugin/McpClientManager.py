"""
McpClientManager - runs MCP (Model Context Protocol) servers for the IDE.

* Pure Python, no Qt imports, so it can be tested on its own.
* Owns a background thread with an asyncio loop. Every server is one task on
  that loop, which keeps the SDK's async context managers entered/exited in the
  same task (required by anyio).
* Thread-safe public API: call it from the GUI thread or from worker threads.
* Works with the official `mcp` SDK, both 1.x and 2.x (`pip install mcp`).

Config file (same shape as Claude Desktop's):

    {
      "mcpServers": {
        "filesystem": {
          "command": "npx",
          "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"],
          "env": {"KEY": "value"},      # optional
          "cwd": "/some/dir",           # optional
          "disabled": false,            # optional
          "includeTools": ["a", "b"],   # optional: expose ONLY these tools
          "excludeTools": ["c"]         # optional: hide these tools (e.g. write ops)
        }
      }
    }
"""

import asyncio
import concurrent.futures
import json
import os
import re
import shutil
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

CONNECT_TIMEOUT = 45.0       # seconds to spawn + initialize + list tools
DEFAULT_CALL_TIMEOUT = 120.0

DEFAULT_CONFIG_TEXT = json.dumps({"mcpServers": {}}, indent=2) + "\n"


class McpError(Exception):
    """Raised for problems the caller should show to the user / the model."""


@dataclass
class ServerState:
    name: str
    config: dict
    status: str = "disconnected"        # disconnected | connecting | connected | error
    error: str = ""
    tools: List[dict] = field(default_factory=list)
    hidden: int = 0                      # tools filtered out by include/excludeTools
    session: Any = None
    stop_event: Optional[asyncio.Event] = None
    task: Optional[asyncio.Task] = None


def _sanitize(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", text)


def _leaf_error(exc: BaseException) -> str:
    """Unwrap (nested) ExceptionGroups from anyio into one readable line."""
    while hasattr(exc, "exceptions") and getattr(exc, "exceptions"):
        exc = exc.exceptions[0]
    msg = str(exc).strip()
    return f"{type(exc).__name__}: {msg}" if msg else type(exc).__name__


def _g(obj: Any, *names: str, default: Any = None) -> Any:
    """getattr that accepts both mcp 1.x (camelCase) and 2.x (snake_case) names."""
    for n in names:
        v = getattr(obj, n, None)
        if v is not None:
            return v
    return default


def result_to_text(result: Any) -> Tuple[str, bool]:
    """Flatten an MCP CallToolResult into (text, is_error)."""
    is_error = bool(_g(result, "isError", "is_error", default=False))
    parts: List[str] = []
    for item in getattr(result, "content", None) or []:
        kind = getattr(item, "type", "")
        if kind == "text":
            parts.append(item.text)
        elif kind == "image":
            parts.append(f"[image: {_g(item, 'mimeType', 'mime_type', default='?')}, "
                         f"{len(getattr(item, 'data', '') or '')} base64 chars]")
        elif kind == "resource":
            res = getattr(item, "resource", None)
            text = getattr(res, "text", None)
            parts.append(text if text is not None else f"[resource: {getattr(res, 'uri', '?')}]")
        elif kind == "resource_link":
            parts.append(f"[resource link: {getattr(item, 'uri', '?')}]")
        else:
            parts.append(str(item))
    if not parts:
        structured = _g(result, "structuredContent", "structured_content")
        if structured is not None:
            parts.append(json.dumps(structured, indent=2, default=str))
    return "\n".join(parts) if parts else "(no output)", is_error


class McpClientManager:
    def __init__(self, config_path: Path, log: Callable[[str], None] = print):
        self.config_path = Path(config_path)
        self._log = log
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self._servers: Dict[str, ServerState] = {}
        self._tool_index: Dict[str, Tuple[str, str]] = {}   # qualified -> (server, tool)
        self._listeners: List[Callable[[], None]] = []

    # ------------------------------------------------------------------ lifecycle

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        ready = threading.Event()

        def runner():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.call_soon(ready.set)
            try:
                self._loop.run_forever()
            finally:
                self._loop.close()

        self._thread = threading.Thread(target=runner, name="mcp-loop", daemon=True)
        self._thread.start()
        ready.wait(5)

    def shutdown(self, timeout: float = 6.0):
        """Stop every server and the background loop. Safe to call twice."""
        loop = self._loop
        if not loop or not loop.is_running():
            return

        async def _stop_all():
            tasks = []
            for st in list(self._servers.values()):
                if st.stop_event:
                    st.stop_event.set()
                if st.task:
                    tasks.append(st.task)
            if tasks:
                await asyncio.wait(tasks, timeout=timeout - 1)

        try:
            asyncio.run_coroutine_threadsafe(_stop_all(), loop).result(timeout)
        except Exception:
            pass
        loop.call_soon_threadsafe(loop.stop)
        if self._thread:
            self._thread.join(2)

    # ------------------------------------------------------------------ listeners

    def add_listener(self, callback: Callable[[], None]):
        """callback() is invoked from the MCP thread whenever state changes."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[], None]):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify(self):
        for cb in list(self._listeners):
            try:
                cb()
            except Exception:
                pass

    # ------------------------------------------------------------------ config

    def ensure_config_file(self):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.config_path.exists():
            self.config_path.write_text(DEFAULT_CONFIG_TEXT, encoding="utf-8")

    def load_config(self) -> Dict[str, dict]:
        self.ensure_config_file()
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError as e:
            raise McpError(f"{self.config_path.name} is not valid JSON: {e}")
        servers = data.get("mcpServers", {})
        if not isinstance(servers, dict):
            raise McpError('"mcpServers" must be an object')
        for name, cfg in servers.items():
            if not isinstance(cfg, dict) or not isinstance(cfg.get("command"), str):
                raise McpError(f'Server "{name}" needs a string "command"')
            for key in ("includeTools", "excludeTools"):
                value = cfg.get(key)
                if value is not None and not (isinstance(value, list) and all(isinstance(v, str) for v in value)):
                    raise McpError(f'Server "{name}": "{key}" must be a list of tool names')
        return servers

    def add_server_to_config(self, name: str, cfg: dict):
        """Add/replace one server entry, preserving everything else in the file."""
        self.ensure_config_file()
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError as e:
            raise McpError(f"{self.config_path.name} is not valid JSON: {e}")
        data.setdefault("mcpServers", {})[name] = cfg
        self.config_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    # ------------------------------------------------------------------ connect / reload

    def reload(self) -> Optional[str]:
        """
        Re-read the config and reconcile running servers with it.
        Returns an error string if the config is invalid, else None.
        """
        self.start()
        try:
            wanted = self.load_config()
        except McpError as e:
            return str(e)

        with self._lock:
            for name in list(self._servers):
                if name not in wanted:
                    self._stop_server(self._servers.pop(name))

            for name, cfg in wanted.items():
                current = self._servers.get(name)
                if current and current.config == cfg and current.status in ("connected", "connecting"):
                    continue
                if current:
                    self._stop_server(current)
                st = ServerState(name=name, config=cfg)
                self._servers[name] = st
                if cfg.get("disabled"):
                    st.error = "disabled in config"
                else:
                    self._spawn(st)
            self._rebuild_index()
        self._notify()
        return None

    def connect(self, name: str):
        with self._lock:
            st = self._servers.get(name)
            if not st or st.status in ("connected", "connecting"):
                return
            fresh = ServerState(name=name, config=st.config)
            self._servers[name] = fresh
            self._spawn(fresh)
        self._notify()

    def disconnect(self, name: str):
        with self._lock:
            st = self._servers.get(name)
            if st:
                self._stop_server(st)
                st.status = "disconnected"
                st.error = ""
                st.tools = []
            self._rebuild_index()
        self._notify()

    def _spawn(self, st: ServerState):
        st.status = "connecting"
        st.error = ""

        def _create():
            st.stop_event = asyncio.Event()
            st.task = self._loop.create_task(self._run_server(st))

        self._loop.call_soon_threadsafe(_create)

    def _stop_server(self, st: ServerState):
        def _set():
            if st.stop_event:
                st.stop_event.set()
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(_set)

    async def _run_server(self, st: ServerState):
        # Imported lazily so the IDE still starts if `mcp` isn't installed.
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError:
            self._fail(st, 'The "mcp" package is not installed (pip install mcp)')
            return

        cfg = st.config
        command = cfg["command"]
        if shutil.which(command) is None and not Path(command).exists():
            self._fail(st, f'Command not found: "{command}" (is it installed and on PATH?)')
            return

        params = StdioServerParameters(
            command=command,
            args=[str(a) for a in cfg.get("args", [])],
            env=cfg.get("env") or None,
            cwd=cfg.get("cwd") or None,
        )
        errlog = tempfile.TemporaryFile("w+")     # keep server stderr for diagnostics
        try:
            async with stdio_client(params, errlog=errlog) as (read, write):
                async with ClientSession(read, write) as session:
                    await asyncio.wait_for(session.initialize(), CONNECT_TIMEOUT)
                    tools = await asyncio.wait_for(self._list_all_tools(session), CONNECT_TIMEOUT)
                    include = set(cfg.get("includeTools") or [])
                    exclude = set(cfg.get("excludeTools") or [])
                    visible = [t for t in tools
                               if (not include or t.name in include) and t.name not in exclude]
                    with self._lock:
                        st.session = session
                        st.hidden = len(tools) - len(visible)
                        st.tools = [self._tool_dict(st.name, t) for t in visible]
                        st.status = "connected"
                        self._rebuild_index()
                    self._log(f"[MCP] {st.name}: connected, {len(visible)} tools"
                              + (f" ({st.hidden} hidden)" if st.hidden else ""))
                    self._notify()
                    await st.stop_event.wait()
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            self._fail(st, f"Timed out after {CONNECT_TIMEOUT:.0f}s starting the server", errlog)
        except Exception as e:
            self._fail(st, _leaf_error(e), errlog)
        finally:
            with self._lock:
                st.session = None
                if st.status != "error":
                    st.status = "disconnected"
                    st.tools = []
                    st.hidden = 0
                self._rebuild_index()
            try:
                errlog.close()
            except Exception:
                pass
            self._notify()

    def _fail(self, st: ServerState, message: str, errlog=None):
        tail = ""
        if errlog is not None:
            try:
                errlog.flush()
                errlog.seek(0)
                tail = errlog.read()[-1200:].strip()
            except Exception:
                pass
        with self._lock:
            st.status = "error"
            st.error = message + (f"\n\nServer stderr:\n{tail}" if tail else "")
            st.tools = []
        self._log(f"[MCP] {st.name}: {message}")
        self._notify()

    @staticmethod
    async def _list_all_tools(session) -> list:
        result = await session.list_tools()
        tools = list(result.tools)
        cursor = _g(result, "nextCursor", "next_cursor")
        while cursor:
            try:
                from mcp import types
                result = await session.list_tools(params=types.PaginatedRequestParams(cursor=cursor))
            except (TypeError, AttributeError):
                result = await session.list_tools(cursor=cursor)
            tools.extend(result.tools)
            cursor = _g(result, "nextCursor", "next_cursor")
        return tools

    @staticmethod
    def _tool_dict(server: str, tool: Any) -> dict:
        return {
            "server": server,
            "name": tool.name,
            "description": (getattr(tool, "description", None) or "").strip(),
            "schema": _g(tool, "inputSchema", "input_schema") or {"type": "object", "properties": {}},
        }

    def _rebuild_index(self):
        index: Dict[str, Tuple[str, str]] = {}
        for st in self._servers.values():
            if st.status != "connected":
                continue
            for t in st.tools:
                qualified = f"{_sanitize(st.name)}__{_sanitize(t['name'])}"
                base, n = qualified, 2
                while qualified in index:
                    qualified, n = f"{base}_{n}", n + 1
                t["qualified"] = qualified
                index[qualified] = (st.name, t["name"])
        self._tool_index = index

    # ------------------------------------------------------------------ queries

    def servers(self) -> List[dict]:
        with self._lock:
            return [
                {
                    "name": st.name,
                    "status": st.status,
                    "error": st.error,
                    "command": " ".join([st.config.get("command", "")] + [str(a) for a in st.config.get("args", [])]),
                    "hidden": st.hidden,
                    "tools": [dict(t) for t in st.tools],
                }
                for st in self._servers.values()
            ]

    def resolve_tool(self, qualified_name: str) -> Optional[Tuple[str, str]]:
        """(server_name, tool_name) for a qualified tool name, or None if unknown."""
        with self._lock:
            return self._tool_index.get(qualified_name)

    def tool_count(self) -> int:
        return len(self._tool_index)

    def ollama_tools(self) -> List[dict]:
        """Tools in the format Ollama's /api/chat expects."""
        out = []
        with self._lock:
            for st in self._servers.values():
                if st.status != "connected":
                    continue
                for t in st.tools:
                    desc = t["description"] or t["name"]
                    out.append({
                        "type": "function",
                        "function": {
                            "name": t["qualified"],
                            "description": f"[{st.name}] {desc}"[:1000],
                            "parameters": t["schema"],
                        },
                    })
        return out

    # ------------------------------------------------------------------ calling

    def call_tool(self, qualified_name: str, arguments: Optional[dict] = None,
                  timeout: float = DEFAULT_CALL_TIMEOUT) -> Tuple[str, bool]:
        """
        Blocking call - run it from a worker thread, not the GUI thread.
        Returns (text, is_error). Raises McpError for unknown tools / dead servers.
        """
        with self._lock:
            target = self._tool_index.get(qualified_name)
            st = self._servers.get(target[0]) if target else None
            session = st.session if st else None
        if not target or not session:
            raise McpError(f'Unknown or disconnected tool "{qualified_name}"')
        if not self._loop or not self._loop.is_running():
            raise McpError("MCP loop is not running")

        async def _call():
            result = await asyncio.wait_for(session.call_tool(target[1], arguments or {}), timeout)
            return result_to_text(result)

        future = asyncio.run_coroutine_threadsafe(_call(), self._loop)
        try:
            return future.result(timeout + 5)
        except (asyncio.TimeoutError, TimeoutError, concurrent.futures.TimeoutError):
            raise McpError(f"Tool timed out after {timeout:.0f}s")
        except McpError:
            raise
        except Exception as e:
            raise McpError(_leaf_error(e))