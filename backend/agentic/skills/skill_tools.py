"""Tools that let an agent load its skills on demand."""

from __future__ import annotations

from collections.abc import Sequence

from langchain_core.tools import BaseTool, StructuredTool

from backend.agentic.skills.registry import Skill
from backend.config import get_settings

LOAD_SKILL = "load_skill"
READ_SKILL_FILE = "read_skill_file"
SKILL_TOOL_NAMES = {LOAD_SKILL, READ_SKILL_FILE}


def _truncate(text: str) -> str:
    limit = get_settings().skill_max_file_chars
    return text if len(text) <= limit else text[:limit] + f"\n... <truncated, {len(text) - limit} more chars>"


def skills_catalog(skills: Sequence[Skill]) -> str:
    """Block appended to the system prompt of an agent that has skills."""
    lines = "\n".join(f"- `{s.name}`: {s.description}" for s in skills)
    return (
        "## Skills\n"
        "Skills are packaged instructions for specific tasks. When the task matches a skill's "
        f"description, call `{LOAD_SKILL}` with its name BEFORE doing the task, then follow its "
        f"instructions. Use `{READ_SKILL_FILE}` to open the files a skill refers to.\n\n"
        f"Available skills:\n{lines}"
    )


def make_skill_tools(skills: Sequence[Skill]) -> list[BaseTool]:
    """`load_skill` + `read_skill_file`, restricted to the given skills."""
    allowed = {s.name: s for s in skills}

    def _get(name: str) -> Skill:
        if name not in allowed:
            raise ValueError(f"Unknown skill '{name}'. Available: {', '.join(allowed)}")
        return allowed[name]

    def load_skill(name: str) -> str:
        skill = _get(name)
        files = skill.files()
        extra = f"\n\n---\nFiles in this skill (open with {READ_SKILL_FILE}): {', '.join(files)}" if files else ""
        return _truncate(f"# Skill: {skill.name}\n\n{skill.body}{extra}")

    def read_skill_file(name: str, path: str) -> str:
        return _truncate(_get(name).read_file(path))

    names = ", ".join(allowed)
    return [
        StructuredTool.from_function(
            load_skill,
            name=LOAD_SKILL,
            description=f"Load the full instructions of a skill. Available skills: {names}.",
        ),
        StructuredTool.from_function(
            read_skill_file,
            name=READ_SKILL_FILE,
            description="Read a file bundled with a skill (e.g. 'references/formulas.md'), as listed by load_skill.",
        ),
    ]
