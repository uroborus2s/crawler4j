from typing import Optional

from pydantic import BaseModel, Field


class CtripConfig(BaseModel):
    """Configuration for Ctrip Task."""
    city_name: str = Field(default="Shanghai", description="City to search")
    hotel_name: Optional[str] = Field(default=None, description="Specific hotel name")
    check_in_date: Optional[str] = Field(default=None, description="Check-in date (YYYY-MM-DD)")
    days: int = Field(default=1, ge=1, le=30, description="Stay duration")
    headless: bool = Field(default=False, description="Run in headless mode")
