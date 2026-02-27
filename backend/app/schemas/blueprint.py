from typing import List, Optional

from pydantic import BaseModel, Field


class NetworkBP(BaseModel):
    name: str = Field(min_length=1)
    cidr: Optional[str] = None
    vlan_id: Optional[int] = Field(default=None, ge=1, le=4094)


class NodeBP(BaseModel):
    name: str = Field(min_length=1)
    role: str = "generic"
    os: str = "linux"
    networks: List[str] = Field(default_factory=list)
    proxmox_template_vmid: Optional[int] = Field(
        default=None,
        description="Future: VMID of a Proxmox template to clone from",
        ge=100,
    )


class LabBlueprint(BaseModel):
    name: str = Field(min_length=1)
codex/verify-the-structure-kqxjtv
    version: str = "0.1.0"
main
    networks: List[NetworkBP] = Field(default_factory=list)
    nodes: List[NodeBP] = Field(default_factory=list)
