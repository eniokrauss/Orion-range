import ipaddress

from app.core.errors import ErrorCode
from app.schemas.blueprint import LabBlueprint

SUPPORTED_BLUEPRINT_SCHEMA_VERSIONS = {"1.0"}


class BlueprintError(Exception):
    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _duplicate_values(values: list[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def validate_blueprint(bp: LabBlueprint) -> None:
    if bp.schema_version not in SUPPORTED_BLUEPRINT_SCHEMA_VERSIONS:
        raise BlueprintError(
            ErrorCode.UNSUPPORTED_BLUEPRINT_SCHEMA,
            (
                f"Unsupported blueprint schema version '{bp.schema_version}'. "
                f"Supported versions: {sorted(SUPPORTED_BLUEPRINT_SCHEMA_VERSIONS)}"
            ),
        )

    net_names = [network.name for network in bp.networks]
    duplicate_networks = _duplicate_values(net_names)
    if duplicate_networks:
        raise BlueprintError(
            ErrorCode.DUPLICATE_NETWORK_NAME,
            f"Duplicate network names are not allowed: {sorted(duplicate_networks)}",
        )

    for network in bp.networks:
        if network.cidr:
            try:
                ipaddress.ip_network(network.cidr, strict=False)
            except ValueError as exc:
                raise BlueprintError(
                    ErrorCode.INVALID_CIDR,
                    f"Network '{network.name}' has an invalid CIDR: '{network.cidr}'.",
                ) from exc

    node_names = [node.name for node in bp.nodes]
    duplicate_nodes = _duplicate_values(node_names)
    if duplicate_nodes:
        raise BlueprintError(
            ErrorCode.DUPLICATE_NODE_NAME,
            f"Duplicate node names are not allowed: {sorted(duplicate_nodes)}",
        )

    known_networks = set(net_names)
    for node in bp.nodes:
        if not node.networks:
            raise BlueprintError(
                ErrorCode.NODE_WITHOUT_NETWORK,
                f"Node '{node.name}' must reference at least one network.",
            )

        duplicate_node_networks = _duplicate_values(node.networks)
        if duplicate_node_networks:
            raise BlueprintError(
                ErrorCode.DUPLICATE_NODE_NETWORK,
                f"Node '{node.name}' has duplicate network references: {sorted(duplicate_node_networks)}",
            )

        unknown_networks = sorted(set(node.networks) - known_networks)
        if unknown_networks:
            raise BlueprintError(
                ErrorCode.UNKNOWN_NETWORK_REFERENCE,
                (
                    f"Node '{node.name}' references unknown networks: {unknown_networks}. "
                    "Declare the network in blueprint.networks first."
                ),
            )
