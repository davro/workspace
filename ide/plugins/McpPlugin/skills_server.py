"""
Stdio MCP server that serves skills. The IDE launches it like any other server
(McpPlugin adds the entry to servers.json automatically).

  tools:   list_skills, load_skill(name, compact=False)
  prompts: one per skill (shows up in any MCP client that supports prompts)
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # so `skills` imports in a subprocess
from skills import SkillRegistry                           # noqa: E402

try:                                                       # mcp 2.x
    from mcp.server.mcpserver import MCPServer as FastMCP   # noqa: E402
except ImportError:                                         # mcp 1.x
    from mcp.server.fastmcp import FastMCP                  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--root", action="append", required=True, help="skills directory (repeatable)")
args = ap.parse_args()

reg = SkillRegistry(args.root)
mcp = FastMCP("skills")


@mcp.tool()
def list_skills() -> str:
    """List the available skills with a one-line description each."""
    skills = reg.scan()
    return "\n".join(f"{s['name']}: {s['description']}" for s in skills.values()) or "No skills found."


@mcp.tool()
def load_skill(name: str, compact: bool = True) -> str:
    """Load the full step-by-step instructions of a skill by name. Follow them after loading."""
    return reg.load(name, compact)


def _register_prompt(skill_name: str, description: str):
    @mcp.prompt(name=skill_name, description=description[:200])
    def _prompt(code: str = "") -> str:
        body = reg.load(skill_name)
        return f"{body}\n\n---\nApply this skill to:\n\n{code}" if code else body


for _s in reg.scan().values():
    _register_prompt(_s["name"], _s["description"])

if __name__ == "__main__":
    mcp.run()