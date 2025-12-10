from ast import alias
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime

# The input model that whatsapp sends us
class WebhookPayload(BaseModel):
    message_id: str = Field(..., min_length=1)
    from_msisdn: str = Field(..., alias="from") # Map JSON "from" -> Python "from_msisdn"
    to_msisdn: str = Field(..., alias="to")
    ts: str
    text: Optional[str] = Field(None, max_length=4096)

    class Config:
        populate_by_name = True

# The output model that we send back to the user
class MessageResponse(BaseModel):
    message_id: str
    from_msisdn: str = Field(..., serialization_alias="from") # When sending JSON out, rename back to "from"
    to_msisdn: str = Field(..., serialization_alias="to")
    ts: str
    text: Optional[str]
    created_at: str
    
# Stats Model for /stats endpoint
class StatsResponse(BaseModel):
    total_messages: int
    senders_count: int
    messages_per_sender: list[dict]
    first_message_ts: Optional[str]
    last_message_ts: Optional[str]