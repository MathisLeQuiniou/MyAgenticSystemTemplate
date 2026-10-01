"""Skills: packaged, on-demand instructions for agents.

A skill is a folder under `backend/skills/` (Anthropic "Agent Skills" format):

    backend/skills/<name>/
    ├── SKILL.md          # YAML front matter (name, description) + instructions
    ├── references/...    # optional files the instructions point to
    └── templates/...

Only `name` + `description` are put in the agent's system prompt (the catalog).
The agent loads the full instructions with the `load_skill` tool when a task
matches, and opens referenced files with `read_skill_file`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from backend.config import get_settings
from backend.utils import get_logger

log = get_logger(__name__)

SKILL_FILE = "SKILL.md"
_FRONT_MATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)
_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    path: Path  # skill folder
    metadata: dict[str, Any] = field(default_factory=dict)  # other front-matter keys

    @property
    def body(self) -> str:
        """Instructions of SKILL.md, without the front matter (read on demand)."""
        text = (self.path / SKILL_FILE).read_text(encoding="utf-8")
        match = _FRONT_MATTER.match(text)
        return (match.group(2) if match else text).strip()

    def files(self) -> list[str]:
        """Relative paths of the skill's extra files (everything but SKILL.md)."""
        return sorted(
            str(p.relative_to(self.path))
            for p in self.path.rglob("*")
            if p.is_file() and p.name != SKILL_FILE and not p.name.startswith(".")
        )

    def read_file(self, relative_path: str) -> str:
        """Read a file of the skill; refuses paths escaping the skill folder."""
        target = (self.path / relative_path).resolve()
        if not target.is_relative_to(self.path.resolve()):
            raise ValueError(f"'{relative_path}' is outside the skill folder")
        if not target.is_file():
            raise FileNotFoundError(f"No file '{relative_path}' in skill '{self.name}'. Files: {', '.join(self.files()) or '-'}")
        return target.read_text(encoding="utf-8")


def parse_skill(folder: Path) -> Skill:
    text = (folder / SKILL_FILE).read_text(encoding="utf-8")
    match = _FRONT_MATTER.match(text)
    if not match:
        raise ValueError("SKILL.md must start with a YAML front matter block (--- name/description ---)")
    meta = yaml.safe_load(match.group(1)) or {}
    name, description = str(meta.pop("name", "")).strip(), " ".join(str(meta.pop("description", "")).split())
    if not _NAME.match(name):
        raise ValueError(f"invalid skill name '{name}' (lowercase letters, digits and dashes)")
    if name != folder.name:
        raise ValueError(f"skill name '{name}' must match its folder name '{folder.name}'")
    if not description:
        raise ValueError("a skill needs a `description` (it is what makes the agent pick it)")
    return Skill(name=name, description=description, path=folder, metadata=meta)


class SkillRegistry:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or get_settings().skills_dir
        self._skills: dict[str, Skill] = {}
        self.load()

    def load(self) -> None:
        self._skills.clear()
        if not self.root.is_dir():
            return
        for folder in sorted(p for p in self.root.iterdir() if (p / SKILL_FILE).is_file()):
            try:
                skill = parse_skill(folder)
                self._skills[skill.name] = skill
            except Exception as exc:  # noqa: BLE001
                log.warning("Skipping skill '%s': %s", folder.name, exc)
        if self._skills:
            log.info("Skills loaded: %s", ", ".join(self._skills))

    def get(self, name: str) -> Skill:
        try:
            return self._skills[name]
        except KeyError:
            raise KeyError(f"Unknown skill '{name}'. Available: {', '.join(self._skills) or '-'}") from None

    def get_many(self, names: list[str] | tuple[str, ...]) -> list[Skill]:
        """Resolve skill names; `["*"]` means every skill."""
        if list(names) == ["*"]:
            return self.all()
        return [self.get(n) for n in names]

    def all(self) -> list[Skill]:
        return list(self._skills.values())


@lru_cache
def get_skill_registry() -> SkillRegistry:
    return SkillRegistry()
