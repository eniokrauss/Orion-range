from app.services.mitre_plugins.base import TechniqueAction
from app.services.mitre_plugins.builtin import BuiltinMitrePlugin


class MitreTechniqueNotFoundError(Exception):
    pass


class MitrePluginRegistry:
    def __init__(self) -> None:
        self._plugins = [BuiltinMitrePlugin()]

    def resolve_action(self, action: str) -> tuple[str, TechniqueAction | None]:
        if not action.lower().startswith("mitre:"):
            return action, None

        technique_id = action.split(":", maxsplit=1)[1]
        for plugin in self._plugins:
            resolved = plugin.resolve(technique_id)
            if resolved:
                return resolved.action, resolved

        raise MitreTechniqueNotFoundError(f"Unknown MITRE technique: {technique_id}")


mitre_plugin_registry = MitrePluginRegistry()
