import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import Annotated
from uuid import UUID

import aiohttp
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.params import Query, Header
from pydantic import UUID4
from starlette.responses import JSONResponse, PlainTextResponse, RedirectResponse

from db import init_db, UserConfig, User, UserAuth
from models import ErrorResponse, SuccessResponse, AuthenticatedResponse

SESSION: aiohttp.ClientSession = ...


@asynccontextmanager
async def lifecycle(_):
    global SESSION

    SESSION = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=4))
    load_dotenv()
    await init_db()

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
            raise AuthServerError(f"Session servers returned an unexpected response status {response.status}")
        json = await response.json()
        if error := json.get("error"):
            raise InvalidAuthenticationError(f"Session servers returned an error: {error}")
        if "id" not in json:
            raise InvalidAuthenticationError("Couldn't authenticate with Mojang")
        return UUID(json["id"])


@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse("https://modrinth.com/mod/female-gender")


@app.get(
    "/auth",
    response_model=AuthenticatedResponse,
    responses={403: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Get authentication token"
)
async def get_auth(server_id: Annotated[str, Query(alias="serverId")], username: Annotated[str, Query()]):
    """Retrieve an authentication token used for updating player data

    This route requires [authenticating with Mojang's session servers](https://wiki.vg/Protocol_Encryption#Authentication).

    The provided authentication token will expire after 1 hour.

    Any authentication tokens that haven't yet expired will be invalidated after obtaining a new token.
    """
    try:
        uuid = await validate_session_server(server_id, username)
    except AuthServerError as e:
        return JSONResponse(status_code=500, content={"success": False, "error": e.message})
    except InvalidAuthenticationError as e:
        return JSONResponse(status_code=403, content={"success": False, "error": e.message})

    await UserAuth.find_many(UserAuth.uuid == uuid).delete_many()
    auth = UserAuth(uuid=uuid, token=secrets.token_urlsafe(32), created_at=datetime.now(timezone.utc))
    # noinspection PyArgumentList
    await auth.insert()

    return {
        "success": True,
        "token": auth.token,
        "account": auth.uuid,
        "expires": auth.created_at + timedelta(hours=1)
    }


@app.put(
    "/{uuid}",
    response_model=SuccessResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Update player data"
)
async def update_data(uuid: UUID4, auth_token: Annotated[str, Header()], body: UserConfig):
    """Stores the provided player data for the given authenticated user

    This requires an `Auth-Token` header provided from the `/auth` route.
    """

    auth = await UserAuth.find_one(UserAuth.token == auth_token)
    if not auth:
        return JSONResponse(status_code=401, content={"success": False, "error": "Authentication is invalid or has expired"})
    if auth.uuid != uuid:
        return JSONResponse(status_code=403, content={"success": False, "error": "The given authentication is not valid for the current user"})

    user = await User.find_one_or_create(uuid)
    user.data = body
    # shut up pycharm
    # noinspection PyArgumentList
    await user.save()
    return {"success": True}


@app.get("/{uuid}", response_model=UserConfig, responses={404: {}}, summary="Get player data")
async def get_player(uuid: UUID4):
    user = await User.find_one(User.uuid == uuid)
    return user and user.data or PlainTextResponse(status_code=404)
