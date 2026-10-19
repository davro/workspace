"""
Skills support for the MCP plugin (pure Python, no Qt, no mcp import).

A skill is  <root>/<name>/SKILL.md  with YAML-ish frontmatter (name, description, ...).
Files are re-read on every call, so edits show up without reloading the IDE.
Later roots override earlier ones (user-level first, project-level last).
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_FM = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.S)

# Sections that keep big models disciplined but only burn context on 7B-14B models.
_DROP_FOR_COMPACT = {"common rationalizations (and rebuttals)", "common rationalizations",
                     "red flags", "references"}


def parse_skill(path: Path) -> Tuple[dict, str]:
    """Return (frontmatter dict, markdown body)."""
    text = Path(path).read_text(encoding="utf-8")
    m = _FM.match(text)
    if not m:
        return {}, text.strip()
    raw, body = m.groups()
    try:
        import yaml
        meta = yaml.safe_load(raw) or {}
        if not isinstance(meta, dict):
            meta = {}
    except Exception:                       # no PyYAML, or bad YAML: top-level "key: value" only
        meta = {}
        for line in raw.splitlines():
            if ":" in line and not line.startswith((" ", "\t", "-")):
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip("\"'")
    return meta, body.strip()


def compact(body: str) -> str:
    """Drop rationalization / red-flag / reference sections."""
    parts = re.split(r"(?m)^(?=## )", body)
    keep = []
    for p in parts:
        if p.startswith("## ") and p.splitlines()[0][3:].strip().lower() in _DROP_FOR_COMPACT:
            continue
        keep.append(p)
    return "".join(keep).strip()


def parse_steps(body: str) -> List[Tuple[int, str, str]]:
    """
    Split a skill into its '### Step N: Title' sections -> [(N, title, text)].
    `text` is the numbered questions plus the '**Deliver:**' line, up to the next heading.
    """
    out = []
    for m in re.finditer(r"(?ms)^###[ \t]+Step[ \t]+(\d+)[ \t]*[:.\-\u2013\u2014]?[ \t]*([^\n]*)\n(.*?)(?=^#{2,3}[ \t]|\Z)", body):
        out.append((int(m.group(1)), m.group(2).strip(), m.group(3).strip()))
    return out


def parse_checklist(body: str) -> List[str]:
    """Items of the '## Verification' section ('- [ ] ...' lines)."""
    m = re.search(r"(?ms)^##[ \t]+Verification[ \t]*\n(.*?)(?=^##[ \t]|\Z)", body)
    if not m:
        return []
    return [x.strip() for x in re.findall(r"(?m)^[ \t]*[-*][ \t]*\[[ xX]\][ \t]*(.+)$", m.group(1))]


def default_skill_roots(workspace=None, config_dir=None) -> List[Path]:
    """
    Where skills are looked for, lowest priority first (a later root overrides a skill of the same name):
      1. bundled    <this plugin>/skills/   ships with the IDE - no separate repo needed
      2. user       <config_dir>/skills/    the user's own skills, for every workspace
      3. project    <workspace>/skills/     skills that belong to one project
    """
    import os

    def clean(p):                      # '/ws/dev/..' -> '/ws'; also expands '~'
        return Path(os.path.abspath(os.path.expanduser(str(p))))

    roots = [Path(__file__).resolve().parent / "skills"]
    if config_dir:
        roots.append(clean(config_dir) / "skills")
    if workspace:
        roots.append(clean(workspace) / "skills")
    return roots


def ensure_skills_server(manager, roots, python=None) -> bool:
    """
    Keep servers.json's 'skills' entry pointing at this plugin's skills_server.py with the current roots.
    Call it on every start: moving the repo, switching venv or workspace then heals itself.
    A 'skills' entry that runs something else is the user's own and is left alone; extra keys
    (env, disabled, ...) of our entry are preserved. Returns True if the file was changed.
    """
    import sys
    script = Path(__file__).resolve().parent / "skills_server.py"
    wanted = {"command": python or sys.executable,
              "args": [str(script)] + [a for r in roots for a in ("--root", str(r))]}
    current = manager.load_config().get("skills")
    if current is not None and Path((current.get("args") or [""])[0]).name != "skills_server.py":
        return False
    if current is not None and all(current.get(k) == v for k, v in wanted.items()):
        return False
    manager.add_server_to_config("skills", {**(current or {}), **wanted})
    return True


class SkillRegistry:
    def __init__(self, roots: List):
        self.roots = [Path(r).expanduser() for r in roots]

    def scan(self) -> Dict[str, dict]:
        skills: Dict[str, dict] = {}
        for root in self.roots:
            if not root.is_dir():
                continue
            for f in sorted(root.glob("*/SKILL.md")):
                try:
                    meta, _ = parse_skill(f)
                except Exception:
                    continue
                name = str(meta.get("name") or f.parent.name).strip()
                skills[name] = {
                    "name": name,
                    "description": " ".join(str(meta.get("description", "")).split()),
                    "category": meta.get("category"),
                    "path": f,
                }
        return skills

    def load(self, name: str, compact_mode: bool = False) -> str:
        skills = self.scan()
        s = skills.get(name)
        if not s:
            return f"Unknown skill '{name}'. Available: {', '.join(skills) or '(none)'}"
        _, body = parse_skill(s["path"])
        return compact(body) if compact_mode else body

    def plan(self, name: str) -> Tuple[List[Tuple[int, str, str]], List[str]]:
        """(steps, verification checklist) of a skill; steps is [] if it has no step structure."""
        s = self.scan().get(name)
        if not s:
            return [], []
        _, body = parse_skill(s["path"])
        return parse_steps(body), parse_checklist(body)

    def index_prompt(self, tool_name: Optional[str] = None) -> str:
        """
        System-prompt index. Pass tool_name (e.g. 'skills__load_skill') to tell the model
        it may load skills itself; leave None when loading is slash-command only.
        """
        skills = self.scan()
        if not skills:
            return ""
        lines = "\n".join(f"- {s['name']}: {s['description']}" for s in skills.values())
        if tool_name:
            head = (f"You have skills (structured procedures for specific tasks). If one clearly "
                    f"applies, call {tool_name} with its name BEFORE answering, then follow it.")
        else:
            head = "Skills available to the user (they activate them with /skill-name):"
        return head + "\n" + lines


# ---------------------------------------------------------------------------
# Bare filename -> absolute path (so small models never have to *search*)
# ---------------------------------------------------------------------------
import os
import time

SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv", "env",
             "dist", "build", ".idea", ".vscode", ".mypy_cache", ".pytest_cache",
             ".tox", "site-packages", ".cache"}
# A bare filename ("FileMonitor.py") or a relative path ("core/FileMonitor.py", "workspace-dev/ide/core/FileMonitor.py").
# Absolute paths are never touched: the lookbehind refuses to start right after a "/".
_BARE = r"[\w-][\w.-]*\.[A-Za-z0-9]{1,8}"
_FILE_TOKEN = re.compile(r"(?<![\w/\\.~:-])((?:[\w-][\w.-]*/)*" + _BARE + r")(?![\w/\\])")


def replace_token(text: str, token: str, path: str) -> str:
    """Replace one filename/relative-path token in `text` with `path` (not inside a longer path)."""
    return re.sub(r"(?<![\w/\\.-])" + re.escape(token) + r"(?![\w/\\])", lambda _m: path, text)


def _shared_dir_parts(a: str, b: str) -> int:
    """How many leading directory components two paths have in common."""
    n = 0
    for x, y in zip(Path(a).parent.parts, Path(b).parent.parts):
        if x != y:
            break
        n += 1
    return n


def _pick_best(candidates: List[str], scores: List[int]) -> Optional[str]:
    """The candidate with the strictly highest positive score, else None (tie / no signal)."""
    best = max(scores)
    if best > 0 and scores.count(best) == 1:
        return candidates[scores.index(best)]
    return None


def resolve_filenames(text: str, root, current_file: Optional[str] = None,
                      max_seconds: float = 2.0) -> Tuple[str, List[str], Dict[str, List[str]]]:
    """
    Find filenames / partial paths in `text` under `root` and replace each with its absolute path.
    No git needed. Breadth-first (shallow matches first), skipping hidden dirs, SKIP_DIRS, symlinks
    and virtualenvs (any dir with pyvenv.cfg).

    When a name matches several files it is narrowed, in code and without the model, by
      1. words in the message that name a directory ("FileMonitor.py in workspace-dev"), then
      2. the project of the file open in the editor (`current_file`): the nearest one wins.
    Whatever is still ambiguous is NOT guessed: it is returned for the caller to ask about.

    Returns (new_text, notes, ambiguous) where ambiguous maps token -> candidate paths.
    """
    from collections import deque

    tokens = {m.group(1) for m in _FILE_TOKEN.finditer(text)}
    if not tokens:
        return text, [], {}
    by_base: Dict[str, List[str]] = {}
    for t in tokens:
        by_base.setdefault(t.rsplit("/", 1)[-1], []).append(t)
    found: Dict[str, List[str]] = {t: [] for t in tokens}
    deadline = time.monotonic() + max_seconds
    timed_out = False
    done_depth: Optional[int] = None
    queue = deque([(str(root), 0)])

    while queue:
        if time.monotonic() > deadline:
            timed_out = True
            break
        directory, depth = queue.popleft()
        if done_depth is not None and depth > done_depth:
            break
        try:
            entries = list(os.scandir(directory))
        except OSError:
            continue
        files = {e.name for e in entries if e.is_file(follow_symlinks=False)}
        if "pyvenv.cfg" in files:                       # a virtualenv: never search inside
            continue
        for base in by_base.keys() & files:
            full = os.path.join(directory, base)
            for t in by_base[base]:
                if ("/" not in t or full.endswith("/" + t)) and len(found[t]) < 8:
                    found[t].append(full)
        if done_depth is None and all(found.values()):
            done_depth = depth
        for e in entries:
            if e.is_dir(follow_symlinks=False) and e.name not in SKIP_DIRS and not e.name.startswith("."):
                queue.append((e.path, depth + 1))

    words = set(re.findall(r"[\w.-]+", text))
    notes: List[str] = []
    ambiguous: Dict[str, List[str]] = {}
    for token, hits in found.items():
        if len(hits) > 1:
            # 1. a word in the message names one candidate's directory (and not the others')
            own = set(token.split("/"))
            hint_scores = [len((set(Path(h).parent.parts) & words) - own) for h in hits]
            chosen = _pick_best(hits, hint_scores)
            why = "named in your message"
            # 2. nearest to the file open in the editor
            if chosen is None and current_file:
                chosen = _pick_best(hits, [_shared_dir_parts(h, current_file) for h in hits])
                why = "same project as the open file"
            if chosen is not None:
                notes.append(f"'{token}' matched {len(hits)} files; using {chosen} ({why}).")
                hits = [chosen]
        if len(hits) == 1:
            text = replace_token(text, token, hits[0])
        elif len(hits) > 1:
            ambiguous[token] = hits
    missing = [t for t, h in found.items() if not h]
    if timed_out and missing:
        notes.append(f"Search stopped after {max_seconds:.0f}s without finding: {', '.join(missing)}. "
                     f"If those are files, give the full path.")
    return text, notes, ambiguous