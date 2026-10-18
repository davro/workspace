"""
OllamaWorker - talks to Ollama's HTTP API (/api/chat) on a background thread.

Replaces the old `ollama run <model> <prompt>` subprocess, which:
  * had no conversation memory (every message was a brand-new chat),
  * returned only when the whole answer was finished (no streaming),
  * cannot do tool calling, which MCP needs.

The worker streams tokens, and if the model asks for tools it asks the GUI for
approval, runs them through the MCP manager and feeds the results back, looping
until the model gives a final answer.
"""

import json
import os
import re
import threading
import urllib.error
import urllib.request
from urllib.parse import urlparse

from PyQt6.QtCore import QThread, pyqtSignal

MAX_TOOL_ROUNDS = 8            # safety net against endless tool loops
MAX_TOOL_RESULT_CHARS = 20000  # keep huge tool outputs from blowing the context


def ollama_base_url() -> str:
    """Resolve the server URL the same way the ollama CLI does (OLLAMA_HOST)."""
    host = (os.environ.get("OLLAMA_HOST") or "").strip() or "127.0.0.1:11434"
    if not host.startswith(("http://", "https://")):
        host = "http://" + host
    parsed = urlparse(host)
    hostname = parsed.hostname or "127.0.0.1"
    if hostname in ("0.0.0.0", "::"):
        hostname = "127.0.0.1"
    scheme = parsed.scheme
    port = parsed.port or (443 if scheme == "https" else 11434)
    return f"{scheme}://{hostname}:{port}"


def _error_text(body: str) -> str:
    try:
        return json.loads(body).get("error", body)
    except Exception:
        return body.strip()[:300]


class _Cancelled(Exception):
    pass


