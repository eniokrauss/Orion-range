from typing import Annotated, List, Optional

from pydantic import BaseModel, Field, StringConstraints

BlueprintString = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]


class NetworkBP(BaseModel):
    name: BlueprintString
    cidr: Optional[str] = None
    vlan_id: Optional[int] = Field(default=None, ge=1, le=4094)


class NodeBP(BaseModel):
    name: BlueprintString
    role: BlueprintString = "generic"
    os: BlueprintString = "linux"
    networks: List[BlueprintString] = Field(default_factory=list)
    proxmox_template_vmid: Optional[int] = Field(
        default=None,
        description="Future: VMID of a Proxmox template to clone from",
        ge=100,
    )


class LabBlueprint(BaseModel):
    name: BlueprintString
    version: str = Field(default="0.1.0", pattern=r"^\d+\.\d+\.\d+$")
    networks: List[NetworkBP] = Field(default_factory=list)
    nodes: List[NodeBP] = Field(default_factory=list)
