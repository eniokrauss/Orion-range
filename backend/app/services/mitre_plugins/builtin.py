from app.services.mitre_plugins.base import TechniqueAction


class BuiltinMitrePlugin:
    plugin_name = "builtin"

    _techniques = {
        "T1566": TechniqueAction(
            technique_id="T1566",
            name="Phishing",
            action="inject-phishing-email",
            description="Send a controlled phishing email to a target mailbox.",
            tactics=("initial-access",),
        ),
        "T1110": TechniqueAction(
            technique_id="T1110",
            name="Brute Force",
            action="simulate-password-spray",
            description="Trigger a password spraying simulation with tuned safeguards.",
            tactics=("credential-access",),
        ),
        "T1041": TechniqueAction(
            technique_id="T1041",
            name="Exfiltration Over C2 Channel",
            action="simulate-c2-exfiltration",
            description="Generate safe exfil-like telemetry over C2-like channel.",
            tactics=("exfiltration", "command-and-control"),
        ),
    }

    def resolve(self, technique_id: str) -> TechniqueAction | None:
        normalized = technique_id.strip().upper()
        return self._techniques.get(normalized)

    def list_techniques(self) -> list[TechniqueAction]:
        return list(self._techniques.values())
