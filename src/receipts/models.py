"""Receipt data models."""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class ReceiptUploadRequest(BaseModel):
    """Receipt upload request model."""

    image_data: str = Field(..., description="Base64-encoded image data")
    filename: str = Field(..., description="Original filename")
    content_type: Optional[str] = Field(default="image/jpeg", description="Image content type")


class Receipt(BaseModel):
    """Receipt model."""

    user_id: str
    receipt_id: str
    s3_key: str
    filename: str
    status: str = "pending"  # pending, processing, processed, failed
    uploaded_at: str
    processed_at: Optional[str] = None
    error_message: Optional[str] = None

    class Config:
        """Pydantic config."""
        from_attributes = True
