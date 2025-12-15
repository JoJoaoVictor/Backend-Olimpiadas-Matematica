from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Schema base com configurações padrão."""
    model_config = ConfigDict(from_attributes=True)

 
class TimestampedSchema(BaseSchema):
    """Schema base com timestamps."""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None