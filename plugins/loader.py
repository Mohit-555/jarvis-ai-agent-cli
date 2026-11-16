import importlib
import inspect
import logging
import os
import pkgutil

logger = logging.getLogger('jarvis.plugins.loader')


class PluginLoader:
    def __init__(self, plugin_dir: str = None):
        if plugin_dir is None:
            plugin_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugins")
        self._plugin_dir = plugin_dir
        self._loaded: dict[str, object] = {}

    def discover(self, path: str = None) -> list[str]:
        search_path = path or self._plugin_dir
        if not os.path.isdir(search_path):
            return []
        plugins = []
        EXCLUDED = {"base_plugin", "loader", "__pycache__"}
        for entry in sorted(os.listdir(search_path)):
            if entry.startswith("_") or entry.startswith("."):
                continue
            name = entry[:-3] if entry.endswith(".py") else entry
            if name in EXCLUDED:
                continue
            plugin_path = os.path.join(search_path, entry)
            if os.path.isdir(plugin_path) and os.path.isfile(os.path.join(plugin_path, "__init__.py")):
                inner_plugins = self.discover(path=plugin_path)
                for inner in inner_plugins:
                    plugins.append(f"{entry}.{inner}")
            elif entry.endswith(".py") and not entry.startswith("_"):
                plugins.append(entry[:-3])
        return sorted(plugins)

    def load(self, plugin_name: str) -> object:
        if plugin_name in self._loaded:
            return self._loaded[plugin_name]
        try:
            module = importlib.import_module(f"plugins.{plugin_name}")
            plugin_classes = [
                cls for _, cls in inspect.getmembers(module, inspect.isclass)
                if issubclass(cls, object) and cls.__module__ == module.__name__
            ]
            from plugins.base_plugin import JarvisPlugin
            for cls in plugin_classes:
                if issubclass(cls, JarvisPlugin) and cls is not JarvisPlugin:
                    instance = cls()
                    self._loaded[plugin_name] = instance
                    logger.info(f"Loaded plugin: {plugin_name}")
                    return instance
            raise ImportError(f"No JarvisPlugin subclass found in {plugin_name}")
        except Exception as e:
            logger.error(f"Failed to load plugin '{plugin_name}': {e}")
            raise

    def load_all(self) -> list[object]:
        plugins = []
        for name in self.discover():
            try:
                instance = self.load(name)
                plugins.append(instance)
            except Exception as e:
                logger.error(f"Skipping plugin '{name}': {e}")
        return plugins

    def get(self, name: str) -> object | None:
        return self._loaded.get(name)

    def unload(self, name: str):
        if name in self._loaded:
            try:
                self._loaded[name].teardown()
            except Exception as e:
                logger.error(f"Plugin teardown error '{name}': {e}")
            del self._loaded[name]
