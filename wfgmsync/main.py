import logging
import os
from contextlib import asynccontextmanager
from datetime import timezone, datetime
from typing import Annotated

import aiohttp
from dotenv import load_dotenv
from fastapi import FastAPI, Query, Header
from pydantic import UUID4

from wfgmsync import common
from wfgmsync.db import init_db, User, ContributorNametag, UserConfig
from wfgmsync.models import (
    StatsResponse,
    ErrorResponse,
    BulkQueryResponse,
    AuthenticatedResponse,
    SuccessResponse,
)
from wfgmsync.routes import v1, v2, contributors


@asynccontextmanager
async def lifecycle(_):
    common.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=4))
    load_dotenv()
    await init_db()

    if "SILENCE_ACCESS_LOGS" in os.environ:
        logging.getLogger("uvicorn.access").disabled = True

    yield

    await common.session.close()


app = FastAPI(
    lifespan=lifecycle,
    docs_url="/",
    version="2.0.0",
    description="""
Sync server for [Female Gender Mod](https://github.com/WildfireRomeo/WildfireFemaleGenderMod);
for documentation on all available routes, see also:

- [v2](/v2/)
- [v1](/v1/)
- [contributor](/contributor/) (internal)
""",
)
app.mount("/v2", v2.app)
app.mount("/v1", v1.app)
app.mount("/contributor", contributors.app)


@app.get("/stats", response_model=StatsResponse, summary="Get sync server statistics")
async def stats():
    return {"synced_users": await User.count(), "timestamp": datetime.now(timezone.utc)}


@app.get(
    "/contributors",
    response_model=dict[UUID4, ContributorNametag],
    summary="Get contributor nametags",
)
async def contributors():
    # noinspection PyComparisonWithNone
    return {x.uuid: x.nametag async for x in User.find(User.nametag != None)}


# region Legacy stub routes


@app.post(
    "/",
    response_model=BulkQueryResponse,
    responses={400: {"model": ErrorResponse}},
    summary="Get data for multiple players",
    deprecated=True,
)
async def bulk_query(body: set[UUID4]):
    """**Deprecated:** This route is a legacy alias for `POST /v1/`"""
    return await v1.get_multiple_players(body)


@app.get(
    "/{uuid}",
    response_model=UserConfig,
    responses={404: {}},
    summary="Get player data",
    deprecated=True,
)
async def get_player(uuid: UUID4):
    """**Deprecated:** This route is a legacy alias for `GET /v1/{uuid}`"""
    return await v1.get_player(uuid)


@app.get(
    "/auth",
    response_model=AuthenticatedResponse,
    responses={403: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Get authentication token",
    deprecated=True,
)
async def get_auth(
    server_id: Annotated[str, Query(alias="serverId")], username: Annotated[str, Query()]
):
    """**Deprecated:** This route is a legacy alias for `GET /v1/auth`"""
    return await v1.get_auth(server_id, username)


@app.put(
    "/{uuid}",
    response_model=SuccessResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Update player data",
    deprecated=True,
)
async def update_data(uuid: UUID4, auth_token: Annotated[str, Header()], body: UserConfig):
    """**Deprecated:** This route is a legacy alias for `PUT /v1/{uuid}`"""
    return await v1.update_data(uuid, auth_token, body)


# endregion
