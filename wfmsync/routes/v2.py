from typing import Annotated

from fastapi import FastAPI, Header
from pydantic import UUID4

from wfmsync.db import ContributorNametag, UserConfig
from wfmsync.models import SuccessResponse

v2 = FastAPI()


@v2.get("/user/{uuid}")
async def query(uuid: UUID4) -> UserConfig:
    pass


@v2.put("/user/{uuid}")
async def update(uuid: UUID4, body: UserConfig) -> SuccessResponse:
    pass


@v2.get("/contributors")
async def contributors() -> dict[UUID4, ContributorNametag]:
    pass


@v2.put("/contributors/{uuid}")
async def update_contributor(uuid: UUID4, admin_token: Annotated[str, Header()], body: ContributorNametag) -> SuccessResponse:
    pass


@v2.delete("/contributors/{uuid}")
async def update_contributor(uuid: UUID4, admin_token: Annotated[str, Header()]) -> SuccessResponse:
    pass
