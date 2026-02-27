codex/verify-the-structure-m8z187
import ipaddress

main
from app.schemas.blueprint import LabBlueprint


class BlueprintError(Exception):
    pass


def _duplicate_values(values: list[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def validate_blueprint(bp: LabBlueprint) -> None:
codex/verify-the-structure-m8z187
    net_names = [network.name for network in bp.networks]
main
    duplicate_networks = _duplicate_values(net_names)
    if duplicate_networks:
        raise BlueprintError(f"Duplicate network names are not allowed: {sorted(duplicate_networks)}")

codex/verify-the-structure-m8z187
main
    for network in bp.networks:
        if network.cidr:
            try:
                ipaddress.ip_network(network.cidr, strict=False)
            except ValueError as exc:
                raise BlueprintError(
                    f"Network '{network.name}' has an invalid CIDR: '{network.cidr}'."
                ) from exc

    node_names = [node.name for node in bp.nodes]
codex/verify-the-structure-m8z187
main
    duplicate_nodes = _duplicate_values(node_names)
    if duplicate_nodes:
        raise BlueprintError(f"Duplicate node names are not allowed: {sorted(duplicate_nodes)}")

    known_networks = set(net_names)
    for node in bp.nodes:
codex/verify-the-structure-m8z187
main
        if not node.networks:
            raise BlueprintError(f"Node '{node.name}' must reference at least one network.")

        duplicate_node_networks = _duplicate_values(node.networks)
        if duplicate_node_networks:
            raise BlueprintError(
                f"Node '{node.name}' has duplicate network references: {sorted(duplicate_node_networks)}"
            )

        unknown_networks = sorted(set(node.networks) - known_networks)
        if unknown_networks:
            raise BlueprintError(
                f"Node '{node.name}' references unknown networks: {unknown_networks}. "
codex/verify-the-structure-m8z187
main
                "Declare the network in blueprint.networks first."
            )
