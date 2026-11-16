from __future__ import annotations
import re
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Skill:
    name: str
    description: str
    when_to_use: str = ''
    allowed_tools: list[str] | None = None
    arguments: str | None = None
    argument_hint: str | None = None
    paths: list[str] | None = None
    model: str | None = None
    user_invocable: bool = True
    context: str = 'fork'
    effort: int | str = 'auto'
    version: str = '1.0'
    source: str = 'bundled'
    file_path: str | None = None
    content: str = ''
    shell: str | None = None
    hooks: dict | None = None
    agent: str | None = None

    def matches_path(self, file_path: str) -> bool:
        if not self.paths:
            return False
        from pathlib import PurePath
        pp = PurePath(file_path)
        for pattern in self.paths:
            if pp.match(pattern):
                return True
            if '**' in pattern:
                flat = pattern.replace('**/', '')
                if pp.match(flat):
                    return True
        return False

    def to_prompt_block(self) -> str:
        parts = [f"## Skill: {self.name}"]
        if self.description:
            parts.append(f"Description: {self.description}")
        if self.when_to_use:
            parts.append(f"When to use: {self.when_to_use}")
        if self.allowed_tools:
            parts.append(f"Allowed tools: {', '.join(self.allowed_tools)}")
        if self.content:
            parts.append(f"\n{self.content}")
        return '\n'.join(parts)

    def to_tool_spec(self) -> dict:
        spec = {
            'name': f'skill__{self.name.lower().replace(" ", "_").replace("-", "_")}',
            'description': f'[SKILL] {self.description}',
            'handler': None,
            'parameters': {
                'type': 'object',
                'properties': {},
            },
        }
        if self.arguments:
            spec['parameters']['properties'][self.arguments] = {
                'type': 'string',
                'description': self.argument_hint or self.arguments,
            }
            spec['parameters']['required'] = [self.arguments] if self.arguments else []
        return spec


SKILL_FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n?(.*)$', re.DOTALL)


def parse_skill_file(file_path: str | Path) -> Skill | None:
    file_path = Path(file_path)
    if not file_path.exists():
        return None

    content = file_path.read_text(encoding='utf-8')
    match = SKILL_FRONTMATTER_RE.match(content)
    if not match:
        return None

    raw_frontmatter = match.group(1)
    body = match.group(2).strip()

    try:
        meta = yaml.safe_load(raw_frontmatter)
    except yaml.YAMLError:
        return None

    if not meta or not meta.get('name'):
        return None

    source = 'user'
    if 'bundled' in str(file_path):
        source = 'bundled'
    elif 'project' in str(file_path):
        source = 'project'

    allowed_tools = meta.get('allowed-tools') or meta.get('allowed_tools')
    if isinstance(allowed_tools, str):
        allowed_tools = [t.strip() for t in allowed_tools.split(',')]

    paths = meta.get('paths')
    if isinstance(paths, str):
        paths = [p.strip() for p in paths.split(',')]

    return Skill(
        name=meta['name'],
        description=meta.get('description', ''),
        when_to_use=meta.get('when_to_use', '') or meta.get('when-to-use', ''),
        allowed_tools=allowed_tools,
        arguments=meta.get('arguments'),
        argument_hint=meta.get('argument-hint') or meta.get('argument_hint'),
        paths=paths,
        model=meta.get('model'),
        user_invocable=meta.get('user-invocable', True) if meta.get('user-invocable') is not None else meta.get('user_invocable', True),
        context=meta.get('context', 'fork'),
        effort=meta.get('effort', 'auto'),
        version=str(meta.get('version', '1.0')),
        source=source,
        file_path=str(file_path),
        content=body,
        shell=meta.get('shell'),
        hooks=meta.get('hooks'),
        agent=meta.get('agent'),
    )
