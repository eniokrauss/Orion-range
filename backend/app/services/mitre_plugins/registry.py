from app.services.mitre_plugins.base import MitrePlugin, TechniqueAction
from app.services.mitre_plugins.builtin import BuiltinMitrePlugin


class MitreTechniqueNotFoundError(Exception):
    pass


class MitrePluginRegistry:
    def __init__(self) -> None:
        self._plugins: list[MitrePlugin] = []
        self.register(BuiltinMitrePlugin())

    def register(self, plugin: MitrePlugin) -> None:
        self._plugins.append(plugin)

    def resolve_action(self, action: str) -> tuple[str, TechniqueAction | None]:
        if not action.lower().startswith("mitre:"):
            return action, None

        technique_id = action.split(":", maxsplit=1)[1]
        for plugin in self._plugins:
            resolved = plugin.resolve(technique_id)
            if resolved:
                return resolved.action, resolved

        raise MitreTechniqueNotFoundError(f"Unknown MITRE technique: {technique_id}")

    def list_techniques(self) -> list[dict]:
        techniques: list[dict] = []
        for plugin in self._plugins:
            for technique in plugin.list_techniques():
                techniques.append(
                    {
                        "plugin": plugin.plugin_name,
                        "technique_id": technique.technique_id,
                        "name": technique.name,
                        "action": technique.action,
                        "description": technique.description,
                        "tactics": list(technique.tactics),
                    }
                )
        return sorted(techniques, key=lambda item: item["technique_id"])


mitre_plugin_registry = MitrePluginRegistry()
