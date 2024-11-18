from __future__ import annotations

import enum
import os
from datetime import timedelta, datetime
from typing import Annotated

from beanie import Document, init_beanie, Indexed
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, UUID4


# fastapi docs suck for enums, so just document the ordinals in the doc string here
class Gender(enum.IntEnum):
    """Integer value referencing the ordinal value of the Gender enum in the mod

    - `FEMALE`: 0
    - `MALE`: 1
    - `OTHER`: 2
    """

    FEMALE = 0
    MALE = 1
    OTHER = 2


class UserAuth(Document):
    uuid: UUID4
    token: Annotated[str, Indexed(unique=True)]
    created_at: Annotated[datetime, Indexed(expireAfterSeconds=60 * 60)]


class UserConfig(BaseModel):
    """User configuration model storing the same data the mod stores locally

    All fields not present in this model will be ignored when the mod sends the client's settings to the server.
    """

    username: UUID4

    ### NOTE TO CONTRIBUTORS: ##
    # All fields below MUST have their default value listed, otherwise things WILL break!

    gender: Gender = Gender.MALE

    bust_size: float = 0.6
    hurt_sounds: bool = True

    breasts_xOffset: float = 0.0
    breasts_yOffset: float = 0.0
    breasts_zOffset: float = 0.0
    breasts_uniboob: bool = True
    breasts_cleavage: float = 0.0

    breast_physics: bool = True
    # armor_physics_override is intentionally skipped
    show_in_armor: bool = True
    bounce_multiplier: float = 0.333
    floppy_multiplier: float = 0.75

    class Settings:
        use_cache = True
        cache_expiration_time = timedelta(minutes=10)
        cache_capacity = 2048


class User(Document):
    uuid: Annotated[UUID4, Indexed()]
    data: UserConfig

    @classmethod
    async def find_one_or_create(cls, uuid: UUID4) -> User:
        existing = await cls.find_one(User.uuid == uuid)
        return existing or cls(uuid=uuid, data=UserConfig(username=uuid))


async def init_db():
    host = os.environ.get("MONGO_HOST", "mongodb://localhost:27017")
    client = AsyncIOMotorClient(host, serverSelectionTimeoutMS=5_000)
    await init_beanie(database=client["wfgm-sync"], document_models=[User, UserAuth])
