from typing import Annotated, List, Optional

from pydantic import BaseModel, Field, StringConstraints, field_validator

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
    version: str = Field(default="0.1.0")
    networks: List[NetworkBP] = Field(default_factory=list)
    nodes: List[NodeBP] = Field(default_factory=list)

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        parts = value.split(".")
        if len(parts) == 2 and all(part.isdigit() for part in parts):
            return f"{parts[0]}.{parts[1]}.0"

        if len(parts) == 3 and all(part.isdigit() for part in parts):
            return value

        raise ValueError("version must follow numeric semantic format: x.y or x.y.z")
