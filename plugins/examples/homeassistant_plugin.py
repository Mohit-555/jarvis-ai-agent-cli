import logging

logger = logging.getLogger('jarvis.plugins.homeassistant')

try:
    from plugins.base_plugin import JarvisPlugin
except ImportError:
    from plugins.base_plugin import JarvisPlugin

try:
    import hassapi as hass
    HAS_HASS = True
except ImportError:
    HAS_HASS = False


class HomeAssistantPlugin(JarvisPlugin):
    name = "homeassistant"
    description = "Home Assistant integration for smart home control"
    version = "1.0.0"
    tools = [
        {"name": "ha_get_states", "description": "Get all entity states"},
        {"name": "ha_turn_on", "description": "Turn on an entity", "parameters": {"entity_id": {"type": "string"}}},
        {"name": "ha_turn_off", "description": "Turn off an entity", "parameters": {"entity_id": {"type": "string"}}},
        {"name": "ha_get_entities", "description": "List all entities"},
    ]

    def __init__(self):
        self._api = None
        self._config = {}
        self._base_url = ""
        self._token = ""

    def setup(self, config: dict = None):
        self._config = config or {}
        self._base_url = self._config.get("base_url", "http://localhost:8123")
        self._token = self._config.get("token", "")
        if self._base_url and self._token and HAS_HASS:
            try:
                self._api = hass.API(self._base_url, self._token)
                logger.info("Home Assistant plugin connected")
            except Exception as e:
                logger.error(f"Home Assistant auth failed: {e}")
        else:
            logger.warning("Home Assistant plugin: missing URL/token or hass-api not installed")

    def teardown(self):
        self._api = None
        logger.info("Home Assistant plugin torn down")

    async def _request(self, method: str, path: str, data: dict = None):
        if not self._api:
            return {"error": "Home Assistant not configured"}
        try:
            import httpx
            url = f"{self._base_url}/api/{path.lstrip('/')}"
            headers = {
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            }
            async with httpx.AsyncClient() as client:
                if method == "GET":
                    resp = await client.get(url, headers=headers)
                elif method == "POST":
                    resp = await client.post(url, headers=headers, json=data or {})
                else:
                    resp = await client.request(method, url, headers=headers, json=data or {})
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"Home Assistant request error: {e}")
            return {"error": str(e)}

    def get_states(self) -> dict:
        if not HAS_HASS:
            return {"states": [], "note": "hass-api not available (stub)"}
        return {"states": [], "note": "Home Assistant states stub"}

    def turn_on(self, entity: str) -> dict:
        return {"status": "ok", "action": "turn_on", "entity": entity, "note": "Stub"}

    def turn_off(self, entity: str) -> dict:
        return {"status": "ok", "action": "turn_off", "entity": entity, "note": "Stub"}

    def get_entities(self) -> dict:
        return {"entities": [], "note": "Home Assistant entities stub"}
