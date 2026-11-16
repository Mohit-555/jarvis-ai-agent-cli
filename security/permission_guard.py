import json
import logging
import os

logger = logging.getLogger('jarvis.security.permissions')

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


class PermissionGuard:
    def __init__(self, config_path: str = None, mode: str = "normal"):
        self._config_path = config_path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "config", "tools_acl.yaml"
        )
        self.mode = mode.lower() if mode else "normal"
        self._rules: dict[str, dict] = {}
        self._load()

    def set_mode(self, mode: str):
        mode_val = mode.lower().strip() if mode else "normal"
        if mode_val not in ("normal", "power"):
            raise ValueError(f"Invalid mode: {mode}. Must be 'normal' or 'power'")
        self.mode = mode_val
        logger.info(f"PermissionGuard execution mode set to: {self.mode}")

    def _load(self):
        if not os.path.exists(self._config_path):
            self._rules = {"default": "confirm", "tools": {}}
            return
        try:
            if self._config_path.endswith((".yaml", ".yml")) and HAS_YAML:
                with open(self._config_path) as f:
                    self._rules = yaml.safe_load(f) or {}
            else:
                with open(self._config_path) as f:
                    self._rules = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load permissions: {e}")
            self._rules = {"default": "confirm", "tools": {}}

    def _save(self):
        os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
        try:
            if self._config_path.endswith((".yaml", ".yml")) and HAS_YAML:
                with open(self._config_path, "w") as f:
                    yaml.dump(self._rules, f)
            else:
                with open(self._config_path.replace(".yaml", ".json").replace(".yml", ".json"), "w") as f:
                    json.dump(self._rules, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save permissions: {e}")

    def get_permission(self, tool_name: str) -> str:
        tools = self._rules.get("tools", {})
        if tool_name in tools:
            rule = tools[tool_name]
            if isinstance(rule, dict):
                return rule.get("level", "confirm")
            return str(rule)
        return self._rules.get("default", "confirm")

    def is_allowed(self, tool_name: str, user: str = None) -> bool:
        return self.get_permission(tool_name) != "deny"

    def require_confirm(self, tool_name: str) -> bool:
        if self.mode == "power":
            return False
        return self.get_permission(tool_name) == "confirm"

    def set_permission(self, tool_name: str, level: str):
        if level not in ("auto", "confirm", "deny"):
            raise ValueError(f"Invalid permission level: {level}")
        tools = self._rules.setdefault("tools", {})
        if isinstance(tools.get(tool_name), dict):
            tools[tool_name]["level"] = level
        else:
            tools[tool_name] = level
        self._save()

    def set_default(self, level: str):
        if level not in ("auto", "confirm", "deny"):
            raise ValueError(f"Invalid permission level: {level}")
        self._rules["default"] = level
        self._save()
