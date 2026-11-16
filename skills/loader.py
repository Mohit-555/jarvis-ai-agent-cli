from __future__ import annotations
import logging
from pathlib import Path
from typing import Generator

from core.config import CONFIG_DIR
from skills.base import Skill, parse_skill_file

logger = logging.getLogger('jarvis.skills.loader')

BUNDLED_DIR = Path(__file__).parent / 'bundled'
USER_SKILLS_DIR = CONFIG_DIR / 'skills'
PROJECT_SKILL_DIR_NAME = '.jarvis-skills'


def discover_bundled() -> list[Skill]:
    return _discover_from_dir(BUNDLED_DIR, source='bundled')


def discover_user() -> list[Skill]:
    USER_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    return _discover_from_dir(USER_SKILLS_DIR, source='user')


def discover_project(project_path: str | Path | None = None) -> list[Skill]:
    if project_path is None:
        project_path = Path.cwd()
    project_path = Path(project_path)
    skill_dir = project_path / PROJECT_SKILL_DIR_NAME
    if skill_dir.exists():
        return _discover_from_dir(skill_dir, source='project')
    return []


def _discover_from_dir(directory: Path, source: str = 'user') -> list[Skill]:
    skills: list[Skill] = []
    if not directory.exists():
        return skills

    md_files = list(directory.rglob('*.md'))
    for md_file in md_files:
        try:
            skill = parse_skill_file(md_file)
            if skill:
                skill.source = source
                skills.append(skill)
                logger.debug(f"Loaded skill '{skill.name}' from {md_file}")
        except Exception as e:
            logger.warning(f"Failed to load skill from {md_file}: {e}")
    return skills


def discover_all(project_path: str | Path | None = None) -> list[Skill]:
    skills: list[Skill] = []
    skills.extend(discover_bundled())
    skills.extend(discover_user())
    skills.extend(discover_project(project_path))

    seen: set[str] = set()
    unique: list[Skill] = []
    for skill in skills:
        key = skill.name.lower().replace(' ', '-')
        if key not in seen:
            seen.add(key)
            unique.append(skill)
        else:
            logger.debug(f"Duplicate skill '{skill.name}' from {skill.source}, skipping")

    logger.info(f"Discovered {len(unique)} skills ({len(skills)} total with duplicates)")
    return unique


def save_user_skill(file_path: str, name: str, description: str, content: str, **kwargs) -> Skill:
    USER_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    skill_path = Path(file_path)
    if not skill_path.is_absolute():
        skill_path = USER_SKILLS_DIR / skill_path

    frontmatter = {
        'name': name,
        'description': description,
        'version': kwargs.get('version', '1.0'),
        'user-invocable': kwargs.get('user_invocable', True),
    }
    if kwargs.get('when_to_use'):
        frontmatter['when-to-use'] = kwargs['when_to_use']
    if kwargs.get('allowed_tools'):
        frontmatter['allowed-tools'] = kwargs['allowed_tools']
    if kwargs.get('arguments'):
        frontmatter['arguments'] = kwargs['arguments']
    if kwargs.get('paths'):
        frontmatter['paths'] = kwargs['paths']
    if kwargs.get('model'):
        frontmatter['model'] = kwargs['model']

    import yaml
    skill_content = f"---\n{yaml.dump(frontmatter, default_flow_style=False).strip()}\n---\n\n{content}\n"
    skill_path.write_text(skill_content)

    return parse_skill_file(skill_path)
