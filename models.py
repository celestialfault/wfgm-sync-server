from datetime import datetime

from pydantic import BaseModel, UUID4

from db import UserConfig


class SuccessResponse(BaseModel):
    success: bool = True


class BulkQueryResponse(BaseModel):
    success: bool = True
    users: dict[UUID4, UserConfig]


class StatsResponse(BaseModel):
    synced_users: int
    timestamp: datetime


class AuthenticatedResponse(BaseModel):
    success: bool = True
    token: str
    account: UUID4
    expires: datetime


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
