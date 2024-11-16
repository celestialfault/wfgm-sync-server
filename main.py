import asyncio
from contextlib import asynccontextmanager
from typing import Annotated, Literal
from uuid import UUID

import aiohttp
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.params import Query
from pydantic import UUID4
from starlette.responses import JSONResponse, PlainTextResponse, RedirectResponse

from db import init_db, UserConfig, User
from models import ErrorResponse, SuccessResponse


SESSION = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=4))


@asynccontextmanager
async def lifecycle(_):
    load_dotenv()
    await init_db()

    yield

    await SESSION.close()


app = FastAPI(lifespan=lifecycle)


class AuthError(RuntimeError):
    message: str

    def __init__(self, message: str):
        self.message = message


async def _validate(uuid: UUID4, server_id: str, username: str) -> Literal[True]:
    url = "https://sessionserver.mojang.com/session/minecraft/hasJoined"
    params = {"username": username, "serverId": server_id}
    async with SESSION.get(url, params=params) as response:
        response.raise_for_status()
        json = await response.json()
        if "id" not in json:
            raise AuthError("Couldn't authenticate with Mojang")
        if UUID(json.get("id")) != uuid:
            raise AuthError("Authenticated user does not match")
        return True


@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse("https://modrinth.com/mod/female-gender")


@app.put(
    "/{uuid}",
    response_model=SuccessResponse,
    responses={403: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Update player data"
)
async def update_data(uuid: UUID4, server_id: Annotated[str, Query(alias="serverId")], username: Annotated[str, Query()], config: UserConfig):
    """Stores the provided player data under the provided UUID

    This route requires [authenticating with Mojang's session servers](https://wiki.vg/Protocol_Encryption#Authentication).
    """

    try:
        await _validate(uuid, server_id, username)
    except AuthError as e:
        return JSONResponse(status_code=403, content={"success": False, "error": f"Invalid authentication: {e.message}"})
    except asyncio.TimeoutError:
        return JSONResponse(status_code=500, content={"success": False, "error": "Couldn't reach authentication servers"})

    user = await User.find_one_or_create(uuid)
    user.data = config
    # shut up pycharm
    # noinspection PyArgumentList
    await user.save()
    return {"success": True}


@app.get("/{uuid}", response_model=UserConfig, responses={404: {}}, summary="Get player data")
async def get_player(uuid: UUID4):
    user = await User.find_one(User.uuid == uuid)
    return user and user.data or PlainTextResponse(status_code=404)
