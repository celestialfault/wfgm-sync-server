from __future__ import annotations

import os
import typing
from datetime import timedelta

from beanie import Document, init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, UUID4


class UserConfig(BaseModel):
    """User configuration model storing the same data the mod stores locally

    All fields not present in this model will be ignored when the mod sends the client's settings to the server.
    """

    username: UUID4

    ### NOTE TO CONTRIBUTORS: ##
    # All fields below MUST have their default value listed, otherwise things WILL break!

    # Refers to ordinal value of Gender in the mod source
    #  0 = female, 1 = male, 2 = other
    gender: typing.Literal[0, 1, 2] = 1

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
    uuid: UUID4
    data: UserConfig

    @classmethod
    async def find_one_or_create(cls, uuid: UUID4) -> User:
        existing = await cls.find_one(User.uuid == uuid)
        return existing or cls(uuid=uuid, data=UserConfig(username=uuid))


async def init_db():
    host = os.environ.get("MONGO_HOST", "mongodb://localhost:27017")
    client = AsyncIOMotorClient(host, serverSelectionTimeoutMS=5_000)
    await init_beanie(database=client["wfgm-sync"], document_models=[User])
