from pydantic import BaseModel, Field


class ScenarioStep(BaseModel):
    name: str = Field(min_length=1)
    action: str = Field(min_length=1)
    delay_ms: int = Field(default=0, ge=0, le=60000)


class ScenarioStartRequest(BaseModel):
    scenario_name: str = Field(min_length=1)
    steps: list[ScenarioStep] = Field(default_factory=list)


class ScenarioRunResponse(BaseModel):
    id: str
    scenario_name: str
    status: str
    timeline: list[dict]
