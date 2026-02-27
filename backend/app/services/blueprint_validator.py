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
    net_names = [n.name for n in bp.networks]
    duplicate_networks = _duplicate_values(net_names)
    if duplicate_networks:
        raise BlueprintError(f"Duplicate network names are not allowed: {sorted(duplicate_networks)}")

    node_names = [n.name for n in bp.nodes]
    duplicate_nodes = _duplicate_values(node_names)
    if duplicate_nodes:
        raise BlueprintError(f"Duplicate node names are not allowed: {sorted(duplicate_nodes)}")

    known_networks = set(net_names)
    for node in bp.nodes:
        unknown = sorted(set(node.networks) - known_networks)
        if unknown:
            raise BlueprintError(
                f"Node '{node.name}' references unknown networks: {unknown}. "
                "Declare the network in blueprint.networks first."
            )
