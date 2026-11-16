from __future__ import annotations
import logging
from pathlib import Path
from typing import Callable

from skills.base import Skill
from skills.loader import discover_all, discover_bundled, discover_user, discover_project

logger = logging.getLogger('jarvis.skills.registry')


class SkillRegistry:
    def __init__(self):
        self._skills: dict[str, Skill] = {}
        self._on_discover: list[Callable] = []

    def discover(self, project_path: str | Path | None = None):
        skills = discover_all(project_path)
        self._skills.clear()
        for skill in skills:
            key = skill.name.lower().replace(' ', '_').replace('-', '_')
            self._skills[key] = skill
        for cb in self._on_discover:
            try:
                cb(self._skills)
            except Exception as e:
                logger.warning(f"Skill discover callback error: {e}")
        logger.info(f"Registry loaded {len(self._skills)} skills")

    def get(self, name_or_key: str) -> Skill | None:
        key = name_or_key.lower().replace(' ', '_').replace('-', '_')
        if key in self._skills:
            return self._skills[key]
        for skill in self._skills.values():
            if skill.name.lower() == name_or_key.lower():
                return skill
        return None

    def list_skills(self) -> list[Skill]:
        return list(self._skills.values())

    def list_by_source(self, source: str) -> list[Skill]:
        return [s for s in self._skills.values() if s.source == source]

    def list_by_path(self, file_path: str) -> list[Skill]:
        matching = []
        for skill in self._skills.values():
            if skill.paths:
                for pattern in skill.paths:
                    if skill.matches_path(file_path):
                        matching.append(skill)
                        break
        return matching

    def get_all_for_prompt(self) -> str:
        blocks = []
        for skill in self._skills.values():
            if skill.user_invocable:
                blocks.append(skill.to_prompt_block())
        return '\n\n'.join(blocks)

    def on_discover(self, callback: Callable):
        self._on_discover.append(callback)

    def count(self) -> int:
        return len(self._skills)

    def get_tool_specs(self) -> list[dict]:
        specs = []
        for skill in self._skills.values():
            if skill.user_invocable:
                spec = skill.to_tool_spec()
                if spec:
                    specs.append(spec)
        return specs
