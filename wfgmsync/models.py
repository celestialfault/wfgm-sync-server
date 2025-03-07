from __future__ import annotations

from datetime import datetime

from beanie.odm.operators.find.comparison import In
from beanie.odm.operators.find.logical import And
from pydantic import BaseModel, UUID4

from wfgmsync.db import UserConfig, User


class SuccessResponse(BaseModel):
    success: bool = True


class BulkQueryResponse(SuccessResponse):
    users: dict[UUID4, UserConfig]

    @classmethod
    async def find(cls, uuids: set[UUID4]) -> BulkQueryResponse:
        # noinspection PyComparisonWithNone
        return cls(
            users={
                x.uuid: x.data
                async for x in User.find_many(And(In(User.uuid, uuids), User.data != None))
            }
        )


class AuthenticatedResponse(SuccessResponse):
    token: str
    account: UUID4
    expires: datetime


class ErrorResponse(BaseModel):
    success: bool = False
    error: str


class StatsResponse(BaseModel):
    synced_users: int
    timestamp: datetime
