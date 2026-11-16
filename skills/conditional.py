from __future__ import annotations
import logging
from pathlib import Path
from typing import Callable

from skills.registry import SkillRegistry

logger = logging.getLogger('jarvis.skills.conditional')


class ConditionalSkillWatcher:
    def __init__(self, registry: SkillRegistry):
        self.registry = registry
        self._callbacks: list[Callable] = []

    def on_file_access(self, file_path: str) -> list[str]:
        matched = self.registry.list_by_path(file_path)
        if matched:
            names = [s.name for s in matched]
            logger.debug(f"Path '{file_path}' matched skills: {names}")
            for cb in self._callbacks:
                try:
                    cb(file_path, matched)
                except Exception as e:
                    logger.warning(f"Conditional callback error: {e}")
        return [s.name for s in matched]

    def on_change(self, callback: Callable):
        self._callbacks.append(callback)

    def get_relevant_skills(self, file_paths: list[str]) -> str:
        seen = set()
        blocks = []
        for fp in file_paths:
            skills = self.registry.list_by_path(fp)
            for s in skills:
                if s.name not in seen:
                    seen.add(s.name)
                    blocks.append(s.to_prompt_block())
        return '\n\n'.join(blocks)

    def get_path_skill_prompt(self, file_paths: list[str]) -> str:
        relevant = self.get_relevant_skills(file_paths)
        if relevant:
            return f"Active skills for current files:\n{relevant}"
        return ''
