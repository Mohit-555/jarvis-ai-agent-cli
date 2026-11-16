import logging

logger = logging.getLogger('jarvis.plugins.spotify')

try:
    from plugins.base_plugin import JarvisPlugin
except ImportError:
    from plugins.base_plugin import JarvisPlugin


class SpotifyPlugin(JarvisPlugin):
    name = "spotify"
    description = "Control Spotify playback"
    version = "1.0.0"
    tools = [
        {"name": "spotify_play", "description": "Resume playback"},
        {"name": "spotify_pause", "description": "Pause playback"},
        {"name": "spotify_next", "description": "Skip to next track"},
        {"name": "spotify_previous", "description": "Go to previous track"},
        {"name": "spotify_search", "description": "Search for tracks", "parameters": {"query": {"type": "string"}}},
    ]

    def __init__(self):
        self._client = None
        self._config = {}

    def setup(self, config: dict = None):
        self._config = config or {}
        client_id = self._config.get("client_id", "")
        client_secret = self._config.get("client_secret", "")
        if client_id and client_secret:
            logger.info("Spotify plugin configured")
        else:
            logger.warning("Spotify plugin: missing credentials")

    def teardown(self):
        self._client = None
        logger.info("Spotify plugin torn down")

    def play(self) -> dict:
        return {"status": "ok", "action": "play", "note": "Spotify playback resumed (stub)"}

    def pause(self) -> dict:
        return {"status": "ok", "action": "pause", "note": "Spotify playback paused (stub)"}

    def next(self) -> dict:
        return {"status": "ok", "action": "next", "note": "Skipped to next track (stub)"}

    def previous(self) -> dict:
        return {"status": "ok", "action": "previous", "note": "Went to previous track (stub)"}

    def search(self, query: str) -> dict:
        return {"status": "ok", "action": "search", "query": query, "results": [], "note": "Spotify search stub"}
