import asyncio
import logging
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import Annotated
from uuid import UUID

import aiohttp
from beanie.operators import In
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.params import Query, Header
from pydantic import UUID4
from starlette.responses import JSONResponse, PlainTextResponse, RedirectResponse, Response

from db import init_db, UserConfig, User, UserAuth, ContributorNametag
from models import (
    ErrorResponse,
    SuccessResponse,
    AuthenticatedResponse,
    BulkQueryResponse,
    StatsResponse,
)

SESSION: aiohttp.ClientSession = ...


@asynccontextmanager
async def lifecycle(_):
    global SESSION

    SESSION = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=4))
    load_dotenv()
    await init_db()

    logging.getLogger("uvicorn.access").disabled = True

    yield

    await SESSION.close()


app = FastAPI(lifespan=lifecycle)


class InvalidAuthenticationError(RuntimeError):
    message: str

    def __init__(self, message: str):
        self.message = message


class AuthServerError(RuntimeError):
    message: str

    def __init__(self, message: str):
        self.message = message


async def validate_session_server(server_id: str, username: str) -> UUID4:
    url = "https://sessionserver.mojang.com/session/minecraft/hasJoined"
    params = {"username": username, "serverId": server_id}
    async with SESSION.get(url, params=params) as response:
        if response.status >= 400:
            raise AuthServerError(
                f"Session servers returned an unexpected response status {response.status}"
            )
        json = await response.json()
        if not json or "id" not in json:
            raise InvalidAuthenticationError("Couldn't authenticate with Mojang")
        return UUID(json["id"])


@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse("https://modrinth.com/mod/female-gender")


# if only QUERY wasn't still a draft...
@app.post(
    "/",
    response_model=BulkQueryResponse,
    responses={400: {"model": ErrorResponse}},
    summary="Get data for multiple players",
)
async def get_multiple_players(body: set[UUID4]):
    """Get player data for up to 20 unique UUIDs at once

    Any provided UUIDs that the server doesn't have any sync data for will simply be omitted from
    the returned users object.
    """
    if len(body) < 2:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "This route requires at least 2 unique UUIDs to be provided",
            },
        )
    if len(body) > 20:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Bulk queries have a limit of 20 unique UUIDs at once",
            },
        )

    return {
        "success": True,
        "users": {x.uuid: x.data async for x in User.find_many(In(User.uuid, body))},
    }


@app.get(
    "/contributors",
    response_model=dict[UUID4, ContributorNametag],
    summary="Get contributor nametags",
)
async def contributors(response: Response):
    response.headers["Cache-Control"] = "public,max-age=3600"
    # noinspection PyComparisonWithNone
    return {x.uuid: x.nametag async for x in User.find(User.nametag != None)}


@app.put(
    "/contributor/{uuid}",
    response_model=SuccessResponse,
    responses={401: {}},
    summary="Update contributor nametag",
)
async def update_contributor(
    uuid: UUID4, auth_token: Annotated[str, Header()], body: ContributorNametag
):
    """Internal endpoint, updates the nametag stored for a contributor"""
    if auth_token != os.environ["ADMIN_TOKEN"]:
        return PlainTextResponse(status_code=401)

    user = await User.find_one(User.uuid == uuid)
    if user is None:
        user = User(uuid=uuid, data=UserConfig())
        # noinspection PyArgumentList
        await user.insert()
    await user.set({User.nametag: body})

    return {"success": True}


@app.delete(
    "/contributor/{uuid}",
    response_model=SuccessResponse,
    responses={401: {}, 404: {"model": ErrorResponse}},
    summary="Delete contributor nametag",
)
async def delete_contributor(uuid: UUID4, auth_token: Annotated[str, Header()]):
    """Internal endpoint, deletes any nametag stored for a contributor"""
    if auth_token != os.environ["ADMIN_TOKEN"]:
        return PlainTextResponse(status_code=401)

    user = await User.find_one(User.uuid == uuid)
    if user is None:
        return JSONResponse(
            status_code=404, content={"success": False, "error": "No such user exists"}
        )
    await user.set({User.nametag: None})

    return {"success": True}


@app.get("/stats", response_model=StatsResponse, summary="Get sync server statistics")
async def stats(response: Response):
    response.headers["Cache-Control"] = "public,max-age=300"
    return {"synced_users": await User.count(), "timestamp": datetime.now(timezone.utc)}


@app.get("/health-check", include_in_schema=False)
async def healthcheck(response: Response):
    response.headers["Cache-Control"] = "nostore"
    return PlainTextResponse(status_code=204)


# TODO wiki.vg is no more; update the link in the docstring here with a minecraft.wiki one at some point
@app.get(
    "/auth",
    response_model=AuthenticatedResponse,
    responses={403: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Get authentication token",
)
async def get_auth(
    server_id: Annotated[str, Query(alias="serverId")],
    username: Annotated[str, Query()],
    response: Response,
):
    """Retrieve an authentication token used for updating player data

    This route requires [authenticating with Mojang's session servers](https://wiki.vg/Protocol_Encryption#Authentication).

    The provided authentication token will expire after 1 hour.

    Any authentication tokens that haven't yet expired will be invalidated after obtaining a new token.
    """
    response.headers["Cache-Control"] = "no-store"

    try:
        uuid = await validate_session_server(server_id, username)
    except AuthServerError as e:
        return JSONResponse(status_code=500, content={"success": False, "error": e.message})
    except InvalidAuthenticationError as e:
        return JSONResponse(status_code=403, content={"success": False, "error": e.message})
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Couldn't reach the authentication servers"},
        )

    await UserAuth.find_many(UserAuth.uuid == uuid).delete_many()
    auth = UserAuth(
        uuid=uuid, token=secrets.token_urlsafe(32), created_at=datetime.now(timezone.utc)
    )
    # noinspection PyArgumentList
    await auth.insert()

    return {
        "success": True,
        "token": auth.token,
        "account": auth.uuid,
        "expires": auth.created_at + timedelta(hours=1),
    }


@app.put(
    "/{uuid}",
    response_model=SuccessResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Update player data",
)
async def update_data(uuid: UUID4, auth_token: Annotated[str, Header()], body: UserConfig, response: Response):
    """Stores the provided player data for the given authenticated user

    This requires an `Auth-Token` header provided from the `/auth` route.
    """
    response.headers["Cache-Control"] = "no-store"

    auth = await UserAuth.find_one(UserAuth.token == auth_token)
    if not auth:
        return JSONResponse(
            status_code=401,
            content={"success": False, "error": "Authentication is invalid or has expired"},
        )
    if auth.uuid != uuid:
        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "error": "The given authentication is not valid for the current user",
            },
        )

    user = await User.find_one_or_create(uuid)
    user.data = body
    # shut up pycharm
    # noinspection PyArgumentList
    await user.save()
    return {"success": True}


@app.get("/{uuid}", response_model=UserConfig, responses={404: {}}, summary="Get player data")
async def get_player(uuid: UUID4, response: Response):
    response.headers["Cache-Control"] = "public,max-age=600"
    user = await User.find_one(User.uuid == uuid)
    return user and user.data or PlainTextResponse(status_code=404)
