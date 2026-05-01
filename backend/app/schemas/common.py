from typing import Any

from pydantic import BaseModel, ConfigDict


class StubResponse(BaseModel):
    message: str
    data: dict[str, Any] = {}

    model_config = ConfigDict(from_attributes=True)
