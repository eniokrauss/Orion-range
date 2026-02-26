from pydantic import BaseModel, Field
from typing import List, Optional

class NetworkBP(BaseModel):
    name: str
    cidr: Optional[str] = None
    vlan_id: Optional[int] = None

class NodeBP(BaseModel):
    name: str
    role: str = "generic"
    os: str = "linux"
    proxmox_template_vmid: Optional[int] = Field(
        default=None,
        description="Future: VMID of a Proxmox template to clone from",
    )

class LabBlueprint(BaseModel):
    name: str
    version: str = "0.1"
    networks: List[NetworkBP] = []
    nodes: List[NodeBP] = []
