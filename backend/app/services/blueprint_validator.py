from app.schemas.blueprint import LabBlueprint

class BlueprintError(Exception):
    pass

def validate_blueprint(bp: LabBlueprint) -> None:
    net_names = [n.name for n in bp.networks]
    if len(net_names) != len(set(net_names)):
        raise BlueprintError("Duplicate network names are not allowed.")

    node_names = [n.name for n in bp.nodes]
    if len(node_names) != len(set(node_names)):
        raise BlueprintError("Duplicate node names are not allowed.")
