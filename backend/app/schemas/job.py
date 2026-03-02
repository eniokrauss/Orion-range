from pydantic import BaseModel, Field


class CreateJobRequest(BaseModel):
    action: str = Field(min_length=1)
    target_blueprint_id: str | None = None
    max_attempts: int = Field(default=3, ge=1, le=10)


class JobResponse(BaseModel):
    id: str
    action: str
    status: str
    target_blueprint_id: str | None = None
    attempts: int
    max_attempts: int
    last_error: str | None = None