class OllamaChatWorker(QThread):
    token = pyqtSignal(str)               # streamed piece of the answer
    tool_call = pyqtSignal(str, str)      # tool name, arguments (JSON text)
    tool_result = pyqtSignal(str, str, bool)   # tool name, preview, is_error
    approval_needed = pyqtSignal(str, str, object)   # name, args JSON, holder dict
    notice = pyqtSignal(str)              # informational line for the chat
    discard_reply = pyqtSignal()          # the text just streamed was really a tool call; drop it
    done = pyqtSignal(list)               # new messages to append to history
    failed = pyqtSignal(str)

    def __init__(self, model, messages, tools=None, mcp=None,
                 timeout=240, tool_timeout=120, options=None, parent=None):
        super().__init__(parent)
        self.model = model
        self.messages = list(messages)
        self.tools = tools or None
        self.mcp = mcp
        self.timeout = timeout
        self.tool_timeout = tool_timeout
        self.options = options or None      # e.g. {"temperature": 0.2}
        self.base_url = ollama_base_url()
        self._cancel = threading.Event()

    def cancel(self):
        self._cancel.set()

    # ------------------------------------------------------------------ main loop

    def run(self):
        convo = list(self.messages)
        new_messages = []
        try:
            for _ in range(MAX_TOOL_ROUNDS):
                msg, cancelled = self._chat_once(convo)
                if msg["content"] or msg.get("tool_calls"):
                    convo.append(msg)
                    new_messages.append(msg)
                if cancelled:
                    self.done.emit(new_messages)
                    return

                calls = msg.get("tool_calls") or []
                if not calls:
                    self.done.emit(new_messages)
                    return

                for call in calls:
                    fn = call.get("function", {})
                    name = fn.get("name", "")
                    args = fn.get("arguments") or {}
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except ValueError:
                            args = {}
                    text, is_error = self._run_tool(name, args)
                    tool_msg = {"role": "tool", "tool_name": name, "content": text}
                    convo.append(tool_msg)
                    new_messages.append(tool_msg)

            self.notice.emit(f"Stopped after {MAX_TOOL_ROUNDS} tool rounds.")
            self.done.emit(new_messages)

        except _Cancelled:
            self.done.emit(new_messages)
        except Exception as e:
            self.failed.emit(str(e))

    # ------------------------------------------------------------------ one request

    def _chat_once(self, convo):
        """Stream one /api/chat call. Returns (assistant_message, was_cancelled)."""
        payload = {"model": self.model, "messages": convo, "stream": True}
        if self.tools:
            payload["tools"] = self.tools
        if self.options:
            payload["options"] = self.options

        request = urllib.request.Request(
            self.base_url + "/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            response = urllib.request.urlopen(request, timeout=self.timeout)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if self.tools and e.code == 400 and "tool" in body.lower():
                self.notice.emit("This model does not support tools - continuing without MCP tools.")
                self.tools = None
                return self._chat_once(convo)
            raise RuntimeError(f"Ollama error {e.code}: {_error_text(body)}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Cannot reach Ollama at {self.base_url} ({e.reason}). Is `ollama serve` running?")

        content, tool_calls, cancelled = [], [], False
        # Some models (llama3.1) write a tool call as plain JSON text instead of a structured
        # call. If a reply starts with "{" or a code fence we hold it back until it is complete,
        # so a tool call is never flashed to the user as raw JSON. None = undecided yet.
        holding = None
        with response:
            for raw in response:
                if self._cancel.is_set():
                    cancelled = True
                    break
                line = raw.strip()
                if not line:
                    continue
                chunk = json.loads(line)
                if chunk.get("error"):
                    raise RuntimeError(chunk["error"])
                message = chunk.get("message") or {}
                piece = message.get("content") or ""
                if piece:
                    content.append(piece)
                    if holding is None:
                        first = "".join(content).lstrip()
                        if first:
                            holding = bool(self.tools) and first[0] in "{`"
                            if not holding:
                                self.token.emit("".join(content))
                    elif holding is False:
                        self.token.emit(piece)
                if message.get("tool_calls"):
                    tool_calls.extend(message["tool_calls"])
                if chunk.get("done"):
                    break

        text = "".join(content)
        if holding:
            calls = None if (cancelled or tool_calls) else self._text_tool_calls(text)
            if calls:
                tool_calls, text = calls, ""
            else:
                self.token.emit(text)

        # Tool call written inside prose / a code fence ("Here are the function calls: ...")
        if not tool_calls and not cancelled and self.tools:
            embedded = self._embedded_tool_call(text)
            if embedded:
                tool_calls, text = [embedded], ""
                self.discard_reply.emit()

        for call in tool_calls:
            fn = call.setdefault("function", {})
            fn["name"] = self._resolve_name(fn.get("name", ""))

        msg = {"role": "assistant", "content": text}
        if tool_calls and not cancelled:
            msg["tool_calls"] = tool_calls
        return msg, cancelled

    # ------------------------------------------------------------------ tool-call tolerance

    def _tool_names(self):
        return [t["function"]["name"] for t in (self.tools or [])]

    def _resolve_name(self, name):
        """Accept 'read_text_file' for 'filesystem__read_text_file' when it is unambiguous."""
        names = self._tool_names()
        if not names or name in names:
            return name
        matches = [n for n in names if n.endswith("__" + name)]
        return matches[0] if len(matches) == 1 else name

    def _embedded_tool_call(self, text):
        """
        Find the first usable tool call written anywhere in `text`.

        Models sometimes plan several steps in prose and paste every call, some of which
        depend on earlier results (e.g. "<result of step 2>"). We run only the first call
        that names a real tool and has no placeholder values; the model then sees the
        real result and chooses the next step itself.
        """
        names = self._tool_names()
        decoder = json.JSONDecoder()
        pos = 0
        while True:
            start = text.find("{", pos)
            if start < 0:
                return None
            pos = start + 1
            try:
                obj, _end = decoder.raw_decode(text, start)
            except ValueError:
                continue
            if not isinstance(obj, dict) or not isinstance(obj.get("name"), str):
                continue
            if set(obj) - {"name", "parameters", "arguments", "args"}:
                continue
            name = self._resolve_name(obj["name"])
            if name not in names:
                continue
            args = obj.get("parameters", obj.get("arguments", obj.get("args", {})))
            if not isinstance(args, dict) or re.search(r"<[^<>\n]{3,}>", json.dumps(args)):
                continue
            return {"function": {"name": name, "arguments": args}}

    @staticmethod
    def _text_tool_calls(text):
        """Parse '{"name": ..., "parameters": {...}}' written as text into tool_calls, or None."""
        raw = text.strip()
        if raw.startswith("```"):
            raw = raw.strip("`").strip()
            if raw[:4].lower() == "json":
                raw = raw[4:].strip()
        try:
            data = json.loads(raw)
        except ValueError:
            return None
        items = [data] if isinstance(data, dict) else data
        if not isinstance(items, list) or not items:
            return None
        calls = []
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                return None
            if set(item) - {"name", "parameters", "arguments", "args"}:
                return None          # has other keys: probably a real JSON answer
            args = item.get("parameters", item.get("arguments", item.get("args", {})))
            calls.append({"function": {"name": item["name"], "arguments": args if isinstance(args, dict) else {}}})
        return calls

    # ------------------------------------------------------------------ tools

    def _run_tool(self, name, args):
        # Models often send `null` for optional parameters they don't need. Servers
        # reject that ("expected number, received null"); omitting the key is equivalent.
        if isinstance(args, dict):
            args = {k: v for k, v in args.items() if v is not None}
        self.tool_call.emit(name, json.dumps(args, ensure_ascii=False))

        # Ask the user (GUI thread) before running anything.
        holder = {"event": threading.Event(), "allow": False}
        self.approval_needed.emit(name, json.dumps(args, indent=2, ensure_ascii=False), holder)
        while not holder["event"].wait(0.2):
            if self._cancel.is_set():
                raise _Cancelled()

        failed = False
        if not holder["allow"]:
            text, is_error = "The user denied this tool call.", True
        elif self.mcp is None:
            text, is_error = "MCP is not available.", True
        else:
            try:
                text, is_error = self.mcp.call_tool(name, args, timeout=self.tool_timeout)
            except Exception as e:
                text, is_error = f"Error: {e}", True
            failed = is_error

        if failed:
            lowered = text.lower()
            if "unknown or disconnected tool" in lowered and self.tools:
                text += "\nAvailable tools: " + ", ".join(self._tool_names())
            hint = ""
            if "enoent" in lowered or "no such file" in lowered or "not found" in lowered:
                hint = (" If a path does not exist, do not guess: list the parent directory "
                        "or search to find the correct path.")
            # Small models tend to narrate ("I will call the tool...") instead of retrying.
            text += ("\n\nThe tool call failed. Check the arguments against the tool's schema "
                     "(omit optional arguments you don't need) and call the tool again." + hint)

        if len(text) > MAX_TOOL_RESULT_CHARS:
            text = text[:MAX_TOOL_RESULT_CHARS] + f"\n...[truncated, {len(text)} chars total]"
        preview = text if len(text) <= 300 else text[:300] + "..."
        self.tool_result.emit(name, preview, is_error)
        return text, is_error